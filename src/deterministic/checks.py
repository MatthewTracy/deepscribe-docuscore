"""
Main deterministic checks module.

Orchestrates all deterministic (non-LLM) quality checks:
1. Section completeness
2. Entity grounding
3. Basic contradiction detection (negation patterns)

These run FIRST in the pipeline - they're fast, free, and catch obvious issues
before we spend money on LLM calls.
"""

import re

from src.models import ContradictionResult, DeterministicResult
from src.deterministic.section_checker import check_sections
from src.deterministic.entity_grounding import check_entity_grounding


def detect_negation_contradictions(
    note: str, transcript: str
) -> list[ContradictionResult]:
    """
    Detect cases where the note says 'denies X' but the transcript says
    'reports X' (or vice versa). This catches a common hallucination pattern.
    """
    contradictions = []

    # Extract denied symptoms from the note
    note_denials = re.findall(
        r"(?:denies|denied|no)\s+([\w\s]+?)(?:\.|,|;|$)",
        note,
        re.IGNORECASE,
    )

    # Extract reported symptoms from the transcript
    transcript_reports = re.findall(
        r"(?:I\s+have|I've\s+been\s+having|I\s+(?:feel|notice|experience)(?:d)?|"
        r"yes.*?I\s+(?:do|have|am))\s+([\w\s]+?)(?:\.|,|;|\?|$)",
        transcript,
        re.IGNORECASE,
    )

    # Normalize for comparison
    def normalize(s: str) -> set[str]:
        words = set(re.sub(r"[^\w\s]", "", s.lower()).split())
        # Filter out stop words
        stop = {"a", "an", "the", "and", "or", "i", "my", "is", "was", "been", "have", "has", "some", "any"}
        return words - stop

    for denial in note_denials:
        denial_terms = normalize(denial)
        if len(denial_terms) < 1:
            continue

        for report in transcript_reports:
            report_terms = normalize(report)
            # Check for significant overlap
            overlap = denial_terms & report_terms
            if len(overlap) >= max(1, len(denial_terms) * 0.5):
                contradictions.append(ContradictionResult(
                    note_claim=f"Note states denial of: {denial.strip()}",
                    transcript_evidence=f"Patient reports: {report.strip()}",
                    description=f"Note denies '{denial.strip()}' but transcript indicates patient reports it. Overlapping terms: {', '.join(overlap)}",
                ))
                break  # one match per denial is enough

    return contradictions


def run_deterministic_checks(
    note: str, transcript: str
) -> tuple[DeterministicResult, dict[str, str]]:
    """
    Run all deterministic checks on a note.

    Returns:
        - DeterministicResult with all findings
        - dict of parsed section texts (reused by LLM judge)
    """
    # 1. Section completeness
    presence, completeness, sections = check_sections(note)

    # 2. Entity grounding
    entity_results, grounding_rate = check_entity_grounding(note, transcript)

    # 3. Negation contradictions
    contradictions = detect_negation_contradictions(note, transcript)

    result = DeterministicResult(
        sections_present=presence,
        section_completeness_score=completeness,
        entities_checked=entity_results,
        entity_grounding_rate=grounding_rate,
        contradictions=contradictions,
    )

    return result, sections
