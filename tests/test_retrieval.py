"""
tests/test_retrieval.py
Unit tests for Local Retrieval Layer (Vector search, difflib fuzzy fallback, threshold short-circuit).
"""

import unittest
from llm.retrieval import retrieve_candidates, RetrievalIndex
from llm.resolve import resolve_entities

class TestRetrieval(unittest.TestCase):
    def test_clean_match_top_k_ordering(self):
        notice = "URGENT DISRUPTION NOTICE: Apex Microelectronics (SUP-101) factory fire halted PMIC-8 production."
        res = retrieve_candidates(notice, top_k=5, threshold=0.25)
        
        self.assertFalse(res["below_threshold"])
        self.assertTrue(len(res["candidates"]) > 0)
        
        top_ids = [c["entity_id"] for c in res["candidates"]]
        self.assertTrue("SUP-101" in top_ids or "SKU-1002" in top_ids)

    def test_unrelated_notice_below_threshold_rejection(self):
        unrelated_notice = "INTERNAL MARKETING MEMO: Q4 promotional campaign strategy for North American consumer electronics trade show."
        res = resolve_entities(unrelated_notice, similarity_threshold=0.35)
        
        self.assertFalse(res["match_found"])
        self.assertEqual(len(res["candidate_matches"]), 0)
        self.assertIn("below threshold", res["ambiguity_notes"].lower())

    def test_fuzzy_matching_fallback(self):
        index = RetrievalIndex()
        # Force fuzzy matching method
        fuzzy_results = index.fuzzy_match("Apex Microelectronics supplier delay", top_k=3)
        self.assertTrue(len(fuzzy_results) > 0)
        self.assertEqual(fuzzy_results[0]["entity_id"], "SUP-101")
        self.assertEqual(fuzzy_results[0]["method"], "fuzzy")

if __name__ == "__main__":
    unittest.main()
