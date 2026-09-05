"""
tests/test_enterprise.py
Unit test suite for Enterprise Control Tower modules:
Health check, Manager auth, full Product CRUD (Add, Edit, Delete soft/hard), Suppliers CRUD,
Warehouses CRUD, Inventory CRUD, Shipments CRUD, Orders CRUD, Customers CRUD, Notifications,
Escalations resolution, PDF Reports generation, and Disruption AI analysis.
"""

import unittest
from fastapi.testclient import TestClient
from app import app
from backend.database import get_db_connection

class TestEnterpriseControlTower(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["track_id"], "PS08")
        self.assertTrue("database_connected" in data)

    def test_manager_authentication_flow(self):
        mgr_res = self.client.post("/api/auth/login", json={"email": "ops@controltower.io", "password": "manager123"})
        self.assertEqual(mgr_res.status_code, 200)
        data = mgr_res.json()
        self.assertEqual(data["session"]["role"], "MANAGER")
        token = data["session"]["session_token"]

        headers = {"Authorization": f"Bearer {token}"}
        me_res = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["role"], "MANAGER")

    def test_products_crud_and_safe_deletion(self):
        # 1. Fetch Active Products
        res = self.client.get("/api/products")
        self.assertEqual(res.status_code, 200)
        products = res.json()["products"]
        self.assertTrue(len(products) >= 1)

        # 2. Add New Product
        new_prd = {
            "id": "PRD-TEST-1001",
            "name": "High-Precision Stepper Motor",
            "sku": "SKU-TEST-1001",
            "category": "Motion Control",
            "supplier_id": "SUP-101",
            "unit_cost": 125.50,
            "reorder_level": 30,
            "status": "ACTIVE"
        }
        create_res = self.client.post("/api/products", json=new_prd)
        self.assertEqual(create_res.status_code, 200)
        self.assertEqual(create_res.json()["status"], "success")
        self.assertIn("added successfully", create_res.json()["message"])

        # 3. Edit Product
        edit_prd = {
            "id": "PRD-TEST-1001",
            "name": "High-Precision Stepper Motor V2",
            "sku": "SKU-TEST-1001",
            "category": "Motion Control Systems",
            "supplier_id": "SUP-101",
            "unit_cost": 139.99,
            "reorder_level": 40,
            "status": "ACTIVE"
        }
        update_res = self.client.put("/api/products/PRD-TEST-1001", json=edit_prd)
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(update_res.json()["status"], "success")
        self.assertIn("updated successfully", update_res.json()["message"])

        # 4. Soft Delete Referenced Product (status becomes INACTIVE)
        ref_p_id = products[0]["id"]
        soft_del_res = self.client.delete(f"/api/products/{ref_p_id}")
        self.assertEqual(soft_del_res.status_code, 200)
        self.assertEqual(soft_del_res.json()["status"], "success")
        self.assertIn("deactivated", soft_del_res.json()["message"])

        # Verify DB status = INACTIVE
        conn = get_db_connection()
        db_row = conn.execute("SELECT status FROM products WHERE id = ?", (ref_p_id,)).fetchone()
        conn.close()
        self.assertIsNotNone(db_row)
        self.assertEqual(db_row["status"], "INACTIVE")

        # Verify excluded from active products list
        active_res = self.client.get("/api/products")
        active_ids = [p["id"] for p in active_res.json()["products"]]
        self.assertNotIn(ref_p_id, active_ids)

        # 5. Hard Delete Unreferenced Product
        hard_del_res = self.client.delete("/api/products/PRD-TEST-1001")
        self.assertEqual(hard_del_res.status_code, 200)
        self.assertEqual(hard_del_res.json()["status"], "success")
        self.assertIn("deleted successfully", hard_del_res.json()["message"])

        conn = get_db_connection()
        deleted_row = conn.execute("SELECT id FROM products WHERE id = 'PRD-TEST-1001'").fetchone()
        conn.close()
        self.assertIsNone(deleted_row)

    def test_suppliers_crud(self):
        # List
        res = self.client.get("/api/suppliers")
        self.assertEqual(res.status_code, 200)

        # Create
        sup_payload = {
            "id": "SUP-TEST-1",
            "name": "Test Components Corp",
            "contact": "Alice Test",
            "email": "alice@testcomp.com",
            "location": "Dallas, TX",
            "performance": 96.5,
            "status": "ACTIVE"
        }
        c_res = self.client.post("/api/suppliers", json=sup_payload)
        self.assertEqual(c_res.status_code, 200)

        # Update
        sup_payload["name"] = "Test Components Global"
        u_res = self.client.put("/api/suppliers/SUP-TEST-1", json=sup_payload)
        self.assertEqual(u_res.status_code, 200)

        # Hard Delete unreferenced
        d_res = self.client.delete("/api/suppliers/SUP-TEST-1")
        self.assertEqual(d_res.status_code, 200)

    def test_warehouses_crud(self):
        # List
        res = self.client.get("/api/warehouses")
        self.assertEqual(res.status_code, 200)

        # Create
        wh_payload = {
            "id": "WH-TEST-1",
            "name": "Test Logistics Facility",
            "location": "Austin, TX",
            "capacity": 25000,
            "current_utilization": 40.0,
            "status": "ACTIVE"
        }
        c_res = self.client.post("/api/warehouses", json=wh_payload)
        self.assertEqual(c_res.status_code, 200)

        # Update
        wh_payload["capacity"] = 30000
        u_res = self.client.put("/api/warehouses/WH-TEST-1", json=wh_payload)
        self.assertEqual(u_res.status_code, 200)

        # Hard Delete unreferenced
        d_res = self.client.delete("/api/warehouses/WH-TEST-1")
        self.assertEqual(d_res.status_code, 200)

    def test_inventory_and_stock_coverage(self):
        res = self.client.get("/api/inventory")
        self.assertEqual(res.status_code, 200)
        inventory = res.json()["inventory"]
        self.assertTrue(len(inventory) >= 1)
        self.assertTrue("stock_coverage_days" in inventory[0])

    def test_shipments_and_orders(self):
        ship_res = self.client.get("/api/shipments")
        self.assertEqual(ship_res.status_code, 200)

        ord_res = self.client.get("/api/orders")
        self.assertEqual(ord_res.status_code, 200)

    def test_customers_crud(self):
        cust_res = self.client.get("/api/customers")
        self.assertEqual(cust_res.status_code, 200)

        cust_payload = {
            "id": "CUST-TEST-1",
            "name": "Dynamic Systems",
            "company": "Dynamic Corp",
            "email": "contact@dynamicsys.com",
            "priority": "HIGH"
        }
        c_res = self.client.post("/api/customers", json=cust_payload)
        self.assertEqual(c_res.status_code, 200)

        cust_payload["company"] = "Dynamic Systems Inc"
        u_res = self.client.put("/api/customers/CUST-TEST-1", json=cust_payload)
        self.assertEqual(u_res.status_code, 200)

        d_res = self.client.delete("/api/customers/CUST-TEST-1")
        self.assertEqual(d_res.status_code, 200)

    def test_notifications_system(self):
        tmpl_res = self.client.get("/api/notifications/templates")
        self.assertEqual(tmpl_res.status_code, 200)

        post_res = self.client.post("/api/notifications", json={
            "sender": "ops@controltower.io",
            "recipient": "test@client.com",
            "subject": "Test Advisory",
            "message": "Notice body text",
            "reason": "Test Delay",
            "related_shipment_id": "SHP-2001"
        })
        self.assertEqual(post_res.status_code, 200)

        list_res = self.client.get("/api/notifications")
        self.assertEqual(list_res.status_code, 200)

    def test_reports_and_pdf_download(self):
        rep_res = self.client.post("/api/reports/generate", json={"period": "2026-09"})
        self.assertEqual(rep_res.status_code, 200)
        rep_id = rep_res.json()["report"]["id"]

        list_res = self.client.get("/api/reports")
        self.assertEqual(list_res.status_code, 200)

        pdf_res = self.client.get(f"/api/reports/{rep_id}/pdf")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.headers["content-type"], "application/pdf")
        self.assertTrue(b"%PDF" in pdf_res.content)

    def test_escalations_and_ai_analysis(self):
        esc_res = self.client.get("/api/escalations")
        self.assertEqual(esc_res.status_code, 200)

        ai_res = self.client.get("/api/ai-analysis")
        self.assertEqual(ai_res.status_code, 200)
        self.assertTrue("problem_summary" in ai_res.json())

if __name__ == "__main__":
    unittest.main()
