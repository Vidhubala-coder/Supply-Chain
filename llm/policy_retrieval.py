"""
llm/policy_retrieval.py
Separate Local Document Retrieval Index for Policy & Guideline Markdown Documents.
Parses documents/*.md and ranks policy sections via text similarity. Zero external vector DB dependencies.
"""

import os
import re
import math
import difflib
from typing import List, Dict, Any, Optional

DOCUMENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "documents")

class PolicyIndex:
    def __init__(self, docs_dir: str = DOCUMENTS_DIR):
        self.docs_dir = docs_dir
        self.sections: List[Dict[str, Any]] = []
        self._load_documents()

    def _load_documents(self):
        if not os.path.exists(self.docs_dir):
            return

        for filename in os.listdir(self.docs_dir):
            if filename.endswith(".md"):
                filepath = os.path.join(self.docs_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Split by markdown headers e.g. ## Section ...
                chunks = re.split(r'\n(?=##\s+)', content)
                doc_title = filename
                for chunk in chunks:
                    chunk = chunk.strip()
                    if not chunk:
                        continue
                    lines = chunk.splitlines()
                    heading = doc_title
                    body = chunk
                    if lines[0].startswith("##") or lines[0].startswith("#"):
                        heading = lines[0].lstrip("#").strip()
                        body = "\n".join(lines[1:]).strip()

                    self.sections.append({
                        "filename": filename,
                        "heading": heading,
                        "text": body,
                        "full_content": chunk
                    })

    def search(self, query: str, top_k: int = 2, threshold: float = 0.20) -> List[Dict[str, Any]]:
        if not self.sections:
            return []

        query_words = set(re.findall(r'\w+', query.lower()))
        results = []

        for sec in self.sections:
            sec_text = (sec["heading"] + " " + sec["text"]).lower()
            sec_words = set(re.findall(r'\w+', sec_text))
            
            # Word overlap score (Jaccard similarity)
            intersection = query_words.intersection(sec_words)
            jaccard = len(intersection) / max(1, len(query_words.union(sec_words)))
            
            # Difflib sequence matcher score
            seq_score = difflib.SequenceMatcher(None, query.lower(), sec_text).ratio()
            
            combined_score = (jaccard * 0.7) + (seq_score * 0.3)

            if combined_score >= threshold:
                results.append({
                    "filename": sec["filename"],
                    "heading": sec["heading"],
                    "snippet": sec["text"][:250] + ("..." if len(sec["text"]) > 250 else ""),
                    "score": round(combined_score, 2),
                    "citation": f"[{sec['filename']} - {sec['heading']}]"
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

_policy_index_instance: Optional[PolicyIndex] = None

def get_policy_index() -> PolicyIndex:
    global _policy_index_instance
    if _policy_index_instance is None:
        _policy_index_instance = PolicyIndex()
    return _policy_index_instance

def retrieve_policy_snippets(query_text: str, top_k: int = 2, threshold: float = 0.15) -> List[Dict[str, Any]]:
    index = get_policy_index()
    return index.search(query_text, top_k=top_k, threshold=threshold)
