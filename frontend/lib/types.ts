// ── Deterministic evaluation types ──────────────────────────────────────────

export interface SectionPresence {
  subjective: boolean;
  objective: boolean;
  assessment: boolean;
  plan: boolean;
}

export interface EntityGroundingResult {
  entity: string;
  found_in_transcript: boolean;
  transcript_evidence: string | null;
}

export interface ContradictionResult {
  note_claim: string;
  transcript_evidence: string;
  description: string;
}

export interface DeterministicResult {
  sections_present: SectionPresence;
  section_completeness_score: number;
  entities_checked: EntityGroundingResult[];
  entity_grounding_rate: number;
  contradictions: ContradictionResult[];
}

// ── LLM Judge types ─────────────────────────────────────────────────────────

export interface SectionScore {
  completeness: number;
  faithfulness: number;
  clinical_accuracy: number;
  reasoning: string;
}

export interface Hallucination {
  note_text: string;
  hallucination_type: "fabrication" | "negation" | "contextual" | "temporal";
  severity: "critical" | "major" | "minor";
  explanation: string;
  transcript_context: string;
}

export interface Omission {
  transcript_text: string;
  expected_section: string;
  clinical_importance: "critical" | "major" | "minor";
  explanation: string;
}

export interface LLMJudgeResult {
  section_scores: Record<string, SectionScore>;
  hallucinations: Hallucination[];
  omissions: Omission[];
  overall_quality: number;
  overall_reasoning: string;
}

// ── Quality gate ────────────────────────────────────────────────────────────

export interface QualityGateResult {
  decision: "PASS" | "REVIEW" | "FAIL";
  reasons: string[];
}

// ── Per-note report ─────────────────────────────────────────────────────────

export interface EvalReport {
  note_id: string;
  quality_gate: QualityGateResult;
  overall_score: number;
  deterministic: DeterministicResult;
  llm_judge: LLMJudgeResult;
}

// ── Meta-eval ───────────────────────────────────────────────────────────────

export interface MetaEvalResult {
  injected_error_detection_rate: number;
  injected_errors_total: number;
  injected_errors_caught: number;
  details: string[];
}

// ── Batch report (results.json) ─────────────────────────────────────────────

export interface BatchReport {
  total_notes: number;
  reports: EvalReport[];
  meta_eval: MetaEvalResult | null;
  avg_overall_score: number;
  gate_distribution: Record<string, number>;
  total_hallucinations: number;
  total_omissions: number;
  most_common_hallucination_types: Record<string, number>;
}

// ── Notes data (notes.json) ─────────────────────────────────────────────────

export interface NoteData {
  note_id: string;
  transcript: string;
  soap_note: string;
}
