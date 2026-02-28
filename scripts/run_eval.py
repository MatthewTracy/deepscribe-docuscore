"""
Run the evaluation pipeline on the sampled dataset.

Automatically resumes from partial results if a previous run was interrupted.

Usage:
    python scripts/run_eval.py                    # Full run (100 notes + meta-eval)
    python scripts/run_eval.py --quick             # Quick test (5 notes, no meta-eval)
    python scripts/run_eval.py --coding              # Enable coding analysis (off by default)
    python scripts/run_eval.py --no-meta           # Skip meta-evaluation
    python scripts/run_eval.py --count 20          # Evaluate first 20 notes
    python scripts/run_eval.py --fresh             # Ignore partial results, start fresh
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env
env_path = project_root / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip().strip("'\"")

from src.models import NoteInput, EvalReport
from src.pipeline import (
    run_pipeline,
    evaluate_single_note,
    _build_batch_report,
    _build_summary,
    _save_intermediate,
)
from src.coding.icd_index import ICDIndex
from src.meta_eval.consistency import run_meta_evaluation


def main():
    parser = argparse.ArgumentParser(description="Run evaluation pipeline")
    parser.add_argument("--quick", action="store_true", help="Quick test (5 notes, no meta-eval)")
    parser.add_argument("--coding", action="store_true", help="Enable coding analysis (skipped by default)")
    parser.add_argument("--no-meta", action="store_true", help="Skip meta-evaluation")
    parser.add_argument("--count", type=int, default=100, help="Number of notes to evaluate")
    parser.add_argument("--data", type=str, default="data/raw/sample_100.json", help="Path to notes JSON")
    parser.add_argument("--output", type=str, default="output", help="Output directory")
    parser.add_argument("--fresh", action="store_true", help="Ignore partial results, start fresh")
    args = parser.parse_args()

    if args.quick:
        args.count = 5
        args.no_meta = True
        print("Quick mode: 5 notes, no meta-eval")

    # Load notes
    data_path = project_root / args.data
    with open(data_path, encoding="utf-8") as f:
        raw_notes = json.load(f)

    notes = [
        NoteInput(
            note_id=n["note_id"],
            transcript=n["transcript"],
            soap_note=n["soap_note"],
        )
        for n in raw_notes[:args.count]
    ]
    print(f"Loaded {len(notes)} notes from {data_path}")

    output_dir = project_root / args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check for partial results to resume from
    partial_path = output_dir / "results_partial.json"
    completed_reports = []

    if not args.fresh and partial_path.exists():
        with open(partial_path, encoding="utf-8") as f:
            partial_data = json.load(f)
        expected_ids = {n.note_id for n in notes}
        matching = [r for r in partial_data if r["note_id"] in expected_ids]
        if matching:
            completed_reports = [EvalReport.model_validate(r) for r in matching]
            print(f"Resuming: {len(completed_reports)} notes already completed")

    if completed_reports:
        # Resume: evaluate only remaining notes
        completed_ids = {r.note_id for r in completed_reports}
        remaining = [n for n in notes if n.note_id not in completed_ids]
        print(f"Remaining: {len(remaining)} notes\n")

        if remaining:
            print("Building ICD-10 FAISS index...")
            icd_index = ICDIndex()
            print(f"  Index built: {len(icd_index.codes)} codes indexed\n")

            for i, note in enumerate(remaining):
                start = time.time()
                idx = len(completed_reports) + i + 1
                print(f"  [{idx}/{len(notes)}] Evaluating {note.note_id}...", end=" ", flush=True)

                try:
                    report = evaluate_single_note(note, icd_index, skip_coding=not args.coding)
                    completed_reports.append(report)
                    elapsed = time.time() - start
                    print(f"done ({elapsed:.1f}s) - gate={report.quality_gate.decision.value}, score={report.overall_score}")
                except Exception as e:
                    print(f"ERROR: {e}")
                    continue

                if (i + 1) % 10 == 0:
                    _save_intermediate(completed_reports, output_dir)

        # Meta-evaluation
        meta_result = None
        if not args.no_meta:
            print("\nRunning meta-evaluation (15 synthetic test cases)...")
            meta_result = run_meta_evaluation()
            print(f"  Error detection: {meta_result.injected_errors_caught}/{meta_result.injected_errors_total} ({meta_result.injected_error_detection_rate:.0%})")

        # Build and save final results
        batch = _build_batch_report(completed_reports, meta_result)

        results_path = output_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            f.write(batch.model_dump_json(indent=2))
        print(f"\nResults saved to {results_path}")

        notes_data = [
            {"note_id": n["note_id"], "transcript": n["transcript"], "soap_note": n["soap_note"]}
            for n in raw_notes[:args.count]
        ]
        notes_path = output_dir / "notes.json"
        with open(notes_path, "w", encoding="utf-8") as f:
            json.dump(notes_data, f, indent=2)
        print(f"Notes data saved to {notes_path}")

        summary = _build_summary(batch)
        summary_path = output_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"Summary saved to {summary_path}")

    else:
        # Fresh run
        batch = run_pipeline(
            notes=notes,
            output_dir=output_dir,
            skip_coding=not args.coding,
            skip_meta_eval=args.no_meta,
        )

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)
    print(f"Notes evaluated: {batch.total_notes}")
    print(f"Average score:   {batch.avg_overall_score:.3f}")
    print(f"Gate distribution: {batch.gate_distribution}")
    print(f"Hallucinations:  {batch.total_hallucinations}")
    print(f"Omissions:       {batch.total_omissions}")

    if batch.meta_eval:
        print(f"\nMeta-evaluation:")
        print(f"  Error detection: {batch.meta_eval.injected_errors_caught}/{batch.meta_eval.injected_errors_total} ({batch.meta_eval.injected_error_detection_rate:.0%})")


if __name__ == "__main__":
    main()
