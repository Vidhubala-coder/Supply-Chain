"""
engine/impact_graph.py
Deterministic Graph Traversal Engine (Stage 2)
Pure Python graph traversal over supply chain data. Zero LLM calls.

Strict Contract:
- Computes ONLY raw shortfall (demand vs. currently-committed available stock,
  EXCLUDING safety stock) per affected order.
- Does NOT apply or resolve any mitigation (safety stock allocation, reallocation,
  or expedite math live exclusively in engine/options.py).
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

def parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return datetime.now()

def traverse_impact(
    candidate_matches: List[Dict[str, Any]],
    suppliers: List[Dict[str, Any]],
    stock: List[Dict[str, Any]],
    shipments: List[Dict[str, Any]],
    orders: List[Dict[str, Any]],
    customers: List[Dict[str, Any]],
    default_delay_days: int = 14
) -> Dict[str, Any]:
    """
    Traverse supply chain relational graph:
    matched entities -> affected shipments/stock -> pending orders -> impacted customers.
    """
    suppliers_by_id = {s["id"]: s for s in suppliers}
    stock_by_sku = {s["sku"]: s for s in stock}
    customers_by_id = {c["customer_id"]: c for c in customers}

    # Step 1: Resolve affected entities from candidate matches
    matched_supplier_ids = set()
    matched_shipment_ids = set()
    matched_skus = set()

    for match in candidate_matches:
        e_type = match.get("entity_type")
        e_id = match.get("entity_id")
        
        if e_type == "supplier":
            matched_supplier_ids.add(e_id)
            # Add SKUs supplied by this supplier
            if e_id in suppliers_by_id:
                for sku in suppliers_by_id[e_id].get("skus", []):
                    matched_skus.add(sku)
        elif e_type == "shipment":
            matched_shipment_ids.add(e_id)
        elif e_type == "stock_item":
            matched_skus.add(e_id)

    # Step 2: Trace affected shipments
    affected_shipments = []
    for shp in shipments:
        is_affected = False
        if shp["shipment_id"] in matched_shipment_ids:
            is_affected = True
        elif shp["supplier_id"] in matched_supplier_ids:
            is_affected = True
        elif shp["sku"] in matched_skus:
            is_affected = True

        if is_affected:
            affected_shipments.append(shp)
            matched_skus.add(shp["sku"])

    # Step 3: Determine delay duration per SKU/shipment
    delay_by_sku: Dict[str, int] = {}
    source_shipment_by_sku: Dict[str, str] = {}
    source_supplier_by_sku: Dict[str, str] = {}

    for shp in affected_shipments:
        sku = shp["sku"]
        delay_by_sku[sku] = max(delay_by_sku.get(sku, 0), default_delay_days)
        source_shipment_by_sku[sku] = shp["shipment_id"]
        source_supplier_by_sku[sku] = shp["supplier_id"]

    for sku in matched_skus:
        if sku not in delay_by_sku:
            delay_by_sku[sku] = default_delay_days
            # Find primary supplier for this SKU
            st = stock_by_sku.get(sku, {})
            sup_id = st.get("supplier_id")
            if sup_id:
                source_supplier_by_sku[sku] = sup_id

    # Step 4: Map pending orders and compute raw shortfall (demand vs unreserved on-hand stock)
    # Available stock for raw shortfall calculation = on_hand (EXCLUDING safety stock)
    on_hand_pool = {s["sku"]: s.get("on_hand", 0) for s in stock}

    affected_orders = []
    total_at_risk_value = 0.0

    # Sort orders by promised_date to simulate allocation queue
    sorted_orders = sorted(orders, key=lambda o: o.get("promised_date", "9999-12-31"))

    for ord_item in sorted_orders:
        sku = ord_item["sku"]
        if sku not in matched_skus:
            continue

        order_qty = ord_item["qty"]
        current_available = on_hand_pool.get(sku, 0)
        
        # Raw committed stock from unreserved on-hand
        committed_stock = min(current_available, order_qty)
        shortfall_qty = max(0, order_qty - committed_stock)
        
        # Update available pool for subsequent orders
        on_hand_pool[sku] = max(0, current_available - committed_stock)

        # Calculate projected delivery date & days late
        delay_days = delay_by_sku.get(sku, default_delay_days)
        promised_dt = parse_date(ord_item.get("promised_date", ""))
        
        if shortfall_qty > 0:
            est_delivery_dt = promised_dt + timedelta(days=delay_days)
            days_late = delay_days
        else:
            est_delivery_dt = promised_dt
            days_late = 0

        cust_info = customers_by_id.get(ord_item["customer_id"], {})
        cust_tier = ord_item.get("customer_tier") or cust_info.get("tier", "Standard")

        order_impact = {
            "order_id": ord_item["order_id"],
            "customer_id": ord_item["customer_id"],
            "customer_name": ord_item.get("customer_name") or cust_info.get("name", "Unknown"),
            "customer_tier": cust_tier,
            "sku": sku,
            "sku_name": ord_item.get("sku_name", sku),
            "order_qty": order_qty,
            "committed_stock": committed_stock,
            "shortfall_qty": shortfall_qty,
            "promised_date": ord_item.get("promised_date"),
            "estimated_delivery_date": est_delivery_dt.strftime("%Y-%m-%d"),
            "days_late": days_late,
            "order_value": ord_item.get("order_value", 0.0),
            "source_shipment_id": source_shipment_by_sku.get(sku),
            "source_supplier_id": source_supplier_by_sku.get(sku),
            "evidence": {
                "shortfall_qty": {
                    "source_table": "orders",
                    "record_ids": [ord_item["order_id"], sku],
                    "raw_values": {
                        "order_qty": order_qty,
                        "committed_stock": committed_stock,
                        "available_unreserved_on_hand": current_available
                    },
                    "formula_string": "shortfall_qty = max(0, order_qty - committed_stock)",
                    "calculated_result": shortfall_qty
                },
                "stock_coverage": {
                    "source_table": "stock",
                    "record_ids": [sku],
                    "raw_values": {
                        "committed_stock": committed_stock,
                        "order_qty": order_qty,
                        "coverage_pct": round((committed_stock / max(1, order_qty)) * 100, 1)
                    },
                    "formula_string": "committed_stock = min(on_hand_unreserved, order_qty)",
                    "calculated_result": committed_stock
                }
            }
        }

        # Order is affected if there is a shortfall OR delay
        if shortfall_qty > 0 or days_late > 0:
            affected_orders.append(order_impact)
            total_at_risk_value += ord_item.get("order_value", 0.0)

    return {
        "matched_entity_ids": list(matched_supplier_ids | matched_shipment_ids | matched_skus),
        "affected_shipments": [s["shipment_id"] for s in affected_shipments],
        "affected_skus": list(matched_skus),
        "affected_orders": affected_orders,
        "total_orders_affected": len(affected_orders),
        "total_at_risk_value": round(total_at_risk_value, 2)
    }
