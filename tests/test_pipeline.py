"""
tests/test_pipeline.py
End-to-end integration tests for the Supply Chain Disruption Response Assistant pipeline.
Covers clean matches, ambiguous notices, Stage 1 short-circuiting, no-impact traps, and 15s timeout fallback.
"""

import unittest
from unittest.mock import patch
from app import app
from fastapi.testclient import TestClient

client = TestClient(app)

class TestPipelineIntegration(unittest.TestCase):
    def test_health_check_endpoint(self):
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["track_id"], "PS08")

    def test_sample_notices_endpoint(self):
        response = client.get("/api/sample-notices")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("notices", data)
        self.assertGreaterEqual(len(data["notices"]), 6)

    def test_analyze_clean_match_pipeline(self):
        # Notice 1: Apex Microelectronics (SUP-101) PMIC-8 factory fire
        payload = {
            "notice_text": "URGENT: Apex Microelectronics (SUP-101) factory fire in Hsinchu. PMIC-8 Power Regulator production halted. Shipment SHP-2002 delayed by 14 days."
        }
        response = client.post("/api/analyze", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["match_found"])
        self.assertFalse(data["short_circuited"])
        self.assertIn("stage1", data)
        self.assertIn("stage2", data)
        self.assertIn("stage3", data)
        self.assertIn("stage4", data)

        # Confirm affected orders are found and options generated
        affected_orders = data["stage3"]["affected_orders"]
        self.assertGreater(len(affected_orders), 0)
        self.assertIn("options", affected_orders[0])

    def test_analyze_stage1_short_circuit_unrelated_notice(self):
        # Notice 8: Unrelated marketing email (match_found: false)
        payload = {
            "notice_text": "INTERNAL MARKETING MEMO: Q4 promotional campaign strategy for North American consumer electronics trade show."
        }
        response = client.post("/api/analyze", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertFalse(data["match_found"])
        self.assertTrue(data["short_circuited"])
        self.assertIsNone(data["stage2"])
        self.assertIsNone(data["stage3"])
        self.assertTrue(data["stage4"]["no_impact"])

    def test_analyze_no_impact_trap(self):
        # Notice 5: Polymer Composites (SUP-104) storm, but stock on hand (1000) covers reserved (400) -> 0 pending orders affected
        payload = {
            "notice_text": "FLASH DISRUPTION: Polymer Composites Corp (SUP-104) Texas facility storm damage. ABS resin plant offline 3 weeks. Shipment SHP-2007 delayed."
        }
        response = client.post("/api/analyze", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Entity matched, but 0 pending orders affected
        self.assertTrue(data["match_found"])
        self.assertFalse(data["short_circuited"])
        self.assertEqual(data["stage2"]["total_orders_affected"], 0)
        self.assertTrue(data["stage4"]["no_impact"])

    @patch("llm.client._raw_generate")
    def test_simulated_gemini_timeout_fast_fallback(self, mock_raw_generate):
        # Simulate slow/hung Gemini API call that times out or raises TimeoutError
        import concurrent.futures
        mock_raw_generate.side_effect = concurrent.futures.TimeoutError("Simulated API timeout")

        payload = {
            "notice_text": "URGENT: Apex Microelectronics (SUP-101) factory fire in Hsinchu. PMIC-8 Power Regulator production halted."
        }
        response = client.post("/api/analyze", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # System must fall back gracefully to deterministic pipeline execution without crashing
        self.assertTrue(data["match_found"])
        self.assertIn("stage4", data)

    def test_action_approve_and_history(self):
        approve_payload = {
            "order_id": "ORD-5001",
            "action": "reallocate",
            "recommendation_reason": "VIP tier safety stock allocation",
            "operator_notes": "Approved for immediate dispatch."
        }
        response = client.post("/api/action/approve", json=approve_payload)
        self.assertEqual(response.status_code, 200)

        history_res = client.get("/api/action/history")
        self.assertEqual(history_res.status_code, 200)
        history = history_res.json()["history"]
        self.assertGreater(len(history), 0)
        self.assertEqual(history[-1]["order_id"], "ORD-5001")
        self.assertEqual(history[-1]["status"], "APPROVED")

    def test_three_state_entity_matching_and_clarify(self):
        ambiguous_stage1 = {
            "notice_summary": "Ambiguous notice matching multiple suppliers.",
            "extracted_signals": {"mentioned_entities": ["Nova Sensors", "Nova Components"], "disruption_type": "shipping_delay", "stated_or_implied_duration": None},
            "match_state": "AMBIGUOUS",
            "match_found": False,
            "candidate_matches": [
                {"entity_type": "supplier", "entity_id": "SUP-105", "confidence": 0.85, "reason": "Match candidate 1"},
                {"entity_type": "supplier", "entity_id": "SUP-106", "confidence": 0.82, "reason": "Match candidate 2"}
            ],
            "ambiguity_notes": "Multiple candidates returned close confidence scores."
        }
        with patch("app.resolve_entities", return_value=ambiguous_stage1):
            res = client.post("/api/analyze", json={"notice_text": "Ambiguous notice text"})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["match_state"], "AMBIGUOUS")
            self.assertFalse(data["match_found"])
            self.assertTrue(data["short_circuited"])

        # Test disruption clarify endpoint
        clarify_payload = {
            "notice_text": "Ambiguous notice text",
            "entity_id": "SUP-105"
        }
        clarify_res = client.post("/api/disruption/clarify", json=clarify_payload)
        self.assertEqual(clarify_res.status_code, 200)
        c_data = clarify_res.json()
        self.assertEqual(c_data["match_state"], "EXACT")
        self.assertTrue(c_data["match_found"])
        self.assertFalse(c_data["short_circuited"])
        self.assertIn("stage3", c_data)

if __name__ == "__main__":
    unittest.main()
