"""
tests/test_auth.py
Unit test suite verifying Manager authentication architecture:
Manager registration flow, duplicate email validation, invalid email handling,
password mismatch, password strength validation, manager login, invalid credentials handling,
session logout, and protected route access.
"""

import unittest
from fastapi.testclient import TestClient
from app import app
from backend.database import get_db_connection

class TestManagerAuthenticationSuite(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Clean up test accounts to ensure test idempotency
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE email IN ('jane.dev@example.com', 'bob.analyst@example.com', 'sarah.connor@example.com', 'dup.test@example.com')")
        conn.commit()
        conn.close()

    def test_01_manager_registration_works(self):
        payload = {
            "name": "Jane Manager",
            "email": "jane.dev@example.com",
            "password": "securepassword123",
            "confirm_password": "securepassword123",
            "department": "Supply Operations"
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")

    def test_02_new_registered_manager_can_login(self):
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
        self.assertEqual(data["session"]["role"], "MANAGER")

    def test_03_duplicate_registration_fails(self):
        reg_payload = {
            "name": "Dup Test",
            "email": "dup.test@example.com",
            "password": "password123",
            "confirm_password": "password123"
        }
        self.client.post("/api/auth/register", json=reg_payload)
        res = self.client.post("/api/auth/register", json=reg_payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("already exists", res.json()["detail"])

    def test_04_invalid_email_format_fails(self):
        payload = {
            "name": "Invalid Email",
            "email": "invalid-email-format",
            "password": "password123",
            "confirm_password": "password123"
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("valid email address", res.json()["detail"])

    def test_05_password_mismatch_fails(self):
        payload = {
            "name": "Mismatch Password",
            "email": "mismatch@example.com",
            "password": "password123",
            "confirm_password": "password456"
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("do not match", res.json()["detail"])

    def test_06_weak_password_fails(self):
        payload = {
            "name": "Weak Password",
            "email": "weak@example.com",
            "password": "123",
            "confirm_password": "123"
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("security criteria", res.json()["detail"])

    def test_07_missing_required_fields_fails(self):
        payload = {
            "name": "",
            "email": "missing@example.com",
            "password": "password123",
            "confirm_password": "password123"
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 400)

    def test_08_wrong_password_fails(self):
        res = self.client.post("/api/auth/login", json={
            "email": "ops@controltower.io",
            "password": "wrongpassword"
        })
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid email or password.")

    def test_09_wrong_email_fails(self):
        res = self.client.post("/api/auth/login", json={
            "email": "nonexistent.user@example.com",
            "password": "anyPassword123"
        })
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid email or password.")

    def test_10_logout_and_protected_route_validation(self):
        # Login seeded manager
        login_res = self.client.post("/api/auth/login", json={
            "email": "ops@controltower.io",
            "password": "manager123"
        })
        token = login_res.json()["session"]["session_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Verify session me
        me_res = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["role"], "MANAGER")

        # Logout
        logout_res = self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(logout_res.status_code, 200)

        # Confirm token is invalidated
        invalid_me = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(invalid_me.status_code, 401)

if __name__ == "__main__":
    unittest.main()
