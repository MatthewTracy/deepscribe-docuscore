"""Quick test: run the full pipeline on 1 note to verify everything works."""

import json
import os
import sys
from pathlib import Path

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip().strip("'\"")

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import NoteInput
from src.pipeline import evaluate_single_note
from src.coding.icd_index import ICDIndex

# Load first note
with open(Path(__file__).parent.parent / "data/raw/sample_100.json") as f:
    notes = json.load(f)

n = notes[0]
note_input = NoteInput(note_id=n["note_id"], transcript=n["transcript"], soap_note=n["soap_note"])

print("Building ICD-10 index...")
icd_index = ICDIndex()
print(f"Index ready: {len(icd_index.codes)} codes\n")

print(f"=== Evaluating {note_input.note_id} ===\n")
report = evaluate_single_note(note_input, icd_index)

print(f"Quality Gate: {report.quality_gate.decision.value}")
for r in report.quality_gate.reasons:
    print(f"  - {r}")
print(f"\nOverall Score: {report.overall_score}")

print(f"\n--- Deterministic ---")
print(f"Section completeness: {report.deterministic.section_completeness_score:.0%}")
print(f"Entity grounding: {report.deterministic.entity_grounding_rate:.0%}")
print(f"Contradictions: {len(report.deterministic.contradictions)}")

print(f"\n--- LLM Judge ---")
print(f"Overall quality: {report.llm_judge.overall_quality}/5")
for section, score in report.llm_judge.section_scores.items():
    print(f"  {section}: C={score.completeness} F={score.faithfulness} A={score.clinical_accuracy}")
print(f"Hallucinations: {len(report.llm_judge.hallucinations)}")
for h in report.llm_judge.hallucinations:
    print(f"  [{h.severity}] {h.hallucination_type.value}: {h.note_text[:60]}")
print(f"Omissions: {len(report.llm_judge.omissions)}")
for o in report.llm_judge.omissions:
    print(f"  [{o.clinical_importance}] {o.transcript_text[:60]}")

# Save test output
output_path = Path(__file__).parent.parent / "output" / "test_single.json"
output_path.parent.mkdir(exist_ok=True)
with open(output_path, "w") as f:
    f.write(report.model_dump_json(indent=2))
print(f"\nFull report saved to {output_path}")
