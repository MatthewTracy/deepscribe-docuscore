"""
FAISS vector index for ICD-10 code matching (exploratory - not integrated into core pipeline).

Coding gap analysis: connect documentation quality to missed/incorrect ICD-10 codes
against ground-truth charts; initial work completed but not integrated pending further data.

Instead of doing exact string matching (which misses paraphrases),
we embed ICD-10 code descriptions using sentence-transformers and
use FAISS to find the closest codes to extracted diagnosis text.
This handles the variation in how clinicians describe diagnoses.
"""

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

from src.coding.icd_data import ICD10_HCC_MAP, HCC_CATEGORIES


class ICDIndex:
    """FAISS index over ICD-10 code descriptions for semantic matching."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.codes = ICD10_HCC_MAP
        self.hcc_categories = HCC_CATEGORIES
        self.index = None
        self.embeddings = None
        self._build_index()

    def _build_index(self):
        """Embed all ICD-10 descriptions and build FAISS index."""
        descriptions = [c["description"] for c in self.codes]
        self.embeddings = self.model.encode(descriptions, normalize_embeddings=True)
        self.embeddings = np.array(self.embeddings, dtype=np.float32)

        # Use inner product (cosine similarity since we normalized)
        dimension = self.embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(self.embeddings)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Find the top-k ICD-10 codes most similar to a diagnosis description.

        Args:
            query: Natural language diagnosis text (e.g., "uncontrolled type 2 diabetes with neuropathy")
            top_k: Number of results to return

        Returns:
            List of dicts with code info and similarity score
        """
        query_embedding = self.model.encode([query], normalize_embeddings=True)
        query_embedding = np.array(query_embedding, dtype=np.float32)

        scores, indices = self.index.search(query_embedding, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            code_info = self.codes[idx].copy()
            code_info["similarity"] = float(score)

            # Add HCC value info if applicable
            hcc = code_info.get("hcc")
            if hcc and hcc in self.hcc_categories:
                code_info["hcc_description"] = self.hcc_categories[hcc]["description"]
                code_info["hcc_annual_value"] = self.hcc_categories[hcc]["avg_annual_value"]
            else:
                code_info["hcc_description"] = None
                code_info["hcc_annual_value"] = 0

            results.append(code_info)

        return results
