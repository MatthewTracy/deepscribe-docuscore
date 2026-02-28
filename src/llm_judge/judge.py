"""
LLM Judge - uses Claude to evaluate clinical note quality.

Design decisions:
- Uses Claude Sonnet 4.6 for cost efficiency (vs Opus for eval tasks)
- Structured JSON output with retry on parse failure
- Temperature 0 for reproducibility
- Each note evaluated independently (no cross-note context leaking)
"""

import json

import anthropic

from src.rate_limiter import wait_for_rate_limit
from src.models import (
    Hallucination,
    HallucinationType,
    LLMJudgeResult,
    Omission,
    SectionScore,
)
from src.llm_judge.prompts import EVALUATION_PROMPT, SYSTEM_PROMPT


# Map string types to enum
HALLUCINATION_TYPE_MAP = {
    "fabrication": HallucinationType.FABRICATION,
    "negation": HallucinationType.NEGATION,
    "contextual": HallucinationType.CONTEXTUAL,
    "temporal": HallucinationType.TEMPORAL,
}


def _parse_judge_response(response_text: str) -> dict:
    """Extract JSON from the LLM response, handling markdown code blocks."""
    text = response_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        first_newline = text.index("\n")
        last_fence = text.rfind("```")
        if last_fence > first_newline:
            text = text[first_newline + 1:last_fence]

    return json.loads(text)


def _build_result(data: dict) -> LLMJudgeResult:
    """Convert raw JSON dict into typed LLMJudgeResult."""
    section_scores = {}
    for section_name, scores in data.get("section_scores", {}).items():
        section_scores[section_name] = SectionScore(
            completeness=scores["completeness"],
            faithfulness=scores["faithfulness"],
            clinical_accuracy=scores["clinical_accuracy"],
            reasoning=scores.get("reasoning", ""),
        )

    hallucinations = []
    for h in data.get("hallucinations", []):
        h_type = HALLUCINATION_TYPE_MAP.get(
            h.get("hallucination_type", "fabrication"),
            HallucinationType.FABRICATION,
        )
        hallucinations.append(Hallucination(
            note_text=h["note_text"],
            hallucination_type=h_type,
            severity=h.get("severity", "minor"),
            explanation=h.get("explanation", ""),
            transcript_context=h.get("transcript_context", "not mentioned"),
        ))

    omissions = []
    for o in data.get("omissions", []):
        omissions.append(Omission(
            transcript_text=o["transcript_text"],
            expected_section=o.get("expected_section", "subjective"),
            clinical_importance=o.get("clinical_importance", "minor"),
            explanation=o.get("explanation", ""),
        ))

    return LLMJudgeResult(
        section_scores=section_scores,
        hallucinations=hallucinations,
        omissions=omissions,
        overall_quality=data.get("overall_quality", 3),
        overall_reasoning=data.get("overall_reasoning", ""),
    )


def evaluate_note(
    transcript: str,
    soap_note: str,
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.0,
    max_retries: int = 2,
) -> LLMJudgeResult:
    """
    Evaluate a single SOAP note against its transcript using Claude.

    Args:
        transcript: The source clinical dialogue
        soap_note: The SOAP note to evaluate
        model: Claude model ID
        temperature: 0 for reproducibility
        max_retries: Retry count on parse failure

    Returns:
        LLMJudgeResult with section scores, hallucinations, and omissions
    """
    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var

    prompt = EVALUATION_PROMPT.format(
        transcript=transcript,
        soap_note=soap_note,
    )

    retry_suffix = "\n\nIMPORTANT: You must respond with valid JSON only. No text before or after the JSON object."

    last_error = None
    for attempt in range(max_retries + 1):
        current_prompt = prompt if attempt == 0 else prompt + retry_suffix
        wait_for_rate_limit()
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": current_prompt}],
        )

        response_text = response.content[0].text

        try:
            data = _parse_judge_response(response_text)
            return _build_result(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            last_error = e
            continue

    # If all retries fail, return a minimal result
    raise RuntimeError(
        f"LLM judge failed to produce valid JSON after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )
