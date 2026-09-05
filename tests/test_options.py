"""
tests/test_options.py
Unit tests for deterministic option generator and trade-off math.
"""

import unittest
from engine.options import generate_order_options, process_impact_options

class TestOptions(unittest.TestCase):
    def test_generate_order_options_vip(self):
        order_impact = {
            "order_id": "ORD-5001",
            "customer_tier": "VIP",
            "shortfall_qty": 80,
            "order_qty": 200,
            "committed_stock": 120,
            "days_late": 14,
            "order_value": 3000.0,
            "sku": "SKU-1002"
        }
        stock_item = {
            "sku": "SKU-1002",
            "safety_stock": 100,
            "unit_cost": 4.20
        }

        res = generate_order_options(order_impact, stock_item)
        
        self.assertEqual(len(res["options"]), 4)
        actions = [o["action"] for o in res["options"]]
        self.assertIn("expedite", actions)
        self.assertIn("part_ship", actions)
        self.assertIn("reallocate", actions)
        self.assertIn("notify_customer", actions)

        # Safety stock is 100, shortfall is 80 -> reallocate is recommended for VIP
        self.assertEqual(res["recommended_option"], "reallocate")

    def test_generate_order_options_standard(self):
        order_impact = {
            "order_id": "ORD-5004",
            "customer_tier": "Standard",
            "shortfall_qty": 50,
            "order_qty": 100,
            "committed_stock": 50,
            "days_late": 14,
            "order_value": 1400.0,
            "sku": "SKU-1002"
        }
        stock_item = {
            "sku": "SKU-1002",
            "safety_stock": 0,
            "unit_cost": 4.20
        }

        res = generate_order_options(order_impact, stock_item)
        self.assertEqual(res["recommended_option"], "part_ship")

if __name__ == "__main__":
    unittest.main()
