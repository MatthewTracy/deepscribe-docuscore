"""
Evaluation pipeline orchestrator.

Ties together all layers:
1. Deterministic checks (fast, free)
2. LLM judge (Claude, per-note)
3. Quality gate (decision logic)
4. Meta-evaluation (reliability testing)

Coding intelligence (src/coding/) is exploratory and not integrated into the
core pipeline. Initial work completed but deferred pending ground-truth coding data.

The pipeline processes notes sequentially to respect API rate limits
and provide clear progress tracking. Each note produces an EvalReport;
all reports are aggregated into a BatchReport with summary statistics.
"""

import json
import time
from pathlib import Path

from src.models import (
    BatchReport,
    CodingResult,
    EvalReport,
    NoteInput,
    QualityGate,
    QualityGateResult,
)
from src.deterministic.checks import run_deterministic_checks
from src.llm_judge.judge import evaluate_note
from src.coding.analyzer import analyze_coding
from src.coding.icd_index import ICDIndex
from src.meta_eval.consistency import run_meta_evaluation


def _compute_quality_gate(
    deterministic_result,
    llm_result,
) -> QualityGateResult:
    """
    Determine quality gate: PASS / REVIEW / FAIL.

    Based on deterministic checks + LLM judge only. Coding intelligence
    is kept separate - it's a proof-of-concept without ground-truth ICD
    codes, so mixing unvalidated coding gaps into the quality gate would
    undermine the gate's credibility.

    FAIL conditions (any one triggers):
    - Critical hallucination detected
    - Section completeness < 0.75 (missing a section)
    - Overall quality score <= 2
    - 3+ major hallucinations

    REVIEW conditions (any one triggers):
    - Major hallucination detected
    - Entity grounding rate < 0.7
    - Any contradiction found
    - Overall quality score == 3
    - Layer discrepancy (high grounding but many LLM-detected hallucinations)

    PASS: Everything else
    """
    reasons = []

    # Check for FAIL conditions
    critical_hallucinations = [
        h for h in llm_result.hallucinations
        if h.severity == "critical"
    ]
    if critical_hallucinations:
        reasons.append(f"Critical hallucination: {critical_hallucinations[0].note_text[:80]}")
        return QualityGateResult(decision=QualityGate.FAIL, reasons=reasons)

    if deterministic_result.section_completeness_score < 0.75:
        reasons.append(f"Missing SOAP sections (completeness: {deterministic_result.section_completeness_score:.0%})")
        return QualityGateResult(decision=QualityGate.FAIL, reasons=reasons)

    if llm_result.overall_quality <= 2:
        reasons.append(f"Very low quality score: {llm_result.overall_quality}/5")
        return QualityGateResult(decision=QualityGate.FAIL, reasons=reasons)

    # FAIL: Many major hallucinations indicate a fundamentally unreliable note
    major_hallucinations = [
        h for h in llm_result.hallucinations
        if h.severity == "major"
    ]
    if len(major_hallucinations) >= 3:
        reasons.append(f"{len(major_hallucinations)} major hallucination(s) - note is unreliable")
        return QualityGateResult(decision=QualityGate.FAIL, reasons=reasons)

    # Check for REVIEW conditions
    if major_hallucinations:
        reasons.append(f"{len(major_hallucinations)} major hallucination(s) detected")

    if deterministic_result.entity_grounding_rate < 0.7 and len(deterministic_result.entities_checked) > 0:
        reasons.append(f"Low entity grounding: {deterministic_result.entity_grounding_rate:.0%}")

    if deterministic_result.contradictions:
        reasons.append(f"{len(deterministic_result.contradictions)} contradiction(s) found")

    if llm_result.overall_quality == 3:
        reasons.append("Borderline quality score: 3/5")

    # Cross-validation: check for discrepancy between deterministic grounding
    # and LLM hallucination findings. High grounding + many hallucinations
    # suggests the deterministic layer missed issues the LLM caught.
    hallucination_count = len(llm_result.hallucinations)
    grounding_rate = deterministic_result.entity_grounding_rate
    if grounding_rate > 0.85 and hallucination_count >= 3:
        reasons.append(
            f"Layer discrepancy: deterministic grounding={grounding_rate:.0%} "
            f"but LLM found {hallucination_count} hallucinations"
        )

    if reasons:
        return QualityGateResult(decision=QualityGate.REVIEW, reasons=reasons)

    return QualityGateResult(decision=QualityGate.PASS, reasons=["All checks passed"])


def _compute_overall_score(deterministic_result, llm_result) -> float:
    """
    Compute a normalized 0-1 overall score from all layers.

    Weighted combination:
    - Section completeness: 15%
    - Entity grounding: 15%
    - LLM section scores average: 50%
    - Hallucination penalty: 20% (deducted)
    """
    # Section completeness (0-1)
    completeness = deterministic_result.section_completeness_score

    # Entity grounding (0-1)
    grounding = deterministic_result.entity_grounding_rate

    # Average LLM section scores (1-5 → 0-1)
    section_avg = 0.0
    if llm_result.section_scores:
        all_scores = []
        for section_score in llm_result.section_scores.values():
            all_scores.extend([
                section_score.completeness,
                section_score.faithfulness,
                section_score.clinical_accuracy,
            ])
        section_avg = (sum(all_scores) / len(all_scores) - 1) / 4  # normalize 1-5 to 0-1

    # Hallucination penalty
    critical = len([h for h in llm_result.hallucinations if h.severity == "critical"])
    major = len([h for h in llm_result.hallucinations if h.severity == "major"])
    minor = len([h for h in llm_result.hallucinations if h.severity == "minor"])
    hallucination_penalty = min(1.0, (critical * 0.3 + major * 0.15 + minor * 0.05))

    score = (
        0.15 * completeness
        + 0.15 * grounding
        + 0.50 * section_avg
        + 0.20 * (1.0 - hallucination_penalty)
    )

    return round(max(0.0, min(1.0, score)), 3)


def evaluate_single_note(
    note: NoteInput,
    icd_index: ICDIndex,
    skip_coding: bool = False,
) -> EvalReport:
    """Evaluate a single note through all layers."""

    # Layer 1: Deterministic checks
    det_result, _sections = run_deterministic_checks(note.soap_note, note.transcript)

    # Layer 2: LLM judge
    llm_result = evaluate_note(note.transcript, note.soap_note)

    # Layer 3: Coding intelligence
    if skip_coding:
        coding_result = CodingResult()
    else:
        coding_result = analyze_coding(note.transcript, note.soap_note, icd_index)

    # Quality gate (deterministic + LLM only; coding is a separate concern)
    gate = _compute_quality_gate(det_result, llm_result)

    # Overall score
    overall = _compute_overall_score(det_result, llm_result)

    return EvalReport(
        note_id=note.note_id,
        quality_gate=gate,
        overall_score=overall,
        deterministic=det_result,
        llm_judge=llm_result,
        coding=coding_result,
    )


def run_pipeline(
    notes: list[NoteInput],
    output_dir: Path,
    skip_coding: bool = False,
    skip_meta_eval: bool = False,
    progress_callback=None,
) -> BatchReport:
    """
    Run the full evaluation pipeline on a batch of notes.

    Args:
        notes: List of notes to evaluate
        output_dir: Where to write results
        skip_coding: Skip coding analysis (faster, cheaper)
        skip_meta_eval: Skip meta-evaluation
        progress_callback: Optional fn(current, total, note_id) for progress

    Returns:
        BatchReport with all results and aggregate stats
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build ICD-10 index once (shared across all notes)
    print("Building ICD-10 FAISS index...")
    icd_index = ICDIndex()
    print(f"  Index built: {len(icd_index.codes)} codes indexed")

    # Evaluate each note
    reports = []
    for i, note in enumerate(notes):
        start = time.time()
        if progress_callback:
            progress_callback(i + 1, len(notes), note.note_id)
        else:
            print(f"  [{i+1}/{len(notes)}] Evaluating {note.note_id}...", end=" ", flush=True)

        try:
            report = evaluate_single_note(note, icd_index, skip_coding=skip_coding)
            reports.append(report)
            elapsed = time.time() - start
            print(f"done ({elapsed:.1f}s) - gate={report.quality_gate.decision.value}, score={report.overall_score}")
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        # Save intermediate results every 10 notes
        if (i + 1) % 10 == 0:
            _save_intermediate(reports, output_dir)

    # Meta-evaluation
    meta_result = None
    if not skip_meta_eval:
        print("\nRunning meta-evaluation (15 synthetic test cases)...")
        meta_result = run_meta_evaluation()
        print(f"  Error detection: {meta_result.injected_errors_caught}/{meta_result.injected_errors_total} ({meta_result.injected_error_detection_rate:.0%})")

    # Compute aggregate stats
    batch = _build_batch_report(reports, meta_result)

    # Save final results
    results_path = output_dir / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        f.write(batch.model_dump_json(indent=2))
    print(f"\nResults saved to {results_path}")

    # Save raw notes data (frontend needs transcripts + SOAP notes for display)
    notes_data = [
        {"note_id": n.note_id, "transcript": n.transcript, "soap_note": n.soap_note}
        for n in notes
    ]
    notes_path = output_dir / "notes.json"
    with open(notes_path, "w", encoding="utf-8") as f:
        json.dump(notes_data, f, indent=2)
    print(f"Notes data saved to {notes_path}")

    # Save summary
    summary = _build_summary(batch)
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary saved to {summary_path}")

    return batch


def _save_intermediate(reports: list[EvalReport], output_dir: Path):
    """Save intermediate results for crash recovery."""
    path = output_dir / "results_partial.json"
    data = [r.model_dump() for r in reports]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _build_batch_report(
    reports: list[EvalReport],
    meta_result=None,
) -> BatchReport:
    """Compute aggregate statistics from individual reports."""
    gate_dist = {"PASS": 0, "REVIEW": 0, "FAIL": 0}
    total_hallucinations = 0
    total_omissions = 0
    total_coding_gaps = 0
    total_revenue = 0.0
    hallucination_types = {}
    gap_codes = {}

    for r in reports:
        gate_dist[r.quality_gate.decision.value] += 1
        total_hallucinations += len(r.llm_judge.hallucinations)
        total_omissions += len(r.llm_judge.omissions)
        total_coding_gaps += r.coding.total_gap_count
        total_revenue += r.coding.total_estimated_revenue_impact

        for h in r.llm_judge.hallucinations:
            hallucination_types[h.hallucination_type.value] = (
                hallucination_types.get(h.hallucination_type.value, 0) + 1
            )

        for g in r.coding.coding_gaps:
            if g.hcc_category:
                key = g.hcc_category
                if key not in gap_codes:
                    gap_codes[key] = {"hcc": key, "count": 0, "total_value": 0}
                gap_codes[key]["count"] += 1
                gap_codes[key]["total_value"] += g.estimated_annual_value or 0

    avg_score = sum(r.overall_score for r in reports) / len(reports) if reports else 0

    # Sort gap codes by total value
    sorted_gaps = sorted(gap_codes.values(), key=lambda x: x["total_value"], reverse=True)

    return BatchReport(
        total_notes=len(reports),
        reports=reports,
        meta_eval=meta_result,
        avg_overall_score=round(avg_score, 3),
        gate_distribution=gate_dist,
        total_hallucinations=total_hallucinations,
        total_omissions=total_omissions,
        total_coding_gaps=total_coding_gaps,
        total_estimated_revenue_impact=total_revenue,
        most_common_hallucination_types=hallucination_types,
        most_common_gap_codes=sorted_gaps[:10],
    )


def _build_summary(batch: BatchReport) -> dict:
    """Build a human-readable summary for the dashboard header."""
    return {
        "total_notes": batch.total_notes,
        "avg_score": batch.avg_overall_score,
        "gate_distribution": batch.gate_distribution,
        "total_hallucinations": batch.total_hallucinations,
        "total_omissions": batch.total_omissions,
        "total_coding_gaps": batch.total_coding_gaps,
        "total_estimated_revenue_impact": batch.total_estimated_revenue_impact,
        "hallucination_types": batch.most_common_hallucination_types,
        "top_coding_gaps": batch.most_common_gap_codes,
        "meta_eval": {
            "injected_error_detection_rate": batch.meta_eval.injected_error_detection_rate,
            "injected_errors_caught": batch.meta_eval.injected_errors_caught,
            "injected_errors_total": batch.meta_eval.injected_errors_total,
        } if batch.meta_eval else None,
    }
