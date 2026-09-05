"""
engine/options.py
Deterministic Option & Trade-off Generator (Stage 3)
Single source of truth for all mitigations: safety stock usage, reallocation,
expedite air-freight cost estimation, and part-ship math. Zero LLM calls.
"""

from typing import List, Dict, Any

# Named weights for deterministic recommendation score calculation
W_ORDERS = 100.0
W_CUSTOMERS = 150.0
W_COST = 1.0
W_DELAY = 3.0
W_RISK = 20.0

def generate_order_options(
    order_impact: Dict[str, Any],
    stock_item: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generates 4 concrete mitigation options with real deterministic figures for a single affected order:
    1. EXPEDITE SHIPMENT
    2. REALLOCATE INVENTORY
    3. PART-SHIP ORDERS
    4. NOTIFY CUSTOMERS / ADJUST DELIVERY
    """
    order_id = order_impact["order_id"]
    customer_tier = order_impact["customer_tier"]
    shortfall_qty = order_impact["shortfall_qty"]
    order_qty = order_impact["order_qty"]
    committed_stock = order_impact["committed_stock"]
    days_late = order_impact["days_late"]
    order_value = order_impact["order_value"]
    sku = order_impact["sku"]

    safety_stock = stock_item.get("safety_stock", 0) if stock_item else 0
    unit_cost = stock_item.get("unit_cost", 15.0) if stock_item else 15.0

    options = []

    # -------------------------------------------------------------
    # Option 1: EXPEDITE SHIPMENT
    # -------------------------------------------------------------
    days_saved_expedite = max(1, days_late - 3)
    expedite_cost = round(50.0 + (shortfall_qty * unit_cost * 0.25) + (days_saved_expedite * 15.0), 2)
    options.append({
        "action": "expedite",
        "title": "EXPEDITE SHIPMENT",
        "tradeoff": f"Cost: ${expedite_cost:,.2f} air freight fee. Saves {days_saved_expedite} days delay, delivering in {max(0, days_late - days_saved_expedite)} days.",
        "cost_estimate": expedite_cost,
        "days_saved": days_saved_expedite,
        "source_figures": {
            "expedite_fee": f"${expedite_cost:,.2f}",
            "days_saved": days_saved_expedite,
            "shortfall_qty": shortfall_qty,
            "unit_cost": f"${unit_cost:,.2f}"
        },
        "evidence": {
            "source_table": "shipments / stock",
            "record_ids": [order_id, sku],
            "raw_values": {
                "base_fee": 50.0,
                "shortfall_qty": shortfall_qty,
                "unit_cost": unit_cost,
                "days_saved": days_saved_expedite
            },
            "formula_string": "50.0 + (shortfall_qty * unit_cost * 0.25) + (days_saved * 15.0)",
            "calculated_result": expedite_cost
        }
    })

    # -------------------------------------------------------------
    # Option 2: REALLOCATE INVENTORY
    # -------------------------------------------------------------
    realloc_qty = min(shortfall_qty, safety_stock)
    remaining_safety = max(0, safety_stock - realloc_qty)
    reallocate_days_saved = days_late if (realloc_qty >= shortfall_qty and shortfall_qty > 0) else max(0, days_late // 2)
    options.append({
        "action": "reallocate",
        "title": "REALLOCATE INVENTORY",
        "tradeoff": f"Draws {realloc_qty} units from warehouse safety buffer ({remaining_safety} units remaining). Zero extra customer delay for reallocated portion.",
        "cost_estimate": 0.0,
        "days_saved": reallocate_days_saved,
        "source_figures": {
            "reallocated_qty": realloc_qty,
            "safety_stock_before": safety_stock,
            "safety_stock_after": remaining_safety,
            "sku": sku
        },
        "evidence": {
            "source_table": "stock",
            "record_ids": [sku],
            "raw_values": {
                "shortfall_qty": shortfall_qty,
                "safety_stock_available": safety_stock,
                "reallocated_qty": realloc_qty
            },
            "formula_string": "realloc_qty = min(shortfall_qty, safety_stock); cost = $0.00",
            "calculated_result": 0.0
        }
    })

    # -------------------------------------------------------------
    # Option 3: PART-SHIP ORDERS
    # -------------------------------------------------------------
    handling_fee = 25.0
    options.append({
        "action": "part_ship",
        "title": "PART-SHIP ORDERS",
        "tradeoff": f"Ship {committed_stock} units immediately ({round((committed_stock/max(1, order_qty))*100)}% of order). Remaining {shortfall_qty} units delayed {days_late} days. Split fee: ${handling_fee:.2f}.",
        "cost_estimate": handling_fee,
        "days_saved": 0,
        "source_figures": {
            "immediate_ship_qty": committed_stock,
            "backorder_qty": shortfall_qty,
            "split_handling_fee": f"${handling_fee:.2f}"
        },
        "evidence": {
            "source_table": "orders / stock",
            "record_ids": [order_id, sku],
            "raw_values": {
                "committed_stock": committed_stock,
                "shortfall_qty": shortfall_qty,
                "handling_fee": handling_fee
            },
            "formula_string": "split_handling_fee = 25.00",
            "calculated_result": handling_fee
        }
    })

    # -------------------------------------------------------------
    # Option 4: NOTIFY CUSTOMERS / ADJUST DELIVERY
    # -------------------------------------------------------------
    discount_credit = round(order_value * 0.05, 2)
    options.append({
        "action": "notify_customer",
        "title": "NOTIFY CUSTOMERS / ADJUST DELIVERY",
        "tradeoff": f"Send delay advisory to customer ({days_late} days late). Offer 5% goodwill credit (${discount_credit:,.2f}).",
        "cost_estimate": discount_credit,
        "days_saved": 0,
        "source_figures": {
            "days_late": days_late,
            "goodwill_discount_credit": f"${discount_credit:,.2f}",
            "order_value": f"${order_value:,.2f}"
        },
        "evidence": {
            "source_table": "orders",
            "record_ids": [order_id],
            "raw_values": {
                "order_value": order_value,
                "discount_rate": 0.05
            },
            "formula_string": "order_value * 0.05",
            "calculated_result": discount_credit
        }
    })

    # -------------------------------------------------------------
    # Deterministic Recommendation Score Calculation
    # formula: score = W_ORDERS*orders_protected + W_CUSTOMERS*customers_protected - W_COST*cost - W_DELAY*delay - W_RISK*risk
    # -------------------------------------------------------------
    is_vip = (str(customer_tier).upper() == "VIP")

    for opt in options:
        net_delay = max(0, days_late - opt["days_saved"])
        
        # Calculate protected status
        if opt["action"] == "reallocate":
            orders_prot = 1.0 if (realloc_qty >= shortfall_qty and shortfall_qty > 0) else 0.0
        elif opt["action"] == "expedite":
            orders_prot = 1.0 if is_vip else 0.4
        elif opt["action"] == "part_ship":
            orders_prot = 1.0 if committed_stock > 0 else 0.0
        else:
            orders_prot = 0.0

        cust_prot = (2.0 if is_vip else 1.0) * orders_prot
        cost_val = opt["cost_estimate"]
        delay_val = float(net_delay)
        risk_val = (1.5 if is_vip else 0.5) * (1.0 if net_delay > 0 else 0.0)

        score = (W_ORDERS * orders_prot) + (W_CUSTOMERS * cust_prot) - (W_COST * cost_val) - (W_DELAY * delay_val) - (W_RISK * risk_val)
        opt["recommendation_score"] = round(score, 2)

    highest_opt = max(options, key=lambda o: o["recommendation_score"])
    recommended_option = highest_opt["action"]
    reason = f"Option {highest_opt['title']} achieved top recommendation score ({highest_opt['recommendation_score']:.2f}) based on weighted protection, cost, and delay trade-offs."

    return {
        "options": options,
        "recommended_option": recommended_option,
        "recommendation_reason": reason
    }

def process_impact_options(
    impact_report: Dict[str, Any],
    stock: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Applies option generation and ranking to all affected orders in the impact report.
    """
    stock_by_sku = {s["sku"]: s for s in stock}
    affected_orders = impact_report.get("affected_orders", [])

    processed_orders = []
    for ord_impact in affected_orders:
        sku = ord_impact["sku"]
        stock_item = stock_by_sku.get(sku, {})
        
        opt_data = generate_order_options(ord_impact, stock_item)
        
        merged_order = {**ord_impact, **opt_data}
        processed_orders.append(merged_order)

    impact_report["affected_orders"] = processed_orders
    return impact_report
