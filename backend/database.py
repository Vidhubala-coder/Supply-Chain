"""
backend/database.py
Enterprise SQLite Database Layer & Relational Data Management for Control Tower (PS08).
Provides automatic schema creation, data seeding, relational integrity checks, and thread-safe connections.
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "supply_chain.db")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        b'supply_chain_salt_2026',
        100000
    ).hex()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create Tables
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT NOT NULL, -- 'ADMIN' or 'OPERATIONS MANAGER'
        status TEXT DEFAULT 'ACTIVE',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS suppliers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        contact TEXT NOT NULL,
        email TEXT NOT NULL,
        location TEXT NOT NULL,
        status TEXT DEFAULT 'ACTIVE',
        performance REAL DEFAULT 95.0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        sku TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        supplier_id TEXT NOT NULL,
        unit_cost REAL NOT NULL,
        reorder_level INTEGER DEFAULT 50,
        status TEXT DEFAULT 'ACTIVE',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS warehouses (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        location TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        current_utilization REAL DEFAULT 0.0,
        status TEXT DEFAULT 'ACTIVE',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS inventory (
        id TEXT PRIMARY KEY,
        product_id TEXT NOT NULL,
        warehouse_id TEXT NOT NULL,
        current_stock INTEGER NOT NULL,
        daily_demand INTEGER NOT NULL,
        safety_stock INTEGER NOT NULL,
        status TEXT NOT NULL, -- 'HEALTHY', 'LOW', 'CRITICAL', 'OUT OF STOCK'
        last_updated TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS shipments (
        id TEXT PRIMARY KEY,
        supplier_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        origin TEXT NOT NULL,
        destination_warehouse_id TEXT NOT NULL,
        expected_delivery TEXT NOT NULL,
        actual_delivery TEXT,
        status TEXT NOT NULL, -- 'PLANNED', 'IN TRANSIT', 'DELAYED', 'OUT FOR DELIVERY', 'DELIVERED', 'CANCELLED'
        delay_duration INTEGER DEFAULT 0,
        delay_reason TEXT,
        expected_new_delivery_date TEXT,
        created_at TEXT NOT NULL,
        last_updated TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS customers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        company TEXT NOT NULL,
        email TEXT NOT NULL,
        priority TEXT DEFAULT 'NORMAL', -- 'CRITICAL', 'HIGH', 'NORMAL'
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        order_date TEXT NOT NULL,
        required_delivery_date TEXT NOT NULL,
        status TEXT NOT NULL, -- 'PENDING', 'CONFIRMED', 'PROCESSING', 'PARTIALLY_FULFILLED', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'AT_RISK'
        priority TEXT DEFAULT 'NORMAL',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS disruptions (
        id TEXT PRIMARY KEY,
        received_time TEXT NOT NULL,
        source TEXT NOT NULL,
        supplier_id TEXT,
        shipment_id TEXT,
        product_id TEXT,
        severity TEXT NOT NULL, -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
        status TEXT NOT NULL, -- 'NEW', 'ANALYZING', 'ANALYZED', 'ACTION_REQUIRED', 'ESCALATED', 'RESOLVED'
        notice_text TEXT NOT NULL,
        recommended_action TEXT,
        orders_affected INTEGER DEFAULT 0,
        customers_affected INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        sender TEXT NOT NULL,
        recipient TEXT NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        reason TEXT NOT NULL,
        related_shipment_id TEXT,
        related_order_id TEXT,
        status TEXT DEFAULT 'SENT', -- 'DRAFT', 'SENT', 'LOGGED'
        sent_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS escalations (
        id TEXT PRIMARY KEY,
        reason TEXT NOT NULL,
        severity TEXT NOT NULL,
        related_disruption_id TEXT,
        status TEXT DEFAULT 'PENDING', -- 'PENDING', 'IN_REVIEW', 'RESOLVED'
        assigned_to TEXT DEFAULT 'Unassigned',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS reports (
        id TEXT PRIMARY KEY,
        period TEXT NOT NULL,
        title TEXT NOT NULL,
        total_shipments INTEGER NOT NULL,
        delivered_shipments INTEGER NOT NULL,
        delayed_shipments INTEGER NOT NULL,
        cancelled_shipments INTEGER NOT NULL,
        total_orders INTEGER NOT NULL,
        orders_at_risk INTEGER NOT NULL,
        orders_delivered INTEGER NOT NULL,
        customers_impacted INTEGER NOT NULL,
        total_disruptions INTEGER NOT NULL,
        resolved_disruptions INTEGER NOT NULL,
        escalated_disruptions INTEGER NOT NULL,
        inventory_shortages INTEGER NOT NULL,
        generated_by TEXT NOT NULL,
        status TEXT DEFAULT 'COMPLETED',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS decision_logs (
        id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        notice_id TEXT,
        notice_text TEXT,
        stage1_data TEXT,
        stage2_data TEXT,
        stage3_data TEXT,
        recommendation TEXT,
        human_decision TEXT,
        user_name TEXT
    );
    """)
    conn.commit()

    seed_initial_data(conn)
    conn.close()

def load_json_file(filename: str) -> List[Dict[str, Any]]:
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def seed_initial_data(conn: sqlite3.Connection):
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Seed Users
    cursor.execute("SELECT COUNT(*) FROM users WHERE LOWER(email) = 'vidhub657@gmail.com' OR id = 'USR-ADMIN'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?,?,?)", ("USR-ADMIN", "vidhub657@gmail.com", "ENV_MANAGED", "System Administrator", "vidhub657@gmail.com", "ADMIN", "ACTIVE", now_str))

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] <= 1:
        users = [
            ("USR-002", "ops_manager", hash_password("manager123"), "Lead Ops Manager", "ops@controltower.io", "OPERATIONS_MANAGER", "ACTIVE", now_str),
            ("USR-003", "sarah_ops", hash_password("sarah123"), "Sarah Jenkins (Logistics)", "s.jenkins@controltower.io", "OPERATIONS_MANAGER", "ACTIVE", now_str)
        ]
        for u in users:
            cursor.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,?,?,?)", u)

    # 2. Seed Suppliers
    cursor.execute("SELECT COUNT(*) FROM suppliers")
    if cursor.fetchone()[0] == 0:
        json_suppliers = load_json_file("suppliers.json")
        suppliers_list = []
        for i, s in enumerate(json_suppliers):
            s_id = s.get("id", f"SUP-{i+1:03d}")
            name = s.get("name", f"Supplier {i+1}")
            contact = s.get("contact", f"Contact Person {i+1}")
            email = s.get("email", f"info@supplier{i+1}.com")
            location = s.get("region", s.get("location", "Berlin, Germany"))
            perf = float(s.get("reliability_score", 95.0)) * 100 if s.get("reliability_score", 1.0) <= 1.0 else float(s.get("reliability_score", 95.0))
            suppliers_list.append((s_id, name, contact, email, location, "ACTIVE", round(perf, 1), now_str))

        extra_suppliers = [
            ("SUP-005", "Apex Microelectronics Inc", "David Vance", "dvance@apexmicro.com", "Hsinchu, Taiwan", "ACTIVE", 94.5, now_str),
            ("SUP-006", "Global Logistics Freight Co", "Elena Rostova", "erostova@globallog.com", "Rotterdam, Netherlands", "ACTIVE", 91.2, now_str),
            ("SUP-007", "Starlight Materials Ltd", "Klaus Weber", "kweber@starlight.de", "Stuttgart, Germany", "ACTIVE", 98.0, now_str),
            ("SUP-008", "Vanguard Industrial Composites", "Chen Wei", "wchen@vanguardic.cn", "Shenzhen, China", "ACTIVE", 89.5, now_str)
        ]
        for item in extra_suppliers:
            if not any(s[0] == item[0] for s in suppliers_list):
                suppliers_list.append(item)

        cursor.executemany("INSERT INTO suppliers VALUES (?,?,?,?,?,?,?,?)", suppliers_list)

    # 3. Seed Warehouses
    cursor.execute("SELECT COUNT(*) FROM warehouses")
    if cursor.fetchone()[0] == 0:
        warehouses = [
            ("WH-NORTH", "North America Central Hub", "Chicago, IL, USA", 50000, 78.4, "ACTIVE", now_str),
            ("WH-SOUTH", "Southern Logistics Depot", "Atlanta, GA, USA", 35000, 62.1, "ACTIVE", now_str),
            ("WH-EAST", "European Gateway Terminal", "Rotterdam, Netherlands", 60000, 84.5, "ACTIVE", now_str),
            ("WH-WEST", "Asia-Pacific Regional Center", "Singapore Terminal", 45000, 71.0, "ACTIVE", now_str)
        ]
        cursor.executemany("INSERT INTO warehouses VALUES (?,?,?,?,?,?,?)", warehouses)

    # 4. Seed Products
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        json_stock = load_json_file("stock.json")
        products_list = []
        seen_skus = set()
        for i, st in enumerate(json_stock):
            sku = st.get("sku", f"SKU-{i+1:03d}")
            if sku in seen_skus: continue
            seen_skus.add(sku)
            p_id = f"PRD-{sku}"
            name = st.get("name", f"Product {sku}")
            cat = st.get("category", "Electronics")
            sup_id = st.get("supplier_id", "SUP-101")
            cost = float(st.get("unit_cost", 150.0))
            reorder = int(st.get("reorder_point", st.get("reorder_level", 50)))
            products_list.append((p_id, name, sku, cat, sup_id, cost, reorder, "ACTIVE", now_str))

        categories = ["Electronics", "Power Systems", "Sensors", "Structural", "Logistics Hardware"]
        for k in range(len(products_list) + 1, 30):
            sku = f"SKU-20{k:02d}"
            if sku in seen_skus: continue
            seen_skus.add(sku)
            p_id = f"PRD-{sku}"
            name = f"Enterprise Component Model-{k*11}"
            cat = categories[k % len(categories)]
            sup_id = f"SUP-10{(k%5)+1}"
            cost = round(45.0 + (k * 18.5), 2)
            products_list.append((p_id, name, sku, cat, sup_id, cost, 50, "ACTIVE", now_str))

        cursor.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?)", products_list)

    # 5. Seed Inventory
    cursor.execute("SELECT COUNT(*) FROM inventory")
    if cursor.fetchone()[0] == 0:
        json_stock = load_json_file("stock.json")
        inventory_list = []
        for i, st in enumerate(json_stock):
            inv_id = f"INV-{i+1:04d}"
            sku = st.get("sku", "")
            p_id = f"PRD-{sku}" if sku else f"PRD-SKU-{i+1:03d}"
            wh_id = st.get("warehouse_id", "WH-NORTH")
            c_stock = int(st.get("on_hand", st.get("current_stock", 300)))
            d_demand = int(st.get("daily_demand", 30))
            s_stock = int(st.get("safety_stock", 100))
            coverage = c_stock / max(1, d_demand)
            if c_stock == 0: status = "OUT OF STOCK"
            elif coverage < 3: status = "CRITICAL"
            elif coverage < 7: status = "LOW"
            else: status = "HEALTHY"
            inventory_list.append((inv_id, p_id, wh_id, c_stock, d_demand, s_stock, status, now_str))

        wh_ids = ["WH-NORTH", "WH-SOUTH", "WH-EAST", "WH-WEST"]
        cursor.execute("SELECT id FROM products")
        all_prd_ids = [r[0] for r in cursor.fetchall()]

        item_count = len(inventory_list)
        for p_id in all_prd_ids:
            for wh_id in wh_ids:
                if not any(inv[1] == p_id and inv[2] == wh_id for inv in inventory_list):
                    item_count += 1
                    c_stock = (item_count * 37) % 650
                    d_demand = max(5, (item_count * 7) % 45)
                    s_stock = max(20, d_demand * 3)
                    coverage = c_stock / d_demand
                    if c_stock == 0: status = "OUT OF STOCK"
                    elif coverage < 3: status = "CRITICAL"
                    elif coverage < 7: status = "LOW"
                    else: status = "HEALTHY"
                    inventory_list.append((f"INV-{item_count:04d}", p_id, wh_id, c_stock, d_demand, s_stock, status, now_str))

        cursor.executemany("INSERT INTO inventory VALUES (?,?,?,?,?,?,?,?)", inventory_list)

    # 6. Seed Customers
    cursor.execute("SELECT COUNT(*) FROM customers")
    if cursor.fetchone()[0] == 0:
        json_cust = load_json_file("customers.json")
        cust_list = []
        for i, c in enumerate(json_cust):
            c_id = c.get("customer_id", c.get("id", f"CUST-{i+1:03d}"))
            name = c.get("name", f"Customer {i+1}")
            comp = c.get("company", c.get("name", f"Enterprise Co {i+1}"))
            email = c.get("contact", c.get("email", f"procurement@company{i+1}.com"))
            priority = c.get("tier", c.get("criticality", "NORMAL")).upper()
            if priority == "VIP": priority = "CRITICAL"
            elif priority == "STANDARD": priority = "NORMAL"
            cust_list.append((c_id, name, comp, email, priority, now_str))

        priorities = ["CRITICAL", "HIGH", "NORMAL"]
        for j in range(len(cust_list) + 1, 85):
            c_id = f"CUST-{j:03d}"
            name = f"Executive Manager {j}"
            comp = f"Global Tech Partner {j}"
            email = f"contact@partner{j}.org"
            prio = priorities[j % 3]
            cust_list.append((c_id, name, comp, email, prio, now_str))

        cursor.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", cust_list)

    # 7. Seed Shipments
    cursor.execute("SELECT COUNT(*) FROM shipments")
    if cursor.fetchone()[0] == 0:
        json_ship = load_json_file("shipments.json")
        shipments_list = []
        statuses = ["IN TRANSIT", "DELAYED", "PLANNED", "DELIVERED", "OUT FOR DELIVERY"]
        for i, sh in enumerate(json_ship):
            s_id = sh.get("shipment_id", sh.get("id", f"SHP{i+101}"))
            sup_id = sh.get("supplier_id", "SUP-101")
            sku = sh.get("sku", "SKU-1001")
            p_id = f"PRD-{sku}"
            qty = int(sh.get("qty", sh.get("quantity", 500)))
            origin = sh.get("origin", "Tokyo, Japan")
            wh_id = sh.get("destination_warehouse", sh.get("destination", "WH-NORTH"))
            exp_del = sh.get("eta", sh.get("expected_delivery", "2026-09-12"))
            status = sh.get("status", "IN TRANSIT").upper()
            if status not in ["PLANNED", "IN TRANSIT", "DELAYED", "OUT FOR DELIVERY", "DELIVERED", "CANCELLED"]:
                status = "IN TRANSIT"
            act_del = "2026-09-04" if status == "DELIVERED" else None
            delay_dur = 7 if status == "DELAYED" else 0
            delay_rsn = "Port congestion and carrier delay" if status == "DELAYED" else None
            exp_new = "2026-09-19" if status == "DELAYED" else None
            shipments_list.append((s_id, sup_id, p_id, qty, origin, wh_id, exp_del, act_del, status, delay_dur, delay_rsn, exp_new, now_str, now_str))

        for k in range(len(shipments_list) + 1, 35):
            s_id = f"SHP{k+100}"
            sup_id = f"SUP-10{(k%5)+1}"
            sku = f"SKU-10{(k%9)+1:02d}"
            p_id = f"PRD-{sku}"
            qty = (k * 150) % 2000 + 300
            st = statuses[k % len(statuses)]
            exp = f"2026-09-{(k%20)+5:02d}"
            act = f"2026-09-{(k%5)+1:02d}" if st == "DELIVERED" else None
            d_dur = 5 if st == "DELAYED" else 0
            d_rsn = "Customs inspection hold" if st == "DELAYED" else None
            d_new = f"2026-09-{(k%20)+10:02d}" if st == "DELAYED" else None
            shipments_list.append((s_id, sup_id, p_id, qty, "Frankfurt Depot", "WH-EAST", exp, act, st, d_dur, d_rsn, d_new, now_str, now_str))

        cursor.executemany("INSERT INTO shipments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", shipments_list)

    # 8. Seed Orders
    cursor.execute("SELECT COUNT(*) FROM orders")
    if cursor.fetchone()[0] == 0:
        json_ord = load_json_file("orders.json")
        orders_list = []
        statuses = ["PENDING", "CONFIRMED", "PROCESSING", "PARTIALLY_FULFILLED", "SHIPPED", "DELIVERED", "AT_RISK"]
        for i, o in enumerate(json_ord):
            o_id = o.get("order_id", o.get("id", f"ORD{i+1001}"))
            c_id = o.get("customer_id", "CUST-301")
            sku = o.get("sku", "SKU-1001")
            p_id = f"PRD-{sku}"
            qty = int(o.get("qty", o.get("quantity", 50)))
            ord_date = o.get("order_date", "2026-09-01")
            req_date = o.get("promised_date", o.get("delivery_deadline", o.get("required_delivery_date", "2026-09-10")))
            st = o.get("status", "PENDING").upper()
            prio = o.get("priority", "NORMAL").upper()
            orders_list.append((o_id, c_id, p_id, qty, ord_date, req_date, st, prio, now_str))

        cursor.execute("SELECT id FROM customers")
        all_c_ids = [r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT id FROM products")
        all_p_ids = [r[0] for r in cursor.fetchall()]

        for m in range(len(orders_list) + 1, 105):
            o_id = f"ORD{m+1000}"
            c_id = all_c_ids[m % len(all_c_ids)]
            p_id = all_p_ids[m % len(all_p_ids)]
            qty = (m * 12) % 150 + 10
            ord_d = "2026-09-02"
            req_d = f"2026-09-{(m%25)+6:02d}"
            st = statuses[m % len(statuses)]
            prio = "CRITICAL" if m % 7 == 0 else ("HIGH" if m % 3 == 0 else "NORMAL")
            orders_list.append((o_id, c_id, p_id, qty, ord_d, req_d, st, prio, now_str))

        cursor.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", orders_list)

    # 9. Seed Disruptions
    cursor.execute("SELECT COUNT(*) FROM disruptions")
    if cursor.fetchone()[0] == 0:
        disruptions = [
            ("DIS-1001", "2026-09-05 08:30:00", "Supplier Notice", "SUP-101", "SHP-2001", "PRD-SKU-1001", "HIGH", "ACTION_REQUIRED", "ABC Components informed shipment SHP-2001 containing MCU-32 Ultra Processor delayed by 7 days due to transit breakdown.", "REALLOCATE INVENTORY", 47, 28, now_str),
            ("DIS-1002", "2026-09-04 14:15:00", "Warehouse Alert", "SUP-102", "SHP-2003", "PRD-SKU-1003", "MEDIUM", "RESOLVED", "WH-SOUTH unexpected throughput bottleneck resolved via shift reallocation.", "EXPEDITE SHIPMENT", 12, 8, now_str),
            ("DIS-1003", "2026-09-03 11:00:00", "Carrier Status", "SUP-105", "SHP-2005", "PRD-SKU-1008", "CRITICAL", "ESCALATED", "Port clearance delay at Rotterdam Terminal for MEMS-6D Motion Sensors.", "ESCALATE TO MANAGEMENT", 34, 19, now_str)
        ]
        cursor.executemany("INSERT INTO disruptions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", disruptions)

    # 10. Seed Notifications
    cursor.execute("SELECT COUNT(*) FROM notifications")
    if cursor.fetchone()[0] == 0:
        notifications = [
            ("NOTIF-001", "ops@controltower.io", "procurement@teslatech.com", "Delivery Schedule Advisory — Order ORD-5001", "Dear Tesla Tech Procurement Team,\n\nDue to an upstream component delay on SHP-2001, Order ORD-5001 has been prioritized for partial shipment.", "Order Delay Mitigation", "SHP-2001", "ORD-5001", "SENT", now_str),
            ("NOTIF-002", "ops@controltower.io", "orders@apexmicro.tw", "Expedite Request for Shipment SHP-2001", "Dear Apex Microelectronics,\n\nPlease provide immediate status update and air-freight expedite quotes for SHP-2001.", "Supplier Expedite Request", "SHP-2001", None, "SENT", now_str)
        ]
        cursor.executemany("INSERT INTO notifications VALUES (?,?,?,?,?,?,?,?,?,?)", notifications)

    # 11. Seed Escalations
    cursor.execute("SELECT COUNT(*) FROM escalations")
    if cursor.fetchone()[0] == 0:
        escalations = [
            ("ESC-001", "Ambiguous supplier reference 'Apex' matched 2 candidate entities.", "MEDIUM", "DIS-1003", "PENDING", "Alex Rivera (Systems)", now_str),
            ("ESC-002", "Critical contradiction: Carrier claims delivery while warehouse reports 0 units received.", "CRITICAL", "DIS-1001", "IN_REVIEW", "Lead Ops Manager", now_str)
        ]
        cursor.executemany("INSERT INTO escalations VALUES (?,?,?,?,?,?,?)", escalations)

    # 12. Seed Reports
    cursor.execute("SELECT COUNT(*) FROM reports")
    if cursor.fetchone()[0] == 0:
        reports = [
            ("REP-2026-08", "2026-08", "August 2026 Monthly Supply Chain Performance Report", 34, 28, 4, 2, 102, 12, 88, 14, 5, 4, 1, 3, "Executive Admin", "COMPLETED", now_str)
        ]
        cursor.executemany("INSERT INTO reports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", reports)

    conn.commit()

# Unified Data Accessors (backed by SQLite with 100% backward-compatible key aliases)
def fetch_suppliers() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM suppliers").fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        d["supplier_id"] = d["id"]
        d["reliability_score"] = round(d["performance"] / 100.0, 2)
        d["region"] = d["location"]
        res.append(d)
    return res

def fetch_stock() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    query = """
    SELECT 
        MIN(i.id) as id,
        p.sku,
        p.name,
        p.category,
        p.supplier_id,
        MIN(i.warehouse_id) as warehouse_id,
        SUM(i.current_stock) as current_stock,
        MAX(i.daily_demand) as daily_demand,
        SUM(i.safety_stock) as safety_stock,
        p.unit_cost,
        p.reorder_level
    FROM inventory i
    JOIN products p ON i.product_id = p.id
    GROUP BY p.sku
    """
    rows = conn.execute(query).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        coverage = d["current_stock"] / max(1, d["daily_demand"])
        d["on_hand"] = d["current_stock"]
        d["reserved"] = d["safety_stock"]
        d["reorder_point"] = d["reorder_level"]
        d["stock_coverage_days"] = round(coverage, 1)
        result.append(d)
    return result

def fetch_shipments() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    query = """
    SELECT 
        s.id,
        s.supplier_id,
        p.sku,
        p.name as product_name,
        s.quantity,
        s.origin,
        s.destination_warehouse_id as destination_warehouse,
        s.expected_delivery,
        s.actual_delivery,
        s.status,
        s.delay_duration,
        s.delay_reason,
        s.expected_new_delivery_date
    FROM shipments s
    LEFT JOIN products p ON s.product_id = p.id
    """
    rows = conn.execute(query).fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        d["shipment_id"] = d["id"]
        d["qty"] = d["quantity"]
        d["eta"] = d["expected_delivery"]
        d["carrier"] = "Express Freight"
        res.append(d)
    return res

def fetch_orders() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    query = """
    SELECT 
        o.id,
        o.customer_id,
        p.sku,
        p.name as product_name,
        o.quantity,
        o.order_date,
        o.required_delivery_date,
        o.status,
        o.priority,
        c.name as customer_name,
        c.company as customer_company,
        c.priority as customer_criticality
    FROM orders o
    LEFT JOIN products p ON o.product_id = p.id
    LEFT JOIN customers c ON o.customer_id = c.id
    """
    rows = conn.execute(query).fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        d["order_id"] = d["id"]
        d["qty"] = d["quantity"]
        d["promised_date"] = d["required_delivery_date"]
        d["delivery_deadline"] = d["required_delivery_date"]
        prio = d["priority"].upper() if d.get("priority") else "NORMAL"
        d["customer_tier"] = "VIP" if prio == "CRITICAL" else ("High" if prio == "HIGH" else "Standard")
        d["urgency_score"] = 85 if prio == "CRITICAL" else (65 if prio == "HIGH" else 40)
        res.append(d)
    return res

def fetch_customers() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM customers").fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        d["customer_id"] = d["id"]
        d["criticality"] = d.get("priority", "NORMAL")
        d["tier"] = "VIP" if d.get("priority") == "CRITICAL" else "Standard"
        res.append(d)
    return res

# Safe Deletion Handlers with Relational Integrity Safeguards
def safe_delete_product(product_id: str) -> Tuple[bool, str]:
    conn = get_db_connection()
    c = conn.cursor()

    inv_count = c.execute("SELECT COUNT(*) FROM inventory WHERE product_id = ?", (product_id,)).fetchone()[0]
    if inv_count > 0:
        conn.close()
        return False, f"Product {product_id} is referenced by {inv_count} active inventory record(s). Deletion blocked to maintain database integrity."

    shp_count = c.execute("SELECT COUNT(*) FROM shipments WHERE product_id = ?", (product_id,)).fetchone()[0]
    if shp_count > 0:
        conn.close()
        return False, f"Product {product_id} is referenced by {shp_count} active shipment(s). Deletion blocked."

    ord_count = c.execute("SELECT COUNT(*) FROM orders WHERE product_id = ?", (product_id,)).fetchone()[0]
    if ord_count > 0:
        conn.close()
        return False, f"Product {product_id} is referenced by {ord_count} active customer order(s). Deletion blocked."

    c.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return True, f"Product {product_id} successfully deleted."

def safe_delete_supplier(supplier_id: str) -> Tuple[bool, str]:
    conn = get_db_connection()
    c = conn.cursor()

    prd_count = c.execute("SELECT COUNT(*) FROM products WHERE supplier_id = ?", (supplier_id,)).fetchone()[0]
    if prd_count > 0:
        conn.close()
        return False, f"Supplier {supplier_id} supplies {prd_count} active product(s). Deletion blocked to protect relational integrity."

    shp_count = c.execute("SELECT COUNT(*) FROM shipments WHERE supplier_id = ?", (supplier_id,)).fetchone()[0]
    if shp_count > 0:
        conn.close()
        return False, f"Supplier {supplier_id} has {shp_count} active shipment record(s). Deletion blocked."

    c.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
    conn.commit()
    conn.close()
    return True, f"Supplier {supplier_id} successfully deleted."

def safe_delete_warehouse(warehouse_id: str) -> Tuple[bool, str]:
    conn = get_db_connection()
    c = conn.cursor()

    inv_count = c.execute("SELECT COUNT(*) FROM inventory WHERE warehouse_id = ?", (warehouse_id,)).fetchone()[0]
    if inv_count > 0:
        conn.close()
        return False, f"Warehouse {warehouse_id} currently holds {inv_count} active inventory stock allocation(s). Deletion blocked."

    c.execute("DELETE FROM warehouses WHERE id = ?", (warehouse_id,))
    conn.commit()
    conn.close()
    return True, f"Warehouse {warehouse_id} successfully deleted."

def safe_delete_customer(customer_id: str) -> Tuple[bool, str]:
    conn = get_db_connection()
    c = conn.cursor()

    ord_count = c.execute("SELECT COUNT(*) FROM orders WHERE customer_id = ?", (customer_id,)).fetchone()[0]
    if ord_count > 0:
        conn.close()
        return False, f"Customer {customer_id} has {ord_count} placed order(s). Deletion blocked."

    c.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()
    return True, f"Customer {customer_id} successfully deleted."

def safe_delete_user(user_id: str) -> Tuple[bool, str]:
    conn = get_db_connection()
    c = conn.cursor()

    if user_id == "USR-ADMIN" or user_id.lower() == "vidhub657@gmail.com":
        conn.close()
        return False, "The primary administrator account (vidhub657@gmail.com) is protected and cannot be deleted."

    user_row = c.execute("SELECT role, email FROM users WHERE id = ? OR LOWER(email) = ?", (user_id, user_id.lower())).fetchone()
    if user_row:
        email = user_row["email"].lower()
        if email == "vidhub657@gmail.com":
            conn.close()
            return False, "The primary administrator account (vidhub657@gmail.com) is protected and cannot be deleted."

    admin_count = c.execute("SELECT COUNT(*) FROM users WHERE role = 'ADMIN'").fetchone()[0]

    if user_row and user_row["role"] == "ADMIN" and admin_count <= 1:
        conn.close()
        return False, "Cannot delete the sole remaining ADMIN user in the system."

    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True, f"User {user_id} deleted successfully."

def toggle_user_status(user_id: str, new_status: str) -> Tuple[bool, str]:
    conn = get_db_connection()
    c = conn.cursor()

    user_row = c.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    if user_row and user_row["email"].lower() == "vidhub657@gmail.com":
        conn.close()
        return False, "The primary administrator account cannot be deactivated."

    c.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    return True, f"User {user_id} status updated to {new_status}."
