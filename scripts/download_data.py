"""
Download and prepare the evaluation dataset.

Uses omi-health/medical-dialogue-to-soap-summary from HuggingFace.
Each example has a clinical dialogue (transcript) and a SOAP note summary.
We sample 100 notes with a fixed seed for reproducibility.
"""

import json
import random
from pathlib import Path

from datasets import load_dataset


DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"

SAMPLE_SIZE = 100
SEED = 42


def download_and_prepare():
    print("Downloading omi-health/medical-dialogue-to-soap-summary...")
    ds = load_dataset("omi-health/medical-dialogue-to-soap-summary", split="train")
    print(f"  Total examples: {len(ds)}")

    # Sample with fixed seed
    random.seed(SEED)
    indices = random.sample(range(len(ds)), min(SAMPLE_SIZE, len(ds)))
    indices.sort()

    notes = []
    for i, idx in enumerate(indices):
        row = ds[idx]
        notes.append({
            "note_id": f"note_{i:03d}",
            "dataset_index": idx,
            "transcript": row["dialogue"],
            "soap_note": row["soap"],
        })

    # Save raw sample
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / "sample_100.json"
    with open(raw_path, "w") as f:
        json.dump(notes, f, indent=2)
    print(f"  Saved {len(notes)} notes to {raw_path}")

    # Show a quick preview
    print(f"\n  Preview of note_000:")
    print(f"    Transcript length: {len(notes[0]['transcript'])} chars")
    print(f"    SOAP note length:  {len(notes[0]['soap_note'])} chars")
    print(f"    Transcript start:  {notes[0]['transcript'][:120]}...")
    print(f"    SOAP start:        {notes[0]['soap_note'][:120]}...")

    return notes


if __name__ == "__main__":
    download_and_prepare()
