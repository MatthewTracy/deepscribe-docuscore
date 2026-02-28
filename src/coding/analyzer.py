"""
Coding intelligence analyzer (exploratory - not integrated into core pipeline).

Coding gap analysis: connect documentation quality to missed/incorrect ICD-10 codes
against ground-truth charts; initial work completed but not integrated pending further data.

Uses Claude to extract diagnoses from the transcript and note,
then uses the FAISS ICD-10 index to map them to codes and identify
coding gaps - places where the transcript supports a more specific
(higher-value) code than what the note documents.
"""

import json
import logging

import anthropic

from src.rate_limiter import wait_for_rate_limit
from src.models import CodingGap, CodingResult, SupportedCode
from src.coding.icd_index import ICDIndex


EXTRACTION_PROMPT = """Extract all medical diagnoses, conditions, and clinical findings from the following text. Include:
- Named diagnoses (e.g., "type 2 diabetes", "hypertension")
- Symptoms that imply a diagnosis (e.g., "A1C of 9.2" implies uncontrolled diabetes)
- Relevant clinical details that affect coding specificity (e.g., "with neuropathy", "stage 3")

Return a JSON array of objects, each with:
- "diagnosis": the condition as stated in the text
- "supporting_text": the exact quote from the text that supports this
- "specificity_details": any details that would affect ICD-10 code specificity (complications, severity, type, laterality)

Text to analyze:
{text}

Source: {source}

Respond with ONLY a JSON array. Example:
[
    {{
        "diagnosis": "type 2 diabetes with peripheral neuropathy",
        "supporting_text": "patient has uncontrolled T2DM with A1C 9.2 and numbness in feet",
        "specificity_details": "uncontrolled (hyperglycemia), with neuropathy"
    }}
]"""


def _extract_diagnoses(text: str, source: str, client: anthropic.Anthropic) -> list[dict]:
    """Use Claude to extract diagnoses from text."""
    wait_for_rate_limit()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        temperature=0.0,
        messages=[{
            "role": "user",
            "content": EXTRACTION_PROMPT.format(text=text, source=source),
        }],
    )

    if not response.content:
        logging.getLogger(__name__).warning(
            f"Empty response content from API for {source} diagnosis extraction"
        )
        return []

    response_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if response_text.startswith("```"):
        first_newline = response_text.index("\n")
        last_fence = response_text.rfind("```")
        if last_fence > first_newline:
            response_text = response_text[first_newline + 1:last_fence]

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        logging.getLogger(__name__).warning(
            f"Failed to parse diagnosis extraction response: {e}. "
            f"Response: {response_text[:200]}"
        )
        return []


def analyze_coding(
    transcript: str,
    soap_note: str,
    icd_index: ICDIndex,
) -> CodingResult:
    """
    Analyze coding opportunities by comparing transcript vs note diagnoses.

    1. Extract diagnoses from both transcript and note
    2. Map each to ICD-10 codes via FAISS
    3. Identify gaps where the transcript supports higher-specificity codes

    Args:
        transcript: Source clinical dialogue
        soap_note: The SOAP note
        icd_index: Pre-built FAISS index over ICD-10 codes

    Returns:
        CodingResult with supported codes and coding gaps
    """
    client = anthropic.Anthropic()

    # Extract diagnoses from both sources
    transcript_diagnoses = _extract_diagnoses(transcript, "clinical transcript", client)
    note_diagnoses = _extract_diagnoses(soap_note, "SOAP note", client)

    # Map note diagnoses to ICD-10 codes (these are "supported" codes)
    supported_codes = []

    for dx in note_diagnoses:
        matches = icd_index.search(dx["diagnosis"], top_k=3)
        if matches and matches[0]["similarity"] > 0.50:
            best = matches[0]
            code = SupportedCode(
                icd10_code=best["code"],
                description=best["description"],
                evidence_source="note",
                evidence_text=dx.get("supporting_text", dx["diagnosis"]),
                hcc_category=best.get("hcc"),
                hcc_description=best.get("hcc_description"),
            )
            supported_codes.append(code)

    # Map transcript diagnoses - look for gaps
    coding_gaps = []

    for dx in transcript_diagnoses:
        matches = icd_index.search(dx["diagnosis"], top_k=5)
        # Raise threshold from 0.35 → 0.55 to reduce false positive gaps.
        # Embedding similarity catches word-stem overlaps (fibrosis≈fibrillation,
        # deficiency≈clotting deficiency) that aren't clinically valid.
        if not matches or matches[0]["similarity"] < 0.55:
            continue

        best_transcript_match = matches[0]

        # Check if the transcript supports a MORE SPECIFIC code than the note
        # Look for the same condition family but higher specificity
        best_note_match = None
        for note_dx in note_diagnoses:
            note_matches = icd_index.search(note_dx["diagnosis"], top_k=3)
            if note_matches:
                # Check if same code family (first 3 chars of ICD-10)
                for nm in note_matches:
                    if (nm["code"][:3] == best_transcript_match["code"][:3]
                            and nm["similarity"] > 0.50):
                        best_note_match = nm
                        break
            if best_note_match:
                break

        # Gap exists if:
        # 1. Transcript code has HCC but note code doesn't, OR
        # 2. Transcript code is more specific (longer code), OR
        # 3. Transcript supports a code not found in note at all
        has_gap = False
        current_code = None

        if best_note_match:
            current_code = best_note_match["code"]
            transcript_has_hcc = best_transcript_match.get("hcc") is not None
            note_has_hcc = best_note_match.get("hcc") is not None

            if transcript_has_hcc and not note_has_hcc:
                has_gap = True
            elif (best_transcript_match.get("specificity") == "high"
                  and best_note_match.get("specificity") == "low"):
                has_gap = True
        else:
            # Transcript has a code the note doesn't mention at all
            if best_transcript_match.get("hcc"):
                has_gap = True

        if has_gap:
            hcc = best_transcript_match.get("hcc")
            annual_value = best_transcript_match.get("hcc_annual_value", 0)

            gap = CodingGap(
                transcript_evidence=dx.get("supporting_text", dx["diagnosis"]),
                current_note_text=best_note_match["description"] if best_note_match else "not mentioned in note",
                current_code=current_code,
                suggested_code=best_transcript_match["code"],
                suggested_description=best_transcript_match["description"],
                hcc_category=hcc,
                estimated_annual_value=float(annual_value) if annual_value else None,
                documentation_suggestion=_generate_doc_suggestion(
                    dx["diagnosis"],
                    dx.get("specificity_details", ""),
                    best_transcript_match["description"],
                ),
            )
            coding_gaps.append(gap)

    total_revenue = sum(g.estimated_annual_value or 0 for g in coding_gaps)

    return CodingResult(
        supported_codes=supported_codes,
        coding_gaps=coding_gaps,
        total_gap_count=len(coding_gaps),
        total_estimated_revenue_impact=total_revenue,
    )


def _generate_doc_suggestion(diagnosis: str, specificity: str, target_description: str) -> str:
    """Generate a concrete documentation improvement suggestion."""
    if specificity:
        return (
            f"To support code '{target_description}', document: \"{diagnosis}\" "
            f"with specificity details: {specificity}. "
            f"Include relevant clinical evidence (lab values, exam findings) in the note."
        )
    return (
        f"To support code '{target_description}', "
        f"add \"{diagnosis}\" to the appropriate SOAP section with supporting clinical details."
    )
