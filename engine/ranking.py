"""
engine/ranking.py
Deterministic Urgency Ranking Engine (Stage 3)
Calculates urgency score (0-100) for affected customer orders based on objective rules.
Zero LLM calls.
"""

from typing import Dict, Any

def compute_urgency_score(
    customer_tier: str,
    order_value: float,
    days_late: int,
    shortfall_qty: int,
    order_qty: int
) -> float:
    """
    Computes a grounded urgency score between 0.0 and 100.0.
    Factors:
    - Customer Tier Weight (VIP = 2.0, Standard = 1.0)
    - Order Value Factor (scaled log/linear)
    - Shortfall Severity Ratio (shortfall_qty / order_qty)
    - Days Late Severity (days_late / 7 days per week)
    """
    tier_weight = 2.0 if str(customer_tier).upper() == "VIP" else 1.0
    
    # Base value score: $1,000 = 10 pts, maxing out around $20,000 = 40 pts
    value_factor = min(40.0, (order_value / 500.0))
    
    # Shortfall ratio (0.0 - 1.0)
    shortfall_ratio = shortfall_qty / max(1, order_qty)
    
    # Delay factor: 7 days = 15 pts
    delay_factor = min(30.0, (days_late / 7.0) * 15.0)

    # Score calculation
    raw_score = (value_factor + delay_factor + (shortfall_ratio * 20.0)) * (tier_weight / 1.5)
    
    return min(100.0, round(max(5.0 if days_late > 0 or shortfall_qty > 0 else 0.0, raw_score), 1))

def rank_affected_orders(affected_orders: list) -> list:
    """
    Ranks affected orders in descending order of urgency score.
    """
    for ord_impact in affected_orders:
        score = compute_urgency_score(
            customer_tier=ord_impact.get("customer_tier", "Standard"),
            order_value=ord_impact.get("order_value", 0.0),
            days_late=ord_impact.get("days_late", 0),
            shortfall_qty=ord_impact.get("shortfall_qty", 0),
            order_qty=ord_impact.get("order_qty", 1)
        )
        ord_impact["urgency_score"] = score

    return sorted(affected_orders, key=lambda o: o["urgency_score"], reverse=True)
