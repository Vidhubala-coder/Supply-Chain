"""
engine/options.py
Deterministic Option & Trade-off Generator (Stage 3)
Single source of truth for all mitigations: safety stock usage, reallocation,
expedite air-freight cost estimation, and part-ship math. Zero LLM calls.
"""

from typing import List, Dict, Any

def generate_order_options(
    order_impact: Dict[str, Any],
    stock_item: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generates 4 concrete mitigation options with real deterministic figures for a single affected order:
    1. expedite: Air-freight replacement shipment
    2. part_ship: Immediate partial shipment of committed stock
    3. reallocate: Utilize safety stock or reallocate stock from standard orders
    4. notify_customer: Proactive delay notification
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
    # Option 1: Expedite via Air Freight
    # -------------------------------------------------------------
    days_saved_expedite = max(1, days_late - 3)
    expedite_cost = round(50.0 + (shortfall_qty * unit_cost * 0.25) + (days_saved_expedite * 15.0), 2)
    options.append({
        "action": "expedite",
        "title": "Expedite Air Freight Replacement",
        "tradeoff": f"Cost: ${expedite_cost:,.2f} air freight fee. Saves {days_saved_expedite} days delay, delivering in {days_late - days_saved_expedite} days.",
        "cost_estimate": expedite_cost,
        "days_saved": days_saved_expedite,
        "source_figures": {
            "expedite_fee": f"${expedite_cost:,.2f}",
            "days_saved": days_saved_expedite,
            "shortfall_qty": shortfall_qty,
            "unit_cost": f"${unit_cost:,.2f}"
        }
    })

    # -------------------------------------------------------------
    # Option 2: Part-Ship Available Stock
    # -------------------------------------------------------------
    handling_fee = 25.0
    options.append({
        "action": "part_ship",
        "title": "Part-Ship On-Hand Stock Immediately",
        "tradeoff": f"Ship {committed_stock} units immediately ({round((committed_stock/max(1, order_qty))*100)}% of order). Remaining {shortfall_qty} units delayed {days_late} days. Split fee: ${handling_fee:.2f}.",
        "cost_estimate": handling_fee,
        "days_saved": 0,
        "source_figures": {
            "immediate_ship_qty": committed_stock,
            "backorder_qty": shortfall_qty,
            "split_handling_fee": f"${handling_fee:.2f}"
        }
    })

    # -------------------------------------------------------------
    # Option 3: Reallocate Safety Stock
    # -------------------------------------------------------------
    realloc_qty = min(shortfall_qty, safety_stock)
    remaining_safety = max(0, safety_stock - realloc_qty)
    options.append({
        "action": "reallocate",
        "title": f"Reallocate Safety Stock ({realloc_qty} units)",
        "tradeoff": f"Draws {realloc_qty} units from warehouse safety buffer ({remaining_safety} units remaining). Zero extra customer delay for reallocated portion.",
        "cost_estimate": 0.0,
        "days_saved": days_late if realloc_qty >= shortfall_qty else max(1, days_late // 2),
        "source_figures": {
            "reallocated_qty": realloc_qty,
            "safety_stock_before": safety_stock,
            "safety_stock_after": remaining_safety,
            "sku": sku
        }
    })

    # -------------------------------------------------------------
    # Option 4: Proactive Delay Notification
    # -------------------------------------------------------------
    discount_credit = round(order_value * 0.05, 2)
    options.append({
        "action": "notify_customer",
        "title": "Notify & Reschedule Delivery",
        "tradeoff": f"Send delay advisory to customer ({days_late} days late). Offer 5% goodwill credit (${discount_credit:,.2f}).",
        "cost_estimate": discount_credit,
        "days_saved": 0,
        "source_figures": {
            "days_late": days_late,
            "goodwill_discount_credit": f"${discount_credit:,.2f}",
            "order_value": f"${order_value:,.2f}"
        }
    })

    # Recommended option selection algorithm
    if customer_tier.upper() == "VIP":
        if realloc_qty >= shortfall_qty:
            recommended_option = "reallocate"
            reason = f"VIP customer tier + safety stock can fully cover shortfall of {shortfall_qty} units."
        else:
            recommended_option = "expedite"
            reason = f"VIP customer order value (${order_value:,.2f}) warrants expedite air freight to minimize delay."
    else:
        if committed_stock > 0:
            recommended_option = "part_ship"
            reason = f"Standard tier order: Partial shipment of {committed_stock} units minimizes customer waiting time."
        else:
            recommended_option = "notify_customer"
            reason = f"Standard tier order: Proactive notification with goodwill credit is most cost-effective."

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
