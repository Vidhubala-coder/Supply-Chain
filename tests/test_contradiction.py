"""
tests/test_contradiction.py
Unit tests for engine/contradiction_service.py.
Covers critical, non-critical, and no-contradiction scenarios.
"""

import unittest
from engine.contradiction_service import detect_contradictions

class TestContradictionService(unittest.TestCase):
    def setUp(self):
        self.suppliers = [
            {"id": "SUP-101", "name": "Apex Microelectronics"},
            {"id": "SUP-102", "name": "Lumina Optics"}
        ]
        self.stock = [
            {"sku": "SKU-1002", "name": "PMIC-8 Power Regulator", "supplier_id": "SUP-101"},
            {"sku": "SKU-1003", "name": "OLED-6 Display", "supplier_id": "SUP-102"}
        ]
        self.shipments = [
            {"id": "SHP-2002", "supplier_id": "SUP-101", "sku": "SKU-1002", "quantity": 1000, "status": "in_transit", "eta": "2026-09-15"}
        ]

    def test_no_contradiction(self):
        notice = "Apex Microelectronics (SUP-101) factory fire delayed SHP-2002 carrying 1000 units of SKU-1002."
        candidate_matches = [{"entity_type": "shipment", "entity_id": "SHP-2002"}]
        extracted_signals = {"stated_or_implied_duration": "14 days"}

        res = detect_contradictions(notice, extracted_signals, candidate_matches, self.suppliers, self.stock, self.shipments)
        self.assertFalse(res["has_contradiction"])
        self.assertEqual(res["severity"], "NONE")
        self.assertEqual(len(res["contradictions"]), 0)

    def test_critical_supplier_mismatch_contradiction(self):
        # Notice claims SUP-102, but mapped candidate is SHP-2002 (SUP-101)
        notice = "Lumina Optics (SUP-102) disruption affecting shipment SHP-2002."
        candidate_matches = [{"entity_type": "shipment", "entity_id": "SHP-2002"}]
        extracted_signals = {"stated_or_implied_duration": "14 days"}

        res = detect_contradictions(notice, extracted_signals, candidate_matches, self.suppliers, self.stock, self.shipments)
        self.assertTrue(res["has_contradiction"])
        self.assertEqual(res["severity"], "CRITICAL")
        self.assertTrue(any(c["field"] == "supplier" for c in res["contradictions"]))

    def test_critical_quantity_contradiction(self):
        # Notice claims 50 units, but DB SHP-2002 has 1000 units
        notice = "Shipment SHP-2002 delayed carrying 50 units of PMIC-8."
        candidate_matches = [{"entity_type": "shipment", "entity_id": "SHP-2002"}]
        extracted_signals = {"stated_or_implied_duration": "14 days"}

        res = detect_contradictions(notice, extracted_signals, candidate_matches, self.suppliers, self.stock, self.shipments)
        self.assertTrue(res["has_contradiction"])
        self.assertEqual(res["severity"], "CRITICAL")
        self.assertTrue(any(c["field"] == "quantity" for c in res["contradictions"]))

    def test_non_critical_status_contradiction(self):
        # Notice claims delivered, but DB status is in_transit
        notice = "Shipment SHP-2002 was delivered yesterday."
        candidate_matches = [{"entity_type": "shipment", "entity_id": "SHP-2002"}]
        extracted_signals = {"stated_or_implied_duration": "0 days"}

        res = detect_contradictions(notice, extracted_signals, candidate_matches, self.suppliers, self.stock, self.shipments)
        self.assertTrue(res["has_contradiction"])
        self.assertEqual(res["severity"], "NON_CRITICAL")
        self.assertTrue(any(c["field"] == "status" for c in res["contradictions"]))

if __name__ == "__main__":
    unittest.main()
