"""
Section completeness checker.

Parses a SOAP note to detect which sections (S, O, A, P) are present and
whether they contain meaningful content. This is a fast, deterministic
first-pass - no LLM needed.
"""

import re

from src.models import SectionPresence


# Common section header patterns in SOAP notes
SECTION_PATTERNS = {
    "subjective": [
        r"(?:^|\n)\s*S(?:ubjective)?[\s:.\-]",
        r"(?:^|\n)\s*(?:Chief\s+Complaint|History\s+of\s+Present|HPI|CC)[\s:.\-]",
    ],
    "objective": [
        r"(?:^|\n)\s*O(?:bjective)?[\s:.\-]",
        r"(?:^|\n)\s*(?:Physical\s+Exam|Vital\s+Signs|PE|Vitals)[\s:.\-]",
    ],
    "assessment": [
        r"(?:^|\n)\s*A(?:ssessment)?[\s:.\-]",
        r"(?:^|\n)\s*(?:Diagnosis|Impression|Assessment\s+and\s+Plan)[\s:.\-]",
    ],
    "plan": [
        r"(?:^|\n)\s*P(?:lan)?[\s:.\-]",
        r"(?:^|\n)\s*(?:Treatment\s+Plan|Follow[\s-]?up|Disposition)[\s:.\-]",
    ],
}

# Minimum character count for a section to be considered "present with content"
MIN_SECTION_LENGTH = 15


def parse_soap_sections(note: str) -> dict[str, str]:
    """
    Extract the text content of each SOAP section from a note.
    Returns a dict like {"subjective": "Patient reports...", "objective": "...", ...}
    """
    # Find all section boundaries with end-of-header positions
    # Each entry: (section_name, match_start, content_start)
    boundaries: list[tuple[str, int, int]] = []

    for section_name, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            for match in re.finditer(pattern, note, re.IGNORECASE):
                boundaries.append((section_name, match.start(), match.end()))
                break
            else:
                continue
            break

    if not boundaries:
        # Try S: O: A: P: shorthand
        mapping = {"S": "subjective", "O": "objective", "A": "assessment", "P": "plan"}
        for match in re.finditer(r"(?:^|\n)\s*([SOAP]):", note):
            letter = match.group(1).upper()
            if letter in mapping:
                boundaries.append((mapping[letter], match.start(), match.end()))

    # Sort by position in the note
    boundaries.sort(key=lambda x: x[1])

    # Extract text between boundaries
    sections: dict[str, str] = {}
    for i, (name, _start, content_start) in enumerate(boundaries):
        # Content runs from end of this header to start of next section
        content_end = boundaries[i + 1][1] if i + 1 < len(boundaries) else len(note)
        text = note[content_start:content_end].strip()
        sections[name] = text

    return sections


def check_sections(note: str) -> tuple[SectionPresence, float, dict[str, str]]:
    """
    Check which SOAP sections are present and have meaningful content.

    Returns:
        - SectionPresence: boolean for each section
        - float: completeness score (0-1, fraction of sections present)
        - dict: the parsed section texts (reused by other components)
    """
    sections = parse_soap_sections(note)

    # If "Assessment and Plan" was used as a combined header, the parser finds
    # assessment but not plan. Count the combined section as both present.
    if "assessment" in sections and "plan" not in sections:
        if re.search(r"assessment\s+and\s+plan", note, re.IGNORECASE):
            sections["plan"] = sections["assessment"]

    presence = SectionPresence(
        subjective=len(sections.get("subjective", "")) >= MIN_SECTION_LENGTH,
        objective=len(sections.get("objective", "")) >= MIN_SECTION_LENGTH,
        assessment=len(sections.get("assessment", "")) >= MIN_SECTION_LENGTH,
        plan=len(sections.get("plan", "")) >= MIN_SECTION_LENGTH,
    )

    present_count = sum([
        presence.subjective,
        presence.objective,
        presence.assessment,
        presence.plan,
    ])
    completeness = present_count / 4.0

    return presence, completeness, sections
