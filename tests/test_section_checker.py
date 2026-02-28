"""Tests for SOAP section parsing and completeness checking."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.deterministic.section_checker import parse_soap_sections, check_sections


def test_standard_soap_parsing():
    """Standard SOAP note with full section headers."""
    note = """Subjective: Patient reports headache for 3 days.
Objective: Vitals stable. BP 120/80.
Assessment: Tension headache.
Plan: OTC analgesics, follow up in 2 weeks."""

    sections = parse_soap_sections(note)
    assert "subjective" in sections
    assert "objective" in sections
    assert "assessment" in sections
    assert "plan" in sections
    assert "headache" in sections["subjective"].lower()


def test_abbreviated_soap_headers():
    """S: O: A: P: shorthand format."""
    note = """S: Patient has a cough for 5 days with sore throat.
O: Temp 100.2, oropharynx erythematous.
A: Acute pharyngitis, likely viral.
P: Supportive care, fluids, rest."""

    sections = parse_soap_sections(note)
    assert "subjective" in sections
    assert "objective" in sections
    assert "assessment" in sections
    assert "plan" in sections


def test_combined_assessment_and_plan():
    """Combined 'Assessment and Plan' header should count for both sections."""
    note = """Subjective: Patient reports knee pain.
Objective: Swelling noted in right knee.
Assessment and Plan: Osteoarthritis of right knee. Start physical therapy. NSAIDs as needed."""

    presence, completeness, sections = check_sections(note)
    assert presence.assessment is True
    assert presence.plan is True
    assert completeness == 1.0


def test_missing_section_detected():
    """Missing section should reduce completeness score."""
    note = """Subjective: Patient reports fatigue.
Objective: Vitals unremarkable.
Plan: Lab work ordered."""

    presence, completeness, sections = check_sections(note)
    assert presence.subjective is True
    assert presence.objective is True
    assert presence.assessment is False
    assert presence.plan is True
    assert completeness == 0.75


def test_empty_note():
    """Empty note should have 0 completeness."""
    presence, completeness, sections = check_sections("")
    assert completeness == 0.0
    assert presence.subjective is False


def test_short_section_not_counted():
    """Section with too little content (< 15 chars) should not count."""
    note = """Subjective: OK.
Objective: Patient appears well with no acute distress.
Assessment: Healthy.
Plan: Return as needed for follow-up visits."""

    presence, completeness, sections = check_sections(note)
    assert presence.subjective is False  # "OK." is too short
    assert presence.objective is True
    assert presence.assessment is False  # "Healthy." is too short
    assert presence.plan is True
