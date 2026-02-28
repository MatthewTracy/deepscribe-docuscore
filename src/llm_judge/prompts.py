"""
Evaluation prompts for the LLM judge.

These prompts are carefully designed to produce structured, evidence-grounded
evaluations. The key design decisions:

1. Section-by-section evaluation (not holistic) - more granular, more actionable
2. Every finding requires a transcript citation - auditable, not just vibes
3. Hallucination taxonomy adapted from CREOLA framework (Nature npj Digital Medicine) - we use temporal instead of CREOLA's causality category
4. Severity levels tied to clinical impact, not just factual accuracy
"""

SYSTEM_PROMPT = """You are a clinical documentation quality evaluator. Your job is to compare a SOAP note against its source transcript and identify quality issues.

You must be precise and evidence-based. Every finding you report MUST include a specific quote from the transcript or note. Do not speculate - only flag issues you can prove from the text.

Severity levels:
- critical: Could cause patient harm (wrong medication, wrong diagnosis, wrong allergy)
- major: Clinically significant but not immediately dangerous (missing key history, wrong dosage detail)
- minor: Documentation quality issue but unlikely to affect care (formatting, minor omission)"""


EVALUATION_PROMPT = """Evaluate this SOAP note against its source transcript.

## Source Transcript
{transcript}

## SOAP Note to Evaluate
{soap_note}

## Instructions

Evaluate the note in three parts:

### Part 1: Section-by-Section Scoring
For each SOAP section (Subjective, Objective, Assessment, Plan), score:
- **completeness** (1-5): How much relevant information from the transcript is captured?
- **faithfulness** (1-5): Does the note accurately reflect what was said? No additions or distortions?
- **clinical_accuracy** (1-5): Is the medical terminology and reasoning correct?

Provide brief reasoning for each section's scores.

### Part 2: Hallucinations
List any information in the note that is NOT supported by the transcript:
- **fabrication**: Information that was never mentioned in the transcript
- **negation**: The opposite of what the transcript says
- **contextual**: Information that distorts the context (e.g., wrong timing, wrong body part)
- **temporal**: Wrong timing or sequence of events

For each hallucination, provide:
- The exact text from the note
- What the transcript actually says (or "not mentioned in transcript")
- Severity (critical/major/minor)

### Part 3: Omissions
List clinically relevant information from the transcript that is MISSING from the note:
- The exact relevant text from the transcript
- Which SOAP section should contain it
- Clinical importance (critical/major/minor)

Respond in this exact JSON format:
{{
    "section_scores": {{
        "subjective": {{
            "completeness": <1-5>,
            "faithfulness": <1-5>,
            "clinical_accuracy": <1-5>,
            "reasoning": "<brief justification>"
        }},
        "objective": {{
            "completeness": <1-5>,
            "faithfulness": <1-5>,
            "clinical_accuracy": <1-5>,
            "reasoning": "<brief justification>"
        }},
        "assessment": {{
            "completeness": <1-5>,
            "faithfulness": <1-5>,
            "clinical_accuracy": <1-5>,
            "reasoning": "<brief justification>"
        }},
        "plan": {{
            "completeness": <1-5>,
            "faithfulness": <1-5>,
            "clinical_accuracy": <1-5>,
            "reasoning": "<brief justification>"
        }}
    }},
    "hallucinations": [
        {{
            "note_text": "<exact quote from note>",
            "hallucination_type": "fabrication|negation|contextual|temporal",
            "severity": "critical|major|minor",
            "explanation": "<why this is a hallucination>",
            "transcript_context": "<what the transcript actually says, or 'not mentioned in transcript'>"
        }}
    ],
    "omissions": [
        {{
            "transcript_text": "<exact quote from transcript>",
            "expected_section": "subjective|objective|assessment|plan",
            "clinical_importance": "critical|major|minor",
            "explanation": "<why this matters clinically>"
        }}
    ],
    "overall_quality": <1-5>,
    "overall_reasoning": "<2-3 sentence summary>"
}}"""
