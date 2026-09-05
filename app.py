"""
app.py
FastAPI Web Server & Pipeline Orchestrator for Supply Chain Disruption Response Assistant (PS08).
Runs on http://localhost:8000 serving both API endpoints and the static SPA frontend.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from llm.resolve import resolve_entities
from engine.impact_graph import traverse_impact
from engine.ranking import rank_affected_orders
from engine.options import process_impact_options
from llm.narrate import narrate_plan

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

app = FastAPI(title="Supply Chain Disruption Response Assistant (PS08)")

# Load static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Audit log store
audit_log: List[Dict[str, Any]] = []

def load_data_file(filename: str) -> List[Dict[str, Any]]:
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# Request Models
class AnalyzeRequest(BaseModel):
    notice_text: Optional[str] = None
    notice_id: Optional[str] = None

class ActionRequest(BaseModel):
    order_id: str
    action: str
    recommendation_reason: Optional[str] = ""
    operator_notes: Optional[str] = ""

@app.get("/")
def read_root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"status": "API active", "message": "Static UI loading..."})

@app.get("/api/health")
def health_check():
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    npy_exists = os.path.exists(os.path.join(DATA_DIR, "precomputed_embeddings.npy"))
    return {
        "status": "online",
        "track_id": "PS08",
        "port": 8000,
        "gemini_api_configured": has_gemini,
        "vector_index_loaded": npy_exists,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/sample-notices")
def get_sample_notices():
    notices = load_data_file("notices.json")
    return {"notices": notices}

@app.get("/api/data-index")
def get_data_index():
    return {
        "suppliers": load_data_file("suppliers.json"),
        "stock": load_data_file("stock.json"),
        "shipments": load_data_file("shipments.json"),
        "orders": load_data_file("orders.json"),
        "customers": load_data_file("customers.json")
    }

@app.post("/api/analyze")
def analyze_disruption(req: AnalyzeRequest):
    notice_text = req.notice_text

    # Resolve notice text from sample ID if provided
    if not notice_text and req.notice_id:
        notices = load_data_file("notices.json")
        match_n = next((n for n in notices if n["id"] == req.notice_id), None)
        if match_n:
            notice_text = match_n["text"]

    if not notice_text or not notice_text.strip():
        raise HTTPException(status_code=400, detail="Notice text or valid notice_id is required.")

    # -------------------------------------------------------------
    # Stage 1: LLM Entity Resolution & Vector Retrieval
    # -------------------------------------------------------------
    stage1 = resolve_entities(notice_text.strip(), similarity_threshold=0.25)
    match_state = stage1.get("match_state", "EXACT" if stage1.get("match_found") else "UNMAPPED")

    # EXPLICIT SHORT-CIRCUIT BRANCH: If UNMAPPED in Stage 1
    if match_state == "UNMAPPED":
        return {
            "notice_text": notice_text,
            "stage1": stage1,
            "stage2": None,
            "stage3": None,
            "stage4": {
                "headline": "No matching supplier, shipment, or stock record found for this notice.",
                "affected_orders": [],
                "no_impact": True,
                "reason": "Stage 1 entity resolution returned match_state: UNMAPPED (similarity below threshold)."
            },
            "match_found": False,
            "match_state": "UNMAPPED",
            "short_circuited": True
        }

    # EXPLICIT SHORT-CIRCUIT BRANCH: If AMBIGUOUS in Stage 1 (Requires human clarification)
    if match_state == "AMBIGUOUS":
        return {
            "notice_text": notice_text,
            "stage1": stage1,
            "stage2": None,
            "stage3": None,
            "stage4": {
                "headline": "AMBIGUOUS ENTITY MATCH DETECTED",
                "affected_orders": [],
                "no_impact": False,
                "reason": "Multiple candidate entities matched this notice within a close confidence band. Human clarification required."
            },
            "candidate_matches": stage1.get("candidate_matches", []),
            "match_found": False,
            "match_state": "AMBIGUOUS",
            "short_circuited": True
        }

    # -------------------------------------------------------------
    # Stage 2: Deterministic Impact Graph Traversal (Zero LLM calls)
    # -------------------------------------------------------------
    suppliers = load_data_file("suppliers.json")
    stock = load_data_file("stock.json")
    shipments = load_data_file("shipments.json")
    orders = load_data_file("orders.json")
    customers = load_data_file("customers.json")

    candidate_matches = stage1.get("candidate_matches", [])
    raw_impact = traverse_impact(
        candidate_matches=candidate_matches,
        suppliers=suppliers,
        stock=stock,
        shipments=shipments,
        orders=orders,
        customers=customers
    )

    # -------------------------------------------------------------
    # Stage 3: Deterministic Urgency Ranking & Option/Cost Math
    # -------------------------------------------------------------
    ranked_orders = rank_affected_orders(raw_impact.get("affected_orders", []))
    raw_impact["affected_orders"] = ranked_orders
    stage3_impact = process_impact_options(raw_impact, stock)

    # -------------------------------------------------------------
    # Stage 4: Grounded LLM Plan Narration
    # -------------------------------------------------------------
    stage4 = narrate_plan(stage3_impact)

    return {
        "notice_text": notice_text,
        "stage1": stage1,
        "stage2": {
            "matched_entity_ids": raw_impact.get("matched_entity_ids"),
            "affected_shipments": raw_impact.get("affected_shipments"),
            "affected_skus": raw_impact.get("affected_skus"),
            "total_orders_affected": raw_impact.get("total_orders_affected"),
            "total_at_risk_value": raw_impact.get("total_at_risk_value")
        },
        "stage3": stage3_impact,
        "stage4": stage4,
        "match_found": True,
        "short_circuited": False
    }

class ClarifyRequest(BaseModel):
    notice_text: Optional[str] = None
    notice_id: Optional[str] = None
    entity_id: str

@app.post("/api/disruption/clarify")
def clarify_disruption(req: ClarifyRequest):
    notice_text = req.notice_text
    if not notice_text and req.notice_id:
        notices = load_data_file("notices.json")
        match_n = next((n for n in notices if n["id"] == req.notice_id), None)
        if match_n:
            notice_text = match_n["text"]

    if not notice_text or not notice_text.strip():
        raise HTTPException(status_code=400, detail="Notice text or valid notice_id is required.")

    suppliers = load_data_file("suppliers.json")
    stock = load_data_file("stock.json")
    shipments = load_data_file("shipments.json")
    orders = load_data_file("orders.json")
    customers = load_data_file("customers.json")

    entity_type = "supplier"
    name = req.entity_id
    if req.entity_id.startswith("SUP") or any(s["id"] == req.entity_id for s in suppliers):
        entity_type = "supplier"
        item = next((s for s in suppliers if s["id"] == req.entity_id), None)
        if item: name = item["name"]
    elif req.entity_id.startswith("SHP") or any(s["id"] == req.entity_id for s in shipments):
        entity_type = "shipment"
        item = next((s for s in shipments if s["id"] == req.entity_id), None)
        if item: name = f"Shipment {item['id']}"
    elif req.entity_id.startswith("SKU") or any(s["id"] == req.entity_id for s in stock):
        entity_type = "stock_item"
        item = next((s for s in stock if s["id"] == req.entity_id), None)
        if item: name = item["name"]

    stage1 = {
        "notice_summary": f"Human operator clarified disruption entity to {name} ({req.entity_id}).",
        "extracted_signals": {
            "mentioned_entities": [name],
            "disruption_type": "production_halt",
            "stated_or_implied_duration": "14 days"
        },
        "match_state": "EXACT",
        "match_found": True,
        "candidate_matches": [
            {
                "entity_type": entity_type,
                "entity_id": req.entity_id,
                "confidence": 1.0,
                "reason": "Human operator clarified entity selection."
            }
        ],
        "ambiguity_notes": "Clarified via operator selection."
    }

    raw_impact = traverse_impact(
        candidate_matches=stage1["candidate_matches"],
        suppliers=suppliers,
        stock=stock,
        shipments=shipments,
        orders=orders,
        customers=customers
    )

    ranked_orders = rank_affected_orders(raw_impact.get("affected_orders", []))
    raw_impact["affected_orders"] = ranked_orders
    stage3_impact = process_impact_options(raw_impact, stock)
    stage4 = narrate_plan(stage3_impact)

    return {
        "notice_text": notice_text,
        "stage1": stage1,
        "stage2": {
            "matched_entity_ids": raw_impact.get("matched_entity_ids"),
            "affected_shipments": raw_impact.get("affected_shipments"),
            "affected_skus": raw_impact.get("affected_skus"),
            "total_orders_affected": raw_impact.get("total_orders_affected"),
            "total_at_risk_value": raw_impact.get("total_at_risk_value")
        },
        "stage3": stage3_impact,
        "stage4": stage4,
        "match_found": True,
        "match_state": "EXACT",
        "short_circuited": False
    }

@app.post("/api/action/approve")
def approve_action(req: ActionRequest):
    entry = {
        "id": f"ACT-{len(audit_log)+1:04d}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "order_id": req.order_id,
        "status": "APPROVED",
        "chosen_action": req.action,
        "recommendation_reason": req.recommendation_reason,
        "operator_notes": req.operator_notes or "Action approved by human operator."
    }
    audit_log.append(entry)
    return {"status": "success", "entry": entry}

@app.post("/api/action/reject")
def reject_action(req: ActionRequest):
    entry = {
        "id": f"ACT-{len(audit_log)+1:04d}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "order_id": req.order_id,
        "status": "REJECTED",
        "chosen_action": req.action,
        "recommendation_reason": req.recommendation_reason,
        "operator_notes": req.operator_notes or "Action rejected by human operator."
    }
    audit_log.append(entry)
    return {"status": "success", "entry": entry}

@app.get("/api/action/history")
def get_action_history():
    return {"history": audit_log}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
