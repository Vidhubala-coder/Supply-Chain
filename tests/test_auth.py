"""
tests/test_auth.py
Unit test suite verifying exact authentication requirements:
User registration flow, reserved admin email (vidhub657@gmail.com),
environment variable ADMIN_PASSWORD validation, RBAC backend protection,
logout, and admin account safety safeguards.
"""

import os
import unittest
from fastapi.testclient import TestClient
from app import app
from backend.database import get_db_connection

class TestAuthenticationSuite(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Clean up test accounts to ensure idempotency
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE email IN ('jane.dev@example.com', 'bob.analyst@example.com', 'sarah.connor@example.com')")
        conn.commit()
        conn.close()

    def test_01_user_registration_works(self):
        payload = {
            "name": "Jane Developer",
            "email": "jane.dev@example.com",
            "password": "securepassword123",
            "confirm_password": "securepassword123",
            "department": "Supply Operations"
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")

    def test_02_new_registered_user_can_login(self):
        # Register user
        reg_payload = {
            "name": "Bob Analyst",
            "email": "bob.analyst@example.com",
            "password": "password123",
            "confirm_password": "password123"
        }
        self.client.post("/api/auth/register", json=reg_payload)

        # Login user
        login_res = self.client.post("/api/auth/login", json={
            "email": "bob.analyst@example.com",
            "password": "password123"
        })
        self.assertEqual(login_res.status_code, 200)
        data = login_res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["session"]["role"], "OPERATIONS_MANAGER")

    def test_03_wrong_password_fails(self):
        res = self.client.post("/api/auth/login", json={
            "email": "bob.analyst@example.com",
            "password": "wrongpassword"
        })
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid email or password.")

    def test_04_wrong_email_fails(self):
        res = self.client.post("/api/auth/login", json={
            "email": "nonexistent.user@example.com",
            "password": "anyPassword123"
        })
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid email or password.")

    def test_05_admin_email_cannot_be_registered_normally(self):
        payload = {
            "name": "Fake Admin Attempt",
            "email": "vidhub657@gmail.com",
            "password": "password123",
            "confirm_password": "password123"
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("reserved for the administrator", res.json()["detail"])

        # Test case-insensitive admin email registration attempt
        upper_payload = {
            "name": "Fake Admin Uppercase",
            "email": "VIDHUB657@GMAIL.COM",
            "password": "password123",
            "confirm_password": "password123"
        }
        upper_res = self.client.post("/api/auth/register", json=upper_payload)
        self.assertEqual(upper_res.status_code, 400)
        self.assertIn("reserved for the administrator", upper_res.json()["detail"])

    def test_06_correct_admin_email_and_env_password_grants_admin(self):
        admin_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
        res = self.client.post("/api/auth/login", json={
            "email": "vidhub657@gmail.com",
            "password": admin_pass
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["session"]["role"], "ADMIN")
        self.assertEqual(data["session"]["email"].lower(), "vidhub657@gmail.com")

    def test_07_correct_admin_email_wrong_password_rejected(self):
        res = self.client.post("/api/auth/login", json={
            "email": "vidhub657@gmail.com",
            "password": "definitely_wrong_admin_pass"
        })
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid email or password.")

    def test_08_normal_user_cannot_access_admin_routes(self):
        # Register normal user first
        self.client.post("/api/auth/register", json={
            "name": "Bob Analyst",
            "email": "bob.analyst@example.com",
            "password": "password123",
            "confirm_password": "password123"
        })
        # Login as normal user
        login_res = self.client.post("/api/auth/login", json={
            "email": "bob.analyst@example.com",
            "password": "password123"
        })
        token = login_res.json()["session"]["session_token"]

        headers = {"Authorization": f"Bearer {token}"}
        admin_res = self.client.get("/api/admin/users", headers=headers)
        self.assertEqual(admin_res.status_code, 403)

    def test_09_normal_user_default_role_is_operations_manager(self):
        reg_payload = {
            "name": "Sarah Connor",
            "email": "sarah.connor@example.com",
            "password": "password123",
            "confirm_password": "password123"
        }
        self.client.post("/api/auth/register", json=reg_payload)

        login_res = self.client.post("/api/auth/login", json={
            "email": "sarah.connor@example.com",
            "password": "password123"
        })
        self.assertEqual(login_res.json()["session"]["role"], "OPERATIONS_MANAGER")

    def test_10_admin_can_access_user_management(self):
        admin_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
        login_res = self.client.post("/api/auth/login", json={
            "email": "vidhub657@gmail.com",
            "password": admin_pass
        })
        token = login_res.json()["session"]["session_token"]

        headers = {"Authorization": f"Bearer {token}"}
        users_res = self.client.get("/api/admin/users", headers=headers)
        self.assertEqual(users_res.status_code, 200)
        self.assertTrue(len(users_res.json()["users"]) >= 1)

    def test_11_logout_works(self):
        # Register normal user first
        self.client.post("/api/auth/register", json={
            "name": "Bob Analyst",
            "email": "bob.analyst@example.com",
            "password": "password123",
            "confirm_password": "password123"
        })
        login_res = self.client.post("/api/auth/login", json={
            "email": "bob.analyst@example.com",
            "password": "password123"
        })
        token = login_res.json()["session"]["session_token"]
        headers = {"Authorization": f"Bearer {token}"}

        logout_res = self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(logout_res.status_code, 200)

        # Confirm token is invalidated
        me_res = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 401)

    def test_12_protected_admin_account_cannot_be_deleted(self):
        admin_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
        login_res = self.client.post("/api/auth/login", json={
            "email": "vidhub657@gmail.com",
            "password": admin_pass
        })
        token = login_res.json()["session"]["session_token"]
        headers = {"Authorization": f"Bearer {token}"}

        del_res = self.client.delete("/api/admin/users/USR-ADMIN", headers=headers)
        self.assertEqual(del_res.status_code, 400)
        self.assertIn("protected and cannot be deleted", del_res.json()["detail"])

if __name__ == "__main__":
    unittest.main()
