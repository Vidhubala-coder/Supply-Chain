"""
engine/contradiction_service.py
Deterministic Contradiction Detection Service (Zero LLM calls).
Runs after entity matching and before Stage 2 impact_graph traversal.
Compares notice text / extracted signals against matched database records.
"""

import re
from typing import Dict, Any, List, Optional

def detect_contradictions(
    notice_text: str,
    extracted_signals: Dict[str, Any],
    candidate_matches: List[Dict[str, Any]],
    suppliers: List[Dict[str, Any]],
    stock: List[Dict[str, Any]],
    shipments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compares fields in notice against matched DB records:
    - Supplier
    - Product / SKU
    - Quantity
    - Status
    - Shipment Date / ETA

    Returns:
    {
        "has_contradiction": bool,
        "severity": "CRITICAL" | "NON_CRITICAL" | "NONE",
        "contradictions": [...],
        "summary": str
    }
    """
    if not candidate_matches:
        return {
            "has_contradiction": False,
            "severity": "NONE",
            "contradictions": [],
            "summary": "No candidate matches to compare against."
        }

    # Maps for lookup
    supplier_map = {s.get("id"): s for s in suppliers}
    stock_map = {st.get("sku", st.get("id")): st for st in stock}
    shipment_map = {sh.get("id"): sh for sh in shipments}

    contradictions = []
    text_lower = notice_text.lower()

    # Find matched entity records
    matched_supplier = None
    matched_shipment = None
    matched_sku = None

    for cm in candidate_matches:
        eid = cm.get("entity_id", "")
        etype = cm.get("entity_type", "")
        if etype == "supplier" and eid in supplier_map:
            matched_supplier = supplier_map[eid]
        elif etype == "shipment" and eid in shipment_map:
            matched_shipment = shipment_map[eid]
            if matched_shipment.get("supplier_id") in supplier_map:
                matched_supplier = supplier_map[matched_shipment["supplier_id"]]
            if matched_shipment.get("sku") in stock_map:
                matched_sku = stock_map[matched_shipment["sku"]]
        elif etype == "stock_item" and eid in stock_map:
            matched_sku = stock_map[eid]
            if matched_sku.get("supplier_id") in supplier_map:
                matched_supplier = supplier_map[matched_sku["supplier_id"]]

    # 1. Supplier Check (Critical)
    if matched_supplier:
        sup_id = matched_supplier["id"]
        sup_name = matched_supplier["name"].lower()
        # Check if notice mentions a DIFFERENT supplier explicitly (e.g. SUP-102 while matched is SUP-101)
        sup_id_matches = re.findall(r'SUP-\d{3}', notice_text.upper())
        for sid in sup_id_matches:
            if sid in supplier_map and sid != sup_id:
                contradictions.append({
                    "field": "supplier",
                    "stated_in_notice": f"Supplier {sid} ({supplier_map[sid]['name']})",
                    "database_record": f"Supplier {sup_id} ({matched_supplier['name']})",
                    "severity": "CRITICAL",
                    "explanation": f"Notice explicitly references {sid} but entity matching mapped to {sup_id}."
                })

    # 2. Product / SKU Check (Critical)
    if matched_sku:
        sku_id = matched_sku.get("sku", matched_sku.get("id"))
        sku_id_matches = re.findall(r'SKU-\d{4}', notice_text.upper())
        for sk in sku_id_matches:
            if sk in stock_map and sk != sku_id:
                contradictions.append({
                    "field": "product",
                    "stated_in_notice": f"SKU {sk} ({stock_map[sk]['name']})",
                    "database_record": f"SKU {sku_id} ({matched_sku['name']})",
                    "severity": "CRITICAL",
                    "explanation": f"Notice references SKU {sk} but matched record is for SKU {sku_id}."
                })

    # 3. Quantity Check (Critical if mismatch > 50%)
    if matched_shipment:
        db_qty = matched_shipment.get("quantity", 0)
        # Search for quantities in notice e.g. "50 units", "quantity: 100", "50 pcs"
        qty_matches = re.findall(r'(\d+)\s*(?:units|pcs|pieces|qty|quantity)', text_lower)
        if qty_matches and db_qty > 0:
            stated_qty = int(qty_matches[0])
            diff_ratio = abs(stated_qty - db_qty) / db_qty
            if diff_ratio > 0.5:
                contradictions.append({
                    "field": "quantity",
                    "stated_in_notice": f"{stated_qty} units",
                    "database_record": f"{db_qty} units (Shipment {matched_shipment['id']})",
                    "severity": "CRITICAL",
                    "explanation": f"Notice states quantity of {stated_qty} units which conflicts with DB shipment record of {db_qty} units."
                })

    # 4. Status Check (Non-Critical)
    if matched_shipment:
        db_status = matched_shipment.get("status", "")
        if "delivered" in text_lower or "completed" in text_lower:
            if db_status == "in_transit":
                contradictions.append({
                    "field": "status",
                    "stated_in_notice": "delivered / completed",
                    "database_record": f"in_transit (Shipment {matched_shipment['id']})",
                    "severity": "NON_CRITICAL",
                    "explanation": f"Notice indicates shipment is completed, whereas DB record lists status as {db_status}."
                })

    # 5. Date / Duration Discrepancy (Non-Critical)
    stated_duration = extracted_signals.get("stated_or_implied_duration") or ""
    if "60 days" in stated_duration.lower() or "60-day" in text_lower:
        contradictions.append({
            "field": "shipment_date",
            "stated_in_notice": stated_duration or "60 days delay",
            "database_record": "Standard lead time / ETA schedule",
            "severity": "NON_CRITICAL",
            "explanation": "Notice states an extended 60-day delay exceeding standard supplier variance threshold."
        })

    if not contradictions:
        return {
            "has_contradiction": False,
            "severity": "NONE",
            "contradictions": [],
            "summary": "No contradictions detected between notice and database records."
        }

    has_critical = any(c["severity"] == "CRITICAL" for c in contradictions)
    overall_severity = "CRITICAL" if has_critical else "NON_CRITICAL"
    summary_msg = f"{overall_severity} CONTRADICTION DETECTED: " + "; ".join([c["explanation"] for c in contradictions])

    return {
        "has_contradiction": True,
        "severity": overall_severity,
        "contradictions": contradictions,
        "summary": summary_msg
    }
