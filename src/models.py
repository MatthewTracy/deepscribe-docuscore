"""
Pydantic data models for the evaluation pipeline.

Every component (deterministic checks, LLM judge, coding engine, meta-eval)
produces typed output conforming to these models. The final EvalReport is what
gets serialized to results.json and consumed by the frontend.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class NoteInput(BaseModel):
    """A single transcript + SOAP note pair to evaluate."""
    note_id: str
    transcript: str
    soap_note: str
    reference_note: str | None = None  # for reference-based eval (not used in current pipeline)


# ---------------------------------------------------------------------------
# Deterministic layer
# ---------------------------------------------------------------------------

class SectionPresence(BaseModel):
    """Whether each SOAP section exists and has content."""
    subjective: bool = False
    objective: bool = False
    assessment: bool = False
    plan: bool = False

class EntityGroundingResult(BaseModel):
    """A single entity checked against the transcript."""
    entity: str
    found_in_transcript: bool
    transcript_evidence: str | None = None  # exact quote from transcript

class ContradictionResult(BaseModel):
    """A contradiction between the note and transcript."""
    note_claim: str
    transcript_evidence: str
    description: str

class DeterministicResult(BaseModel):
    """Output from all deterministic checks."""
    sections_present: SectionPresence
    section_completeness_score: float = Field(ge=0, le=1)
    entities_checked: list[EntityGroundingResult] = []
    entity_grounding_rate: float = Field(ge=0, le=1, default=0.0)
    contradictions: list[ContradictionResult] = []


# ---------------------------------------------------------------------------
# LLM judge layer
# ---------------------------------------------------------------------------

class SectionScore(BaseModel):
    """LLM judge scores for a single SOAP section."""
    completeness: int = Field(ge=1, le=5, description="1-5: How much relevant transcript info is captured")
    faithfulness: int = Field(ge=1, le=5, description="1-5: How accurately it reflects the transcript")
    clinical_accuracy: int = Field(ge=1, le=5, description="1-5: Medical correctness and terminology")
    reasoning: str = Field(description="Brief justification for scores")

class HallucinationType(str, Enum):
    FABRICATION = "fabrication"        # information not in transcript at all
    NEGATION = "negation"              # opposite of what transcript says
    CONTEXTUAL = "contextual"          # distortion of context/specifics
    TEMPORAL = "temporal"              # wrong timing/sequence

class Hallucination(BaseModel):
    """A single hallucinated claim in the note."""
    note_text: str = Field(description="The hallucinated text from the note")
    hallucination_type: HallucinationType
    severity: str = Field(description="critical | major | minor")
    explanation: str
    transcript_context: str = Field(description="What the transcript actually says (or 'not mentioned')")

class Omission(BaseModel):
    """A clinically relevant finding in the transcript missing from the note."""
    transcript_text: str = Field(description="The relevant quote from the transcript")
    expected_section: str = Field(description="Which SOAP section should contain this")
    clinical_importance: str = Field(description="critical | major | minor")
    explanation: str

class LLMJudgeResult(BaseModel):
    """Output from the LLM judge evaluation."""
    section_scores: dict[str, SectionScore] = Field(
        description="Scores keyed by section: subjective, objective, assessment, plan"
    )
    hallucinations: list[Hallucination] = []
    omissions: list[Omission] = []
    overall_quality: int = Field(ge=1, le=5, description="1-5 overall note quality")
    overall_reasoning: str = Field(description="Summary of quality assessment")


# ---------------------------------------------------------------------------
# Coding intelligence layer (exploratory - not integrated into core pipeline)
# Coding gap analysis: connect documentation quality to missed/incorrect ICD-10
# codes against ground-truth charts; initial work completed but not integrated
# pending further data.
# ---------------------------------------------------------------------------

class SupportedCode(BaseModel):
    """An ICD-10 code supported by the documentation."""
    icd10_code: str
    description: str
    evidence_source: str = Field(description="transcript | note | both")
    evidence_text: str = Field(description="Quote supporting this code")
    hcc_category: str | None = None
    hcc_description: str | None = None

class CodingGap(BaseModel):
    """A diagnosis in the transcript not coded to full specificity in the note."""
    transcript_evidence: str = Field(description="What the transcript says")
    current_note_text: str = Field(description="What the note says (or 'not mentioned')")
    current_code: str | None = Field(description="The less-specific code the note supports")
    suggested_code: str = Field(description="The more specific code the transcript supports")
    suggested_description: str
    hcc_category: str | None = None
    estimated_annual_value: float | None = Field(
        description="Estimated annual RAF value in dollars", default=None
    )
    documentation_suggestion: str = Field(
        description="Specific text the note should include to support the code"
    )

class CodingResult(BaseModel):
    """Output from coding intelligence analysis."""
    supported_codes: list[SupportedCode] = []
    coding_gaps: list[CodingGap] = []
    total_gap_count: int = 0
    total_estimated_revenue_impact: float = 0.0


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------

class QualityGate(str, Enum):
    PASS = "PASS"       # note is safe to push to EHR
    REVIEW = "REVIEW"   # note needs human review
    FAIL = "FAIL"       # note has critical issues, block from EHR

class QualityGateResult(BaseModel):
    """Quality gate decision with reasoning."""
    decision: QualityGate
    reasons: list[str]


# ---------------------------------------------------------------------------
# Combined evaluation report (per note)
# ---------------------------------------------------------------------------

class EvalReport(BaseModel):
    """Complete evaluation for a single note. This is the core output."""
    note_id: str
    quality_gate: QualityGateResult
    overall_score: float = Field(ge=0, le=1)
    deterministic: DeterministicResult
    llm_judge: LLMJudgeResult
    coding: CodingResult


# ---------------------------------------------------------------------------
# Meta-evaluation
# ---------------------------------------------------------------------------

class MetaEvalResult(BaseModel):
    """Results from evaluating the evaluator's reliability."""
    injected_error_detection_rate: float = Field(
        ge=0, le=1,
        description="Fraction of deliberately injected errors caught"
    )
    injected_errors_total: int
    injected_errors_caught: int
    details: list[str] = Field(
        description="Per-test details for transparency"
    )


# ---------------------------------------------------------------------------
# Batch / aggregate report
# ---------------------------------------------------------------------------

class BatchReport(BaseModel):
    """Aggregate report across all evaluated notes."""
    total_notes: int
    reports: list[EvalReport]
    meta_eval: MetaEvalResult | None = None

    # Aggregate stats (computed after all notes evaluated)
    avg_overall_score: float = 0.0
    gate_distribution: dict[str, int] = Field(default_factory=dict)
    total_hallucinations: int = 0
    total_omissions: int = 0
    total_coding_gaps: int = 0
    total_estimated_revenue_impact: float = 0.0
    most_common_hallucination_types: dict[str, int] = Field(default_factory=dict)
    most_common_gap_codes: list[dict] = Field(default_factory=list)
