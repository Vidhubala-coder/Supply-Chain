"""
llm/retrieval.py
Local Retrieval Layer using Precomputed Vector Index + NumPy Cosine Similarity.
Includes pure-Python difflib fuzzy matching fallback.
Zero live API calls during app startup or runtime search!
"""

import os
import json
import numpy as np
import difflib
from typing import List, Dict, Any
from scripts.build_embeddings import deterministic_feature_vector

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
NPY_PATH = os.path.join(DATA_DIR, "precomputed_embeddings.npy")
META_PATH = os.path.join(DATA_DIR, "index_meta.json")

class RetrievalIndex:
    def __init__(self):
        self.embeddings = None
        self.entities = []
        self._load_index()

    def _load_index(self):
        if os.path.exists(NPY_PATH) and os.path.exists(META_PATH):
            try:
                self.embeddings = np.load(NPY_PATH)
                with open(META_PATH, "r", encoding="utf-8") as f:
                    self.entities = json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load precomputed embeddings: {e}")
                self.embeddings = None
                self.entities = []

    def fuzzy_match(self, notice_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Pure Python difflib fuzzy match fallback over entity names and text."""
        notice_lower = notice_text.lower()
        results = []

        for ent in self.entities:
            name_score = difflib.SequenceMatcher(None, ent["name"].lower(), notice_lower).ratio()
            
            # Check for substring inclusion
            text_lower = ent["text"].lower()
            substring_bonus = 0.0
            for word in notice_lower.split():
                if len(word) > 3 and word in text_lower:
                    substring_bonus += 0.15

            total_score = min(1.0, round(name_score * 0.5 + min(0.5, substring_bonus), 3))
            results.append({
                "entity_type": ent["entity_type"],
                "entity_id": ent["entity_id"],
                "name": ent["name"],
                "similarity": float(total_score),
                "text": ent["text"],
                "method": "fuzzy"
            })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def retrieve_candidates(self, notice_text: str, top_k: int = 5, threshold: float = 0.25) -> Dict[str, Any]:
        """
        Retrieves top-k candidate entities using cosine similarity over precomputed embeddings.
        Falls back to difflib fuzzy matching if vector index is unavailable.
        """
        if self.embeddings is None or len(self.entities) == 0:
            candidates = self.fuzzy_match(notice_text, top_k=top_k)
        else:
            query_vec = deterministic_feature_vector(notice_text)
            scores = np.dot(self.embeddings, query_vec)

            candidates = []
            for i, score in enumerate(scores):
                ent = self.entities[i]
                sim = float(round(max(0.0, min(1.0, score)), 3))
                candidates.append({
                    "entity_type": ent["entity_type"],
                    "entity_id": ent["entity_id"],
                    "name": ent["name"],
                    "similarity": sim,
                    "text": ent["text"],
                    "metadata": ent.get("metadata", {}),
                    "method": "vector"
                })

            candidates.sort(key=lambda x: x["similarity"], reverse=True)
            candidates = candidates[:top_k]

        best_score = candidates[0]["similarity"] if candidates else 0.0
        below_threshold = best_score < threshold

        return {
            "candidates": candidates,
            "best_similarity": best_score,
            "below_threshold": below_threshold,
            "threshold_used": threshold
        }

# Global singleton retrieval instance loaded at import time
_retrieval_instance = None

def get_retrieval_index() -> RetrievalIndex:
    global _retrieval_instance
    if _retrieval_instance is None:
        _retrieval_instance = RetrievalIndex()
    return _retrieval_instance

def retrieve_candidates(notice_text: str, top_k: int = 5, threshold: float = 0.25) -> Dict[str, Any]:
    index = get_retrieval_index()
    return index.retrieve_candidates(notice_text, top_k=top_k, threshold=threshold)
