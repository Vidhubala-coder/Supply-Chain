"""
app.py
Enterprise FastAPI Control Tower Server & Pipeline Orchestrator for PS08.
Runs on http://localhost:8000 serving all APIs and static SPA frontend.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Header, Depends, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.database import (
    init_db, get_db_connection, hash_password,
    fetch_suppliers, fetch_stock, fetch_shipments, fetch_orders, fetch_customers,
    safe_delete_product, safe_delete_supplier, safe_delete_warehouse,
    safe_delete_customer, safe_delete_user
)
from backend.auth import authenticate_user, get_current_session, invalidate_session
from backend.notifications import create_notification, get_all_notifications, get_templates
from backend.reports import generate_report, get_reports_list, generate_pdf_bytes

from llm.resolve import resolve_entities
from engine.contradiction_service import detect_contradictions
from engine.impact_graph import traverse_impact
from engine.ranking import rank_affected_orders
from engine.options import process_impact_options
from llm.narrate import narrate_plan

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

app = FastAPI(title="Enterprise Supply Chain Control Tower (PS08)")

# Initialize Database on Startup
init_db()

# Load static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Audit log store
audit_log: List[Dict[str, Any]] = []

def load_data_file(filename: str) -> List[Dict[str, Any]]:
    """Backed by live SQLite database while maintaining zero breaking changes."""
    if filename == "suppliers.json":
        return fetch_suppliers()
    elif filename == "stock.json":
        return fetch_stock()
    elif filename == "shipments.json":
        return fetch_shipments()
    elif filename == "orders.json":
        return fetch_orders()
    elif filename == "customers.json":
        return fetch_customers()

    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

# Request Models
class LoginRequest(BaseModel):
    username: str
    password: str

class AnalyzeRequest(BaseModel):
    notice_text: Optional[str] = None
    notice_id: Optional[str] = None

class ActionRequest(BaseModel):
    order_id: str
    action: str
    recommendation_reason: Optional[str] = ""
    operator_notes: Optional[str] = ""

class ClarifyRequest(BaseModel):
    notice_text: Optional[str] = None
    notice_id: Optional[str] = None
    entity_id: str

class ProductModel(BaseModel):
    id: Optional[str] = None
    name: str
    sku: str
    category: str
    supplier_id: str
    unit_cost: float
    reorder_level: Optional[int] = 50
    status: Optional[str] = "ACTIVE"

class SupplierModel(BaseModel):
    id: Optional[str] = None
    name: str
    contact: str
    email: str
    location: str
    performance: Optional[float] = 95.0
    status: Optional[str] = "ACTIVE"

class WarehouseModel(BaseModel):
    id: Optional[str] = None
    name: str
    location: str
    capacity: int
    current_utilization: Optional[float] = 50.0
    status: Optional[str] = "ACTIVE"

class InventoryModel(BaseModel):
    id: Optional[str] = None
    product_id: str
    warehouse_id: str
    current_stock: int
    daily_demand: int
    safety_stock: int
    status: Optional[str] = "HEALTHY"

class ShipmentModel(BaseModel):
    id: Optional[str] = None
    supplier_id: str
    product_id: str
    quantity: int
    origin: str
    destination_warehouse_id: str
    expected_delivery: str
    actual_delivery: Optional[str] = None
    status: str
    delay_duration: Optional[int] = 0
    delay_reason: Optional[str] = None
    expected_new_delivery_date: Optional[str] = None

class OrderModel(BaseModel):
    id: Optional[str] = None
    customer_id: str
    product_id: str
    quantity: int
    order_date: str
    required_delivery_date: str
    status: str
    priority: Optional[str] = "NORMAL"

class CustomerModel(BaseModel):
    id: Optional[str] = None
    name: str
    company: str
    email: str
    priority: Optional[str] = "NORMAL"

class UserModel(BaseModel):
    id: Optional[str] = None
    username: str
    password: Optional[str] = "password123"
    name: str
    email: str
    role: str
    status: Optional[str] = "ACTIVE"

class NotificationRequest(BaseModel):
    sender: str
    recipient: str
    subject: str
    message: str
    reason: str
    related_shipment_id: Optional[str] = None
    related_order_id: Optional[str] = None

class ReportGenRequest(BaseModel):
    period: str = "2026-09"

class EscalationRequest(BaseModel):
    reason: str
    severity: str
    related_disruption_id: Optional[str] = None
    assigned_to: Optional[str] = "Lead Ops Manager"

# ROOT & HEALTH
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
    db_exists = os.path.exists(os.path.join(DATA_DIR, "supply_chain.db"))
    return {
        "status": "online",
        "track_id": "PS08",
        "port": 8000,
        "gemini_api_configured": has_gemini,
        "vector_index_loaded": npy_exists,
        "database_connected": db_exists,
        "timestamp": datetime.now().isoformat()
    }

# AUTHENTICATION
@app.post("/api/auth/login")
def login(req: LoginRequest):
    session = authenticate_user(req.username, req.password)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {"status": "success", "session": session}

@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        invalidate_session(token)
    return {"status": "logged_out"}

@app.get("/api/auth/me")
def get_me(authorization: Optional[str] = Header(None)):
    session = get_current_session(authorization)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"user": session}

# CORE DISRUPTION API
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

def log_timeline_event(stage: str, details: str, notice_id: Optional[str] = None, order_id: Optional[str] = None, status: str = "INFO"):
    entry = {
        "id": f"TL-{len(audit_log)+1:04d}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage": stage,
        "details": details,
        "notice_id": notice_id,
        "order_id": order_id,
        "status": status
    }
    audit_log.append(entry)
    return entry

@app.post("/api/analyze")
def analyze_disruption(req: AnalyzeRequest):
    notice_text = req.notice_text

    if not notice_text and req.notice_id:
        notices = load_data_file("notices.json")
        match_n = next((n for n in notices if n["id"] == req.notice_id), None)
        if match_n:
            notice_text = match_n["text"]

    if not notice_text or not notice_text.strip():
        raise HTTPException(status_code=400, detail="Notice text or valid notice_id is required.")

    log_timeline_event("Notice Received", f"Ingested disruption notice text ({len(notice_text)} chars).", notice_id=req.notice_id)

    stage1 = resolve_entities(notice_text.strip(), similarity_threshold=0.25)
    match_state = stage1.get("match_state", "EXACT" if stage1.get("match_found") else "UNMAPPED")

    log_timeline_event("Entities Matched", f"Stage 1 entity resolution state: {match_state}.", notice_id=req.notice_id)

    if match_state == "UNMAPPED":
        log_timeline_event("Awaiting Resolution", "Short-circuited due to UNMAPPED entity state.", notice_id=req.notice_id, status="UNMAPPED")
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
            "short_circuited": True,
            "timeline": [e for e in audit_log if e.get("notice_id") == req.notice_id or e.get("stage")]
        }

    if match_state == "AMBIGUOUS":
        log_timeline_event("Awaiting Clarification", "Short-circuited pending human entity clarification.", notice_id=req.notice_id, status="AMBIGUOUS")
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
            "short_circuited": True,
            "timeline": [e for e in audit_log if e.get("notice_id") == req.notice_id or e.get("stage")]
        }

    suppliers = load_data_file("suppliers.json")
    stock = load_data_file("stock.json")
    shipments = load_data_file("shipments.json")
    orders = load_data_file("orders.json")
    customers = load_data_file("customers.json")

    candidate_matches = stage1.get("candidate_matches", [])
    contradiction_res = detect_contradictions(
        notice_text=notice_text,
        extracted_signals=stage1.get("extracted_signals", {}),
        candidate_matches=candidate_matches,
        suppliers=suppliers,
        stock=stock,
        shipments=shipments
    )

    if contradiction_res.get("severity") == "CRITICAL":
        log_timeline_event("Contradiction Blocked", contradiction_res["summary"], notice_id=req.notice_id, status="CRITICAL_CONTRADICTION")
        return {
            "notice_text": notice_text,
            "stage1": stage1,
            "contradiction": contradiction_res,
            "stage2": None,
            "stage3": None,
            "stage4": {
                "headline": "CRITICAL CONTRADICTION DETECTED",
                "affected_orders": [],
                "no_impact": False,
                "reason": contradiction_res["summary"]
            },
            "match_found": True,
            "short_circuited": True,
            "timeline": [e for e in audit_log if e.get("notice_id") == req.notice_id or e.get("stage")]
        }

    raw_impact = traverse_impact(
        candidate_matches=candidate_matches,
        suppliers=suppliers,
        stock=stock,
        shipments=shipments,
        orders=orders,
        customers=customers
    )
    log_timeline_event("Impact Calculated", f"Identified {raw_impact.get('total_orders_affected', 0)} affected pending order(s).", notice_id=req.notice_id)

    ranked_orders = rank_affected_orders(raw_impact.get("affected_orders", []))
    raw_impact["affected_orders"] = ranked_orders
    stage3_impact = process_impact_options(raw_impact, stock)
    log_timeline_event("Options Evaluated", "Generated 4 mitigation options with deterministic costs and recommendation scores.", notice_id=req.notice_id)

    stage4 = narrate_plan(stage3_impact)
    log_timeline_event("Recommendation Made", f"Final plan generated: {stage4.get('headline', '')}", notice_id=req.notice_id)
    log_timeline_event("Awaiting Approval", "Action plan prepared for human operator review.", notice_id=req.notice_id, status="AWAITING_APPROVAL")

    return {
        "notice_text": notice_text,
        "stage1": stage1,
        "contradiction": contradiction_res,
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
        "short_circuited": False,
        "timeline": [e for e in audit_log if e.get("notice_id") == req.notice_id or e.get("stage")]
    }

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

# ACTIONS & DECISION AUDIT
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
    log_timeline_event(stage="Rejected", details=f"Order {req.order_id} action rejected by operator.", order_id=req.order_id, status="REJECTED")
    return {"status": "success", "entry": entry}

@app.post("/api/action/escalate")
def escalate_action(req: ActionRequest):
    entry = {
        "id": f"ACT-{len(audit_log)+1:04d}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "order_id": req.order_id,
        "status": "ESCALATED",
        "chosen_action": req.action or "escalate_to_human",
        "recommendation_reason": req.recommendation_reason or "Escalated for human compliance/operator review.",
        "operator_notes": req.operator_notes or "Incident escalated by operator."
    }
    audit_log.append(entry)
    log_timeline_event(stage="Escalated", details=f"Incident for {req.order_id} escalated to management.", order_id=req.order_id, status="ESCALATED")
    
    # Also log to DB escalations
    conn = get_db_connection()
    esc_id = f"ESC-{uuid.uuid4().hex[:6].upper()}"
    conn.execute("INSERT INTO escalations VALUES (?,?,?,?,?,?,?)", (esc_id, req.recommendation_reason or "Human escalation triggered", "HIGH", None, "PENDING", "Lead Ops Manager", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

    return {"status": "success", "entry": entry}

@app.get("/api/action/history")
def get_action_history():
    return {"history": audit_log}

# AI PROBLEM ANALYSIS
@app.get("/api/ai-analysis")
def get_ai_problem_analysis():
    return {
        "problem_summary": "Supply chain disruption analysis indicates component delay risk across high-urgency customer orders.",
        "reported_cause": "Supplier component production halt and carrier maritime transit delay.",
        "affected_entities": {
            "suppliers": ["SUP-001 (ABC Components)", "SUP-004 (Precision Optical)"],
            "shipments": ["SHP102", "SHP104"],
            "warehouses": ["WH-NORTH", "WH-EAST"]
        },
        "operational_impact": {
            "shortage_skus": ["SKU101 (Motor-X)", "SKU104 (Sensors)"],
            "total_orders_at_risk": 47,
            "total_customers_affected": 28,
            "financial_exposure": 185000.0
        },
        "risk_level": "HIGH",
        "unknown_information": [
            "Exact customs release date for Rotterdam Terminal shipment SHP104",
            "Alternative air-freight availability out of Frankfurt Depot"
        ],
        "recommended_investigation": [
            "Request immediate air-freight expedited quotes from Carrier",
            "Perform local warehouse inventory audit at WH-SOUTH for reserve stock"
        ],
        "policy_evidence": [
            {"source": "response_guidelines.md", "section": "Critical Order Protection", "rule": "Orders with lead time < 5 days or VIP customers must be prioritized for inventory reallocation."}
        ]
    }

# ENTERPRISE CRUD MANAGEMENT API
# 1. PRODUCTS
@app.get("/api/products")
def get_products():
    conn = get_db_connection()
    rows = conn.execute("""
    SELECT p.*, s.name as supplier_name 
    FROM products p 
    LEFT JOIN suppliers s ON p.supplier_id = s.id
    ORDER BY p.id ASC
    """).fetchall()
    conn.close()
    return {"products": [dict(r) for r in rows]}

@app.post("/api/products")
def create_product(p: ProductModel):
    conn = get_db_connection()
    p_id = p.id or f"PRD-{p.sku}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?)", (p_id, p.name, p.sku, p.category, p.supplier_id, p.unit_cost, p.reorder_level, p.status, now_str))
    conn.commit()
    conn.close()
    return {"status": "success", "id": p_id}

@app.put("/api/products/{product_id}")
def update_product(product_id: str, p: ProductModel):
    conn = get_db_connection()
    conn.execute("""
    UPDATE products 
    SET name=?, sku=?, category=?, supplier_id=?, unit_cost=?, reorder_level=?, status=?
    WHERE id=?
    """, (p.name, p.sku, p.category, p.supplier_id, p.unit_cost, p.reorder_level, p.status, product_id))
    conn.commit()
    conn.close()
    return {"status": "success", "id": product_id}

@app.delete("/api/products/{product_id}")
def delete_product(product_id: str):
    success, msg = safe_delete_product(product_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}

# 2. SUPPLIERS
@app.get("/api/suppliers")
def get_suppliers():
    return {"suppliers": fetch_suppliers()}

@app.post("/api/suppliers")
def create_supplier(s: SupplierModel):
    conn = get_db_connection()
    s_id = s.id or f"SUP-{uuid.uuid4().hex[:4].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO suppliers VALUES (?,?,?,?,?,?,?,?)", (s_id, s.name, s.contact, s.email, s.location, s.status, s.performance, now_str))
    conn.commit()
    conn.close()
    return {"status": "success", "id": s_id}

@app.delete("/api/suppliers/{supplier_id}")
def delete_supplier(supplier_id: str):
    success, msg = safe_delete_supplier(supplier_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}

# 3. WAREHOUSES
@app.get("/api/warehouses")
def get_warehouses():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM warehouses ORDER BY id ASC").fetchall()
    conn.close()
    return {"warehouses": [dict(r) for r in rows]}

@app.post("/api/warehouses")
def create_warehouse(w: WarehouseModel):
    conn = get_db_connection()
    w_id = w.id or f"WH-{uuid.uuid4().hex[:4].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO warehouses VALUES (?,?,?,?,?,?,?)", (w_id, w.name, w.location, w.capacity, w.current_utilization, w.status, now_str))
    conn.commit()
    conn.close()
    return {"status": "success", "id": w_id}

@app.delete("/api/warehouses/{warehouse_id}")
def delete_warehouse(warehouse_id: str):
    success, msg = safe_delete_warehouse(warehouse_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}

# 4. INVENTORY
@app.get("/api/inventory")
def get_inventory():
    conn = get_db_connection()
    rows = conn.execute("""
    SELECT i.*, p.sku, p.name as product_name, p.unit_cost, w.name as warehouse_name
    FROM inventory i
    JOIN products p ON i.product_id = p.id
    JOIN warehouses w ON i.warehouse_id = w.id
    ORDER BY i.id ASC
    """).fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        coverage = d["current_stock"] / max(1, d["daily_demand"])
        d["stock_coverage_days"] = round(coverage, 1)
        res.append(d)
    return {"inventory": res}

@app.post("/api/inventory")
def create_inventory(inv: InventoryModel):
    conn = get_db_connection()
    inv_id = inv.id or f"INV-{uuid.uuid4().hex[:6].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cov = inv.current_stock / max(1, inv.daily_demand)
    if inv.current_stock == 0: st = "OUT OF STOCK"
    elif cov < 3: st = "CRITICAL"
    elif cov < 7: st = "LOW"
    else: st = "HEALTHY"

    conn.execute("INSERT INTO inventory VALUES (?,?,?,?,?,?,?,?)", (inv_id, inv.product_id, inv.warehouse_id, inv.current_stock, inv.daily_demand, inv.safety_stock, st, now_str))
    conn.commit()
    conn.close()
    return {"status": "success", "id": inv_id}

# 5. SHIPMENTS
@app.get("/api/shipments")
def get_shipments():
    return {"shipments": fetch_shipments()}

@app.post("/api/shipments")
def create_shipment(s: ShipmentModel):
    conn = get_db_connection()
    s_id = s.id or f"SHP{uuid.uuid4().hex[:4].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
    INSERT INTO shipments (id, supplier_id, product_id, quantity, origin, destination_warehouse_id, expected_delivery, actual_delivery, status, delay_duration, delay_reason, expected_new_delivery_date, created_at, last_updated)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (s_id, s.supplier_id, s.product_id, s.quantity, s.origin, s.destination_warehouse_id, s.expected_delivery, s.actual_delivery, s.status, s.delay_duration, s.delay_reason, s.expected_new_delivery_date, now_str, now_str))
    conn.commit()
    conn.close()
    return {"status": "success", "id": s_id}

# 6. ORDERS
@app.get("/api/orders")
def get_orders():
    return {"orders": fetch_orders()}

@app.post("/api/orders")
def create_order(o: OrderModel):
    conn = get_db_connection()
    o_id = o.id or f"ORD{uuid.uuid4().hex[:4].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", (o_id, o.customer_id, o.product_id, o.quantity, o.order_date, o.required_delivery_date, o.status, o.priority, now_str))
    conn.commit()
    conn.close()
    return {"status": "success", "id": o_id}

# 7. CUSTOMERS
@app.get("/api/customers")
def get_customers():
    return {"customers": fetch_customers()}

@app.post("/api/customers")
def create_customer(c: CustomerModel):
    conn = get_db_connection()
    c_id = c.id or f"CUST-{uuid.uuid4().hex[:4].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO customers VALUES (?,?,?,?,?,?)", (c_id, c.name, c.company, c.email, c.priority, now_str))
    conn.commit()
    conn.close()
    return {"status": "success", "id": c_id}

@app.delete("/api/customers/{customer_id}")
def delete_customer(customer_id: str):
    success, msg = safe_delete_customer(customer_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}

# 8. ADMIN USER MANAGEMENT
@app.get("/api/admin/users")
def get_users():
    conn = get_db_connection()
    rows = conn.execute("SELECT id, username, name, email, role, status, created_at FROM users ORDER BY id ASC").fetchall()
    conn.close()
    return {"users": [dict(r) for r in rows]}

@app.post("/api/admin/users")
def create_user(u: UserModel):
    conn = get_db_connection()
    u_id = u.id or f"USR-{uuid.uuid4().hex[:4].upper()}"
    pw_hash = hash_password(u.password or "password123")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)", (u_id, u.username, pw_hash, u.name, u.email, u.role, u.status, now_str))
    conn.commit()
    conn.close()
    return {"status": "success", "id": u_id}

@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: str):
    success, msg = safe_delete_user(user_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}

# DISRUPTIONS LIST
@app.get("/api/disruptions")
def get_disruptions():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM disruptions ORDER BY created_at DESC").fetchall()
    conn.close()
    return {"disruptions": [dict(r) for r in rows]}

# NOTIFICATIONS API
@app.get("/api/notifications")
def get_notifications_api():
    return {"notifications": get_all_notifications()}

@app.get("/api/notifications/templates")
def get_notification_templates_api():
    return {"templates": get_templates()}

@app.post("/api/notifications")
def send_notification_api(req: NotificationRequest):
    notif = create_notification(req.sender, req.recipient, req.subject, req.message, req.reason, req.related_shipment_id, req.related_order_id, status="SENT")
    return {"status": "success", "notification": notif}

# REPORTS & PDF EXPORT
@app.get("/api/reports")
def get_reports_api():
    return {"reports": get_reports_list()}

@app.post("/api/reports/generate")
def generate_report_api(req: ReportGenRequest):
    rep = generate_report(req.period, generated_by="Lead Ops Manager")
    return {"status": "success", "report": rep}

@app.get("/api/reports/{report_id}/pdf")
def download_pdf_report(report_id: str):
    pdf_bytes = generate_pdf_bytes(report_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Supply_Chain_Report_{report_id}.pdf"}
    )

# ESCALATIONS MANAGEMENT
@app.get("/api/escalations")
def get_escalations_api():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM escalations ORDER BY created_at DESC").fetchall()
    conn.close()
    return {"escalations": [dict(r) for r in rows]}

@app.post("/api/escalations")
def create_escalation_api(req: EscalationRequest):
    conn = get_db_connection()
    esc_id = f"ESC-{uuid.uuid4().hex[:4].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO escalations VALUES (?,?,?,?,?,?,?)", (esc_id, req.reason, req.severity, req.related_disruption_id, "PENDING", req.assigned_to or "Lead Ops Manager", now_str))
    conn.commit()
    conn.close()
    return {"status": "success", "id": esc_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
