"""Tests for meta-evaluation test case structure and coverage."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.meta_eval.consistency import INJECTED_ERROR_TESTS


def test_correct_test_count():
    """Should have exactly 15 test cases."""
    assert len(INJECTED_ERROR_TESTS) == 15


def test_hallucination_cases():
    """Should have 6 hallucination test cases."""
    h_cases = [t for t in INJECTED_ERROR_TESTS if t["expected_finding"] == "hallucination"]
    assert len(h_cases) == 6


def test_omission_cases():
    """Should have 6 omission test cases."""
    o_cases = [t for t in INJECTED_ERROR_TESTS if t["expected_finding"] == "omission"]
    assert len(o_cases) == 6


def test_clean_controls():
    """Should have exactly 3 clean-note control cases."""
    controls = [t for t in INJECTED_ERROR_TESTS if t["expected_finding"] == "none"]
    assert len(controls) == 3


def test_all_cases_have_required_fields():
    """Every test case must have all required fields."""
    required = {"name", "transcript", "soap_note", "expected_finding", "expected_text", "description"}
    for test in INJECTED_ERROR_TESTS:
        missing = required - set(test.keys())
        assert not missing, f"Test '{test.get('name', '?')}' missing fields: {missing}"


def test_unique_test_names():
    """All test case names should be unique."""
    names = [t["name"] for t in INJECTED_ERROR_TESTS]
    assert len(names) == len(set(names))


def test_error_cases_have_expected_text():
    """Non-control cases must have non-empty expected_text."""
    for test in INJECTED_ERROR_TESTS:
        if test["expected_finding"] != "none":
            assert test["expected_text"], f"Test '{test['name']}' has empty expected_text"


def test_injected_errors_present_in_notes():
    """For hallucination cases, the fabricated content should actually be in the SOAP note."""
    for test in INJECTED_ERROR_TESTS:
        if test["expected_finding"] == "hallucination":
            assert test["expected_text"].lower() in test["soap_note"].lower(), (
                f"Test '{test['name']}': expected text '{test['expected_text']}' "
                f"not found in SOAP note"
            )


def test_omitted_content_in_transcript():
    """For omission cases, the expected content should be in the transcript."""
    for test in INJECTED_ERROR_TESTS:
        if test["expected_finding"] == "omission":
            assert test["expected_text"].lower() in test["transcript"].lower(), (
                f"Test '{test['name']}': expected text '{test['expected_text']}' "
                f"not found in transcript"
            )
