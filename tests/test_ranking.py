"""
tests/test_ranking.py
Unit tests for deterministic urgency ranking engine.
"""

import unittest
from engine.ranking import compute_urgency_score, rank_affected_orders

class TestRanking(unittest.TestCase):
    def test_compute_urgency_score_vip_high_value(self):
        score_vip = compute_urgency_score(
            customer_tier="VIP",
            order_value=13500.0,
            days_late=14,
            shortfall_qty=80,
            order_qty=150
        )
        score_standard = compute_urgency_score(
            customer_tier="Standard",
            order_value=1400.0,
            days_late=14,
            shortfall_qty=80,
            order_qty=150
        )
        
        self.assertGreater(score_vip, score_standard)
        self.assertGreaterEqual(score_vip, 50.0)

    def test_rank_affected_orders_sorting(self):
        orders = [
            {"order_id": "O1", "customer_tier": "Standard", "order_value": 1000, "days_late": 5, "shortfall_qty": 10, "order_qty": 100},
            {"order_id": "O2", "customer_tier": "VIP", "order_value": 15000, "days_late": 14, "shortfall_qty": 80, "order_qty": 100}
        ]
        ranked = rank_affected_orders(orders)
        self.assertEqual(ranked[0]["order_id"], "O2")
        self.assertGreater(ranked[0]["urgency_score"], ranked[1]["urgency_score"])

if __name__ == "__main__":
    unittest.main()
