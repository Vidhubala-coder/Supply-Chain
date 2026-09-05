"""
tests/test_enterprise.py
Unit tests for Enterprise Control Tower modules:
Authentication, SQLite CRUD, Relational Safety Checks, Notifications, PDF Reports, Escalations, and AI Problem Analysis.
"""

import unittest
from fastapi.testclient import TestClient
from app import app

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

    def test_authentication_flow(self):
        # Successful Admin Login
        res = self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["session"]["role"], "ADMIN")
        token = data["session"]["session_token"]

        # Verify Me endpoint
        headers = {"Authorization": f"Bearer {token}"}
        me_res = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["username"], "admin")

        # Invalid Login
        fail_res = self.client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
        self.assertEqual(fail_res.status_code, 401)

        # Operations Manager Login
        mgr_res = self.client.post("/api/auth/login", json={"username": "manager", "password": "manager123"})
        self.assertEqual(mgr_res.status_code, 200)
        self.assertEqual(mgr_res.json()["session"]["role"], "OPERATIONS MANAGER")

    def test_products_crud_and_safe_deletion(self):
        # Fetch Products
        res = self.client.get("/api/products")
        self.assertEqual(res.status_code, 200)
        products = res.json()["products"]
        self.assertTrue(len(products) >= 20)

        # Attempt to delete referenced product (should fail cleanly)
        ref_p_id = products[0]["id"]
        del_res = self.client.delete(f"/api/products/{ref_p_id}")
        self.assertEqual(del_res.status_code, 400)
        self.assertTrue("referenced by" in del_res.json()["detail"])

        # Create new unreferenced product & delete safely
        new_prd = {
            "id": "PRD-TEST-999",
            "name": "Test Prototype Sensor",
            "sku": "SKU-TEST-999",
            "category": "Testing",
            "supplier_id": "SUP-101",
            "unit_cost": 99.9,
            "reorder_level": 10
        }
        c_res = self.client.post("/api/products", json=new_prd)
        self.assertEqual(c_res.status_code, 200)

        safe_del_res = self.client.delete("/api/products/PRD-TEST-999")
        self.assertEqual(safe_del_res.status_code, 200)
        self.assertEqual(safe_del_res.json()["status"], "success")

    def test_suppliers_crud(self):
        res = self.client.get("/api/suppliers")
        self.assertEqual(res.status_code, 200)
        suppliers = res.json()["suppliers"]
        self.assertTrue(len(suppliers) >= 8)

    def test_warehouses_crud(self):
        res = self.client.get("/api/warehouses")
        self.assertEqual(res.status_code, 200)
        warehouses = res.json()["warehouses"]
        self.assertTrue(len(warehouses) >= 4)

    def test_inventory_and_stock_coverage(self):
        res = self.client.get("/api/inventory")
        self.assertEqual(res.status_code, 200)
        inventory = res.json()["inventory"]
        self.assertTrue(len(inventory) >= 100)
        first = inventory[0]
        self.assertTrue("stock_coverage_days" in first)

    def test_shipments_and_orders(self):
        ship_res = self.client.get("/api/shipments")
        self.assertEqual(ship_res.status_code, 200)
        self.assertTrue(len(ship_res.json()["shipments"]) >= 30)

        ord_res = self.client.get("/api/orders")
        self.assertEqual(ord_res.status_code, 200)
        self.assertTrue(len(ord_res.json()["orders"]) >= 100)

    def test_customers_crud(self):
        cust_res = self.client.get("/api/customers")
        self.assertEqual(cust_res.status_code, 200)
        self.assertTrue(len(cust_res.json()["customers"]) >= 80)

    def test_admin_users(self):
        usr_res = self.client.get("/api/admin/users")
        self.assertEqual(usr_res.status_code, 200)
        self.assertTrue(len(usr_res.json()["users"]) >= 2)

    def test_notifications_system(self):
        tmpl_res = self.client.get("/api/notifications/templates")
        self.assertEqual(tmpl_res.status_code, 200)
        self.assertTrue("customer_delay_notification" in tmpl_res.json()["templates"])

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
        self.assertTrue(len(list_res.json()["notifications"]) >= 1)

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
