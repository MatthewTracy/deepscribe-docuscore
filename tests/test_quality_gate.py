"""Tests for quality gate logic and scoring formula."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock heavy dependencies before importing pipeline
sys.modules.setdefault("numpy", MagicMock())
sys.modules.setdefault("faiss", MagicMock())
sys.modules.setdefault("sentence_transformers", MagicMock())

from src.models import (
    DeterministicResult,
    EntityGroundingResult,
    Hallucination,
    HallucinationType,
    LLMJudgeResult,
    Omission,
    SectionPresence,
    SectionScore,
)
from src.pipeline import _compute_quality_gate, _compute_overall_score


def _make_deterministic(completeness=1.0, grounding=0.9, contradictions=None):
    return DeterministicResult(
        sections_present=SectionPresence(
            subjective=True, objective=True, assessment=True, plan=True
        ),
        section_completeness_score=completeness,
        entities_checked=[
            EntityGroundingResult(entity="test", found_in_transcript=True)
        ],
        entity_grounding_rate=grounding,
        contradictions=contradictions or [],
    )


def _make_llm(
    quality=4,
    hallucinations=None,
    omissions=None,
):
    scores = {}
    for section in ["subjective", "objective", "assessment", "plan"]:
        scores[section] = SectionScore(
            completeness=4, faithfulness=4, clinical_accuracy=4,
            reasoning="Good."
        )
    return LLMJudgeResult(
        section_scores=scores,
        hallucinations=hallucinations or [],
        omissions=omissions or [],
        overall_quality=quality,
        overall_reasoning="Adequate note.",
    )


def _hallucination(severity="major", h_type=HallucinationType.FABRICATION):
    return Hallucination(
        note_text="fabricated text",
        hallucination_type=h_type,
        severity=severity,
        explanation="Not in transcript",
        transcript_context="not mentioned",
    )


# ── Quality Gate Tests ───────────────────────────────────────────────────────

def test_pass_when_clean():
    """Clean note with no issues should PASS."""
    det = _make_deterministic()
    llm = _make_llm()
    gate = _compute_quality_gate(det, llm)
    assert gate.decision.value == "PASS"


def test_fail_on_critical_hallucination():
    """A critical hallucination should trigger FAIL."""
    det = _make_deterministic()
    llm = _make_llm(hallucinations=[_hallucination("critical")])
    gate = _compute_quality_gate(det, llm)
    assert gate.decision.value == "FAIL"


def test_fail_on_missing_sections():
    """Low section completeness (< 0.75) should FAIL."""
    det = _make_deterministic(completeness=0.5)
    llm = _make_llm()
    gate = _compute_quality_gate(det, llm)
    assert gate.decision.value == "FAIL"


def test_fail_on_very_low_quality():
    """Overall quality <= 2 should FAIL."""
    det = _make_deterministic()
    llm = _make_llm(quality=2)
    gate = _compute_quality_gate(det, llm)
    assert gate.decision.value == "FAIL"


def test_fail_on_three_major_hallucinations():
    """3+ major hallucinations should FAIL."""
    det = _make_deterministic()
    llm = _make_llm(hallucinations=[_hallucination("major")] * 3)
    gate = _compute_quality_gate(det, llm)
    assert gate.decision.value == "FAIL"


def test_review_on_major_hallucination():
    """A single major hallucination should trigger REVIEW."""
    det = _make_deterministic()
    llm = _make_llm(hallucinations=[_hallucination("major")])
    gate = _compute_quality_gate(det, llm)
    assert gate.decision.value == "REVIEW"


def test_review_on_low_grounding():
    """Low entity grounding (< 0.7) should trigger REVIEW."""
    det = _make_deterministic(grounding=0.5)
    llm = _make_llm()
    gate = _compute_quality_gate(det, llm)
    assert gate.decision.value == "REVIEW"


def test_review_on_borderline_quality():
    """Quality score of 3/5 should trigger REVIEW."""
    det = _make_deterministic()
    llm = _make_llm(quality=3)
    gate = _compute_quality_gate(det, llm)
    assert gate.decision.value == "REVIEW"


def test_review_on_layer_discrepancy():
    """High grounding + many hallucinations = layer discrepancy = REVIEW."""
    det = _make_deterministic(grounding=0.95)
    llm = _make_llm(hallucinations=[_hallucination("minor")] * 4)
    gate = _compute_quality_gate(det, llm)
    assert gate.decision.value == "REVIEW"
    assert any("discrepancy" in r.lower() for r in gate.reasons)


# ── Scoring Formula Tests ────────────────────────────────────────────────────

def test_perfect_score():
    """Perfect inputs should produce high score."""
    det = _make_deterministic(completeness=1.0, grounding=1.0)
    llm = _make_llm(quality=5)
    # Override section scores to all 5s
    for section in llm.section_scores.values():
        section.completeness = 5
        section.faithfulness = 5
        section.clinical_accuracy = 5

    score = _compute_overall_score(det, llm)
    assert score >= 0.95


def test_hallucination_penalty_reduces_score():
    """Hallucinations should reduce the overall score."""
    det = _make_deterministic()
    llm_clean = _make_llm()
    llm_dirty = _make_llm(hallucinations=[_hallucination("major")] * 2)

    score_clean = _compute_overall_score(det, llm_clean)
    score_dirty = _compute_overall_score(det, llm_dirty)
    assert score_dirty < score_clean


def test_score_bounded_zero_to_one():
    """Score should always be between 0 and 1."""
    det = _make_deterministic(completeness=0.0, grounding=0.0)
    llm = _make_llm(quality=1, hallucinations=[_hallucination("critical")] * 5)
    for section in llm.section_scores.values():
        section.completeness = 1
        section.faithfulness = 1
        section.clinical_accuracy = 1

    score = _compute_overall_score(det, llm)
    assert 0.0 <= score <= 1.0
