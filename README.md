# DocuScore: Clinical Documentation Quality Evaluation Platform

> After reviewing DeepScribe's published research ([DeepScore](https://arxiv.org/abs/2409.16307), HEAL, and the [oncology documentation study](https://www.hmpgloballearningnetwork.com/site/jcp/abstracts/enhancing-oncology-documentation-and-diagnosis-capture-integrated-ai-scribe)), I built this evaluation suite to address the specific gaps these papers acknowledge: no automated hallucination detection, manual-only evaluation, and no evaluator reliability validation.
>
> Most evaluation frameworks answer: *"Is this note accurate?"*
> This system also answers: *"Can you trust the system that made that judgment?"*

**[Live Demo: docuscore.vercel.app](https://docuscore.vercel.app)** - Interactive dashboard with all 100 evaluated notes, drill-down findings, and meta-evaluation results.

---

## Results at a Glance

100 clinical notes evaluated against source transcripts:

| Metric | Value |
|--------|-------|
| Average quality score | 79.6% |
| Quality gate: PASS | 12 notes |
| Quality gate: REVIEW | 83 notes |
| Quality gate: FAIL | 5 notes |
| Hallucinations detected | 322 (75% fabrication, 22% contextual, 2% temporal, 1% negation) |
| Omissions detected | 513 |
| Meta-eval: Judge validation | 15/15 on synthetic test cases (6 hallucination + 6 omission + 3 clean controls) |

---

## What This System Does

DocuScore is a two-layer evaluation pipeline that takes clinical transcripts and AI-generated SOAP notes, then produces:

1. **Quality evaluation**: hallucination detection, omission detection, section-by-section scoring with evidence citations
2. **Reliability measurement**: meta-evaluation proving the evaluator itself is trustworthy

The output is an interactive React dashboard where you can explore every finding, drill into individual notes with side-by-side transcript/note views, and understand aggregate patterns.

### How This Addresses DeepScribe's Goals

**Goal 1: Move fast.** The pipeline is fully automated. Run `python scripts/run_eval.py` on any model's output and get structured results in ~50 minutes for 100 notes. The deterministic layer is instant and free; the LLM judge adds ~$0.02/note. Auto-resume on interruption means partial runs aren't wasted. This plugs directly into CI/CD for regression testing on model updates or PR changes.

**Goal 2: Understand production quality.** The three-tier quality gate (PASS/REVIEW/FAIL) maps directly to production routing: PASS auto-pushes to EHR, REVIEW queues for human audit, FAIL blocks. The dashboard surfaces aggregate patterns (hallucination type distributions, score breakdowns, per-section quality) so quality trends are visible across the full note population. Meta-evaluation proves the evaluator itself is reliable, so you can trust the signals it produces.

### Architecture

```
  Clinical Transcript + SOAP Note
              │
  ┌───────────▼─────────────────────────────────┐
  │  Layer 1: Deterministic Checks    [FREE]     │
  │  • SOAP section completeness                 │
  │  • Entity grounding (note → transcript)      │
  │  • Negation contradiction detection          │
  └───────────┬─────────────────────────────────┘
              │
  ┌───────────▼─────────────────────────────────┐
  │  Layer 2: LLM Judge (Claude Sonnet 4.6)      │
  │  • Section-by-section scoring (1-5)          │
  │    - Completeness, faithfulness, accuracy    │
  │  • Hallucination taxonomy (adapted CREOLA)    │
  │    - Fabrication | Negation | Contextual |  │
  │      Temporal                               │
  │    - Each with severity + transcript cite    │
  │  • Omission detection with clinical impact   │
  └───────────┬─────────────────────────────────┘
              │
  ┌───────────▼─────────────────────────────────┐
  │  Quality Gate: PASS / REVIEW / FAIL          │
  │  FAIL:                                       │
  │  • Critical hallucination                    │
  │  • Missing SOAP section (<75% complete)      │
  │  • Very low quality (<=2/5)                  │
  │  • 3+ major hallucinations                   │
  │  REVIEW:                                     │
  │  • Major hallucination present               │
  │  • Low entity grounding (<70%)               │
  │  • Negation contradictions found             │
  │  • Borderline quality (3/5)                  │
  │  • Layer discrepancy (high grounding but     │
  │    many LLM-flagged hallucinations)          │
  │  PASS: All checks clean                      │
  └───────────┬─────────────────────────────────┘
              │
  ┌───────────▼─────────────────────────────────┐
  │  Meta-Evaluation (Judge Validation Suite)    │
  │  • 15 synthetic test cases with known errors │
  │    - 6 halluc + 6 omission + 3 clean control│
  │  • Sensitivity: does it catch real errors?   │
  │  • Specificity: does it avoid false alarms?  │
  └─────────────────────────────────────────────┘
```

### Scoring Formula

```
overall_score = 0.15 × section_completeness
              + 0.15 × entity_grounding_rate
              + 0.50 × avg_llm_section_scores (normalized 1-5 → 0-1)
              + 0.20 × (1 - hallucination_penalty)

where hallucination_penalty = min(1.0, critical×0.3 + major×0.15 + minor×0.05)
```

---

## The Dashboard

The frontend is a Next.js app deployed on Vercel.

**Dashboard**: Aggregate quality overview with score distributions, gate breakdown, hallucination type breakdown, and meta-evaluation results.

**Note Explorer**: Per-note deep dive:
- Side-by-side transcript/note view with section highlighting
- Quick stats bar (overall score, completeness, grounding, hallucination/omission counts)
- Action Items tab that transforms findings into a checklist: Remove (fabricated content), Revise (distorted content), Add (missing content), sorted by clinical severity
- Hallucinations tab with evidence citations
- Omissions tab with expected sections
- Section scores with reasoning

---

## Addressing Gaps in DeepScribe's Published Research

DeepScore ([Oleson, 2024](https://arxiv.org/abs/2409.16307)) established entity-level quality metrics for AI-generated clinical notes (96.2% Accurate Entity Rate, 100% Critical Defect-Free Rate). However:

- **No automated hallucination detection.** DeepScore identifies entity-level defects but doesn't classify hallucination types or provide explanations.
- **Manual evaluation only.** Relies on human scribes and auditors, limiting scalability.
- **No evaluator reliability validation.** A gap the paper explicitly acknowledges.

Separately, DeepScribe's [oncology study](https://www.hmpgloballearningnetwork.com/site/jcp/abstracts/enhancing-oncology-documentation-and-diagnosis-capture-integrated-ai-scribe) (2025) showed a 17% increase in ICD-10 codes captured, but notes: *"The accuracy of the AI-generated notes was not explicitly evaluated."*

DocuScore addresses these gaps.

---

## Craftsmanship Highlights

### 1. Evidence-Grounded Evaluation

Every hallucination flag and omission alert includes specific citations from the source transcript. The evaluation is auditable: a clinician can verify any finding by checking the cited text.

### 2. Layered Architecture: Cheap Checks First

The deterministic layer catches structural issues (missing sections, ungrounded entities, negation contradictions) before making any LLM API calls. Entity extraction uses scispacy (`en_core_sci_md`) for biomedical NER, with a medical synonym dictionary (~200 entries) so "HTN" in the note matches "hypertension" in the transcript.

- **Layer 1** (deterministic): Free, instant, catches structural issues
- **Layer 2** (LLM judge): ~$0.02/note, catches nuanced quality issues

Cross-validation between layers catches blind spots: if deterministic grounding is high (>85%) but the LLM finds 3+ hallucinations, the quality gate flags the discrepancy for review.

### 3. Meta-Evaluation: Proving the Evaluator Works

DocuScore evaluates the evaluator with a judge validation suite of 15 synthetic test cases with known errors:

- **6 hallucination tests**: fabricated medications, negation reversal, wrong dosages (10x error), fabricated family history, temporal distortion, contextual distortion (well-controlled reported as "poorly controlled")
- **6 omission tests**: critical allergy (anaphylaxis), vision changes, surgical history, medication (warfarin interaction), social history (alcohol use), red flag symptom (cauda equina)
- **3 clean-note controls**: accurate notes (sore throat, diabetes follow-up, hypertension follow-up) that should NOT trigger false alarms. These test specificity, not just sensitivity. A judge that flags everything would score 12/15 on detection but fail the controls.

---

## Technical Decisions & Tradeoffs

| Decision | Choice | Why |
|----------|--------|-----|
| **LLM for judge** | Claude Sonnet 4.6 | Cost discipline: ~$0.02/note vs ~$0.10 with Opus. Sufficient quality for structured eval. |
| **Hallucination taxonomy** | Adapted from CREOLA (4 types) | Adapted from the CREOLA framework (Nature npj Digital Medicine). We use fabrication, negation, contextual, and temporal (CREOLA uses causality instead of temporal). Each type requires different remediation. |
| **Scoring** | Section-level, not holistic | "Your Plan section scores 2/5 on faithfulness" is more useful than "overall score: 0.74". |
| **Quality gate** | Three-tier (PASS/REVIEW/FAIL) | Maps to production workflow: PASS auto-pushes to EHR, REVIEW queues for humans, FAIL blocks. |
| **Frontend** | Next.js on Vercel | Professional presentation, always available for review. |
| **Dataset** | omi-health/medical-dialogue-to-soap-summary (100 notes) | Realistic clinical dialogue-to-SOAP pairs. ~$5 API cost for full pipeline. |

### Reference-Based vs Non-Reference-Based

DocuScore uses **non-reference-based evaluation** - the note is evaluated directly against the source transcript, not against a clinician-edited gold standard. This scales to production: the transcript already exists, no clinician needs to write a reference note for every encounter.

The tradeoff: reference-based evaluation catches formatting conventions and clinical phrasing norms that transcript-based evaluation misses. It's better suited for regression testing on a small curated test set. The ideal system uses both - DocuScore's `NoteInput` already has a `reference_note` field for this.

### Honest Limitations

**No clinician ground truth.** The LLM judge has not been validated against clinician ratings. The scoring weights (15/15/50/20) and quality gate thresholds are informed by clinical reasoning but not empirically calibrated. In production, we'd run a clinician calibration study and tune weights to maximize correlation with human judgment. (See backlog: clinician validation, scoring weight sensitivity analysis.)

**Meta-eval is a proof-of-concept.** 15 synthetic test cases demonstrate the methodology but are statistically underpowered for strong confidence intervals. The test cases are also generic (not specialty-specific). Production would need 100+ tests spanning oncology, primary care, ED, and inpatient scenarios. (See backlog: expand meta-eval suite.)

**LLM scoring variance.** The evaluation prompt defines severity tiers and scoring rubrics but doesn't include annotated examples. Without few-shot anchoring, Claude's section scores (1-5) can vary across similar notes. (See backlog: few-shot examples in LLM prompt.)

**Dataset notes are AI-generated.** The omi-health dataset has real quality variation but may not capture the specific error patterns of DeepScribe's models.

---

## Running the Pipeline

### Prerequisites

```bash
# Python 3.11+
pip install -r requirements.txt
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Quick Start

```bash
# Download dataset (100 clinical notes)
python scripts/download_data.py

# Quick test: 5 notes, no meta-eval, ~2 minutes
python scripts/run_eval.py --quick

# Full evaluation: 100 notes + meta-eval, ~50 minutes, ~$5 API cost
python scripts/run_eval.py

# Results are in output/results.json
```

### Frontend

```bash
# Copy results to frontend
cp output/results.json frontend/public/data/
cp output/notes.json frontend/public/data/

# Run locally
cd frontend && npm install && npm run dev
```

Or visit the live deployment: [docuscore.vercel.app](https://docuscore.vercel.app)

---

## Project Structure

```
deepscribe-docuscore/
├── README.md
├── requirements.txt
├── .env                          # API key (gitignored)
├── src/
│   ├── models.py                 # Pydantic data models (shared schema)
│   ├── pipeline.py               # Pipeline orchestrator
│   ├── rate_limiter.py           # API rate limiting
│   ├── deterministic/
│   │   ├── checks.py             # Main deterministic runner
│   │   ├── section_checker.py    # SOAP section parsing + completeness
│   │   └── entity_grounding.py   # Entity-to-transcript verification (scispacy NER)
│   ├── llm_judge/
│   │   ├── judge.py              # Claude evaluation engine
│   │   └── prompts.py            # Evaluation prompts (adapted from CREOLA)
│   ├── meta_eval/
│   │   └── consistency.py        # Judge validation suite (15 synthetic test cases)
│   └── coding/                   # Exploratory, not integrated
│       ├── analyzer.py           # ICD-10 coding gap analysis
│       ├── icd_data.py           # ICD-10 code definitions
│       └── icd_index.py          # Code lookup utilities
├── scripts/
│   ├── download_data.py          # Dataset download from Hugging Face
│   ├── run_eval.py               # Pipeline runner (auto-resumes from partial results)
│   └── test_single.py            # Single-note test
├── frontend/                     # Next.js React dashboard
│   ├── app/
│   │   ├── page.tsx              # Dashboard overview
│   │   └── notes/                # Note Explorer (list + detail views)
│   ├── components/               # Shared UI components (Navbar, StatCard, etc.)
│   ├── lib/                      # Types, data hooks, utilities
│   └── public/data/              # Pre-computed results (bundled with deploy)
├── tests/
│   ├── test_section_checker.py   # SOAP parsing tests
│   ├── test_quality_gate.py      # Quality gate + scoring tests
│   └── test_meta_eval.py         # Meta-eval structure validation
├── data/
│   └── raw/sample_100.json       # Downloaded dataset
└── output/
    ├── results.json              # Full evaluation results
    ├── notes.json                # Raw transcript + note data
    └── summary.json              # Aggregate statistics
```

---

## Backlog of Ideas & Improvements

- Clinician validation: have clinicians rate a stratified sample of 50 notes, measure Cohen's kappa between human and LLM judge scores to calibrate the system, including validating that Claude's severity labels (critical/major/minor) match clinician assessments since these directly drive the hallucination penalty
- Scoring weight sensitivity analysis: vary weights across +/-20%, measure correlation with clinician satisfaction, optimize empirically
- Expand meta-eval to 100+ synthetic tests across specialties (oncology staging/tumor markers, emergency medicine, surgical cases), with separate sensitivity/specificity per hallucination type
- NLI-based faithfulness checking: use natural language inference to verify each note sentence is entailed by the transcript, catching semantic contradictions that entity grounding misses (upgrades Layer 1 from word-matching to meaning-matching)
- Few-shot examples in LLM prompt: provide annotated transcript/note pairs to anchor Claude's scoring rubric and reduce variance
- Multi-model inter-rater reliability: run multiple LLM judges (Claude, GPT, Gemini) and measure agreement via Fleiss' kappa
- Omission penalty in scoring formula: add explicit penalty term for critical/major omissions, calibrated against clinician judgment on omission severity
- Negation-aware entity grounding: integrate negation context into grounding checks so negated entities (e.g., "denies chest pain") are not counted as grounded when affirmed in the note
- UMLS entity linking to replace the manual synonym dictionary
- Cross-note pattern detection (e.g., "model consistently omits allergy info")
- Specialty-specific eval rubrics (oncology vs primary care vs surgery)
- CI/CD regression testing: run on held-out test set before/after model updates
- Coding gap analysis (exploratory): connect documentation quality to missed/incorrect ICD-10 codes against ground-truth charts; initial work completed but not integrated pending further data
- Reference-based evaluation: compare against clinician-edited gold standard notes
---

*Built for the DeepScribe AI Engineer coding challenge*
*Evaluation dataset: [omi-health/medical-dialogue-to-soap-summary](https://huggingface.co/datasets/omi-health/medical-dialogue-to-soap-summary)*
