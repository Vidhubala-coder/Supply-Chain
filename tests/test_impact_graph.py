"""
tests/test_impact_graph.py
Unit tests for deterministic graph traversal engine.
Verifies raw shortfall calculations without applying safety stock mitigations.
"""

import json
import os
import unittest
from engine.impact_graph import traverse_impact

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

class TestImpactGraph(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(DATA_DIR, "suppliers.json"), "r", encoding="utf-8") as f:
            self.suppliers = json.load(f)
        with open(os.path.join(DATA_DIR, "stock.json"), "r", encoding="utf-8") as f:
            self.stock = json.load(f)
        with open(os.path.join(DATA_DIR, "shipments.json"), "r", encoding="utf-8") as f:
            self.shipments = json.load(f)
        with open(os.path.join(DATA_DIR, "orders.json"), "r", encoding="utf-8") as f:
            self.orders = json.load(f)
        with open(os.path.join(DATA_DIR, "customers.json"), "r", encoding="utf-8") as f:
            self.customers = json.load(f)

    def test_traverse_impact_clean_supplier_delay(self):
        # Candidate match for Apex Microelectronics (SUP-101) & SHP-2002
        candidates = [
            {"entity_type": "supplier", "entity_id": "SUP-101", "confidence": 0.95},
            {"entity_type": "shipment", "entity_id": "SHP-2002", "confidence": 0.90}
        ]

        res = traverse_impact(
            candidate_matches=candidates,
            suppliers=self.suppliers,
            stock=self.stock,
            shipments=self.shipments,
            orders=self.orders,
            customers=self.customers,
            default_delay_days=14
        )

        self.assertIn("SUP-101", res["matched_entity_ids"])
        self.assertIn("SKU-1002", res["affected_skus"])
        self.assertTrue(len(res["affected_orders"]) > 0)

        # ORD-5001 is for SKU-1002 (PMIC-8), qty=200, on_hand=120 -> shortfall = 80
        ord1_impact = next(o for o in res["affected_orders"] if o["order_id"] == "ORD-5001")
        self.assertEqual(ord1_impact["order_qty"], 200)
        self.assertEqual(ord1_impact["committed_stock"], 120)
        self.assertEqual(ord1_impact["shortfall_qty"], 80)
        self.assertEqual(ord1_impact["days_late"], 14)
        self.assertEqual(ord1_impact["customer_tier"], "VIP")

    def test_traverse_impact_no_shortfall_trap(self):
        # SUP-104 disruption (Polymer Composites). SKU-1006 has 1000 on hand, order ORD-5009 requires 250.
        candidates = [
            {"entity_type": "supplier", "entity_id": "SUP-104", "confidence": 0.95}
        ]

        res = traverse_impact(
            candidate_matches=candidates,
            suppliers=self.suppliers,
            stock=self.stock,
            shipments=self.shipments,
            orders=self.orders,
            customers=self.customers,
            default_delay_days=14
        )

        # SKU-1006 has 1000 on hand, order ORD-5009 needs 250 -> committed_stock=250, shortfall=0, days_late=0.
        ord9_impact = [o for o in res["affected_orders"] if o["order_id"] == "ORD-5009"]
        self.assertEqual(len(ord9_impact), 0)

    def test_traverse_impact_multiple_skus(self):
        candidates = [
            {"entity_type": "supplier", "entity_id": "SUP-102", "confidence": 0.92}
        ]

        res = traverse_impact(
            candidate_matches=candidates,
            suppliers=self.suppliers,
            stock=self.stock,
            shipments=self.shipments,
            orders=self.orders,
            customers=self.customers,
            default_delay_days=10
        )

        self.assertIn("SKU-1003", res["affected_skus"])
        self.assertTrue(len(res["affected_orders"]) >= 1)

if __name__ == "__main__":
    unittest.main()
