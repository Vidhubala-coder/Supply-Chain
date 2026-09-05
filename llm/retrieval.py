"""
llm/retrieval.py
Local Retrieval Layer using FAISS Vector Index + NumPy Cosine Similarity fallback.
Includes pure-Python difflib fuzzy matching fallback.
Zero live API calls during app startup or runtime search!
"""

import os
import json
import numpy as np
import difflib
from typing import List, Dict, Any
from scripts.build_embeddings import deterministic_feature_vector

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
NPY_PATH = os.path.join(DATA_DIR, "precomputed_embeddings.npy")
META_PATH = os.path.join(DATA_DIR, "index_meta.json")

class RetrievalIndex:
    def __init__(self):
        self.embeddings = None
        self.entities = []
        self.faiss_index = None
        self._load_index()

    def _load_index(self):
        if os.path.exists(NPY_PATH) and os.path.exists(META_PATH):
            try:
                self.embeddings = np.load(NPY_PATH).astype('float32')
                with open(META_PATH, "r", encoding="utf-8") as f:
                    self.entities = json.load(f)

                if HAS_FAISS and self.embeddings is not None:
                    # Normalize vectors for cosine similarity
                    faiss_embeds = self.embeddings.copy()
                    norms = np.linalg.norm(faiss_embeds, axis=1, keepdims=True)
                    norms[norms == 0] = 1e-10
                    faiss_embeds = faiss_embeds / norms

                    dimension = faiss_embeds.shape[1]
                    self.faiss_index = faiss.IndexFlatIP(dimension)
                    self.faiss_index.add(faiss_embeds)
            except Exception as e:
                print(f"Warning: Failed to load precomputed embeddings or FAISS index: {e}")
                self.embeddings = None
                self.entities = []
                self.faiss_index = None

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
        Retrieves top-k candidate entities using FAISS index (if available) or NumPy cosine similarity.
        Falls back to difflib fuzzy matching if vector index is unavailable.
        """
        if self.embeddings is None or len(self.entities) == 0:
            candidates = self.fuzzy_match(notice_text, top_k=top_k)
        elif self.faiss_index is not None and HAS_FAISS:
            query_vec = deterministic_feature_vector(notice_text).astype('float32')
            norm = np.linalg.norm(query_vec)
            if norm > 0:
                query_vec = query_vec / norm
            query_vec = np.expand_dims(query_vec, axis=0)

            distances, indices = self.faiss_index.search(query_vec, top_k)
            candidates = []
            for score, idx in zip(distances[0], indices[0]):
                if idx < len(self.entities):
                    ent = self.entities[idx]
                    sim = float(round(max(0.0, min(1.0, float(score))), 3))
                    candidates.append({
                        "entity_type": ent["entity_type"],
                        "entity_id": ent["entity_id"],
                        "name": ent["name"],
                        "similarity": sim,
                        "text": ent["text"],
                        "metadata": ent.get("metadata", {}),
                        "method": "faiss"
                    })
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
            "threshold_used": threshold,
            "faiss_enabled": HAS_FAISS and (self.faiss_index is not None)
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
