"""
backend/auth.py
Manager Authentication & Session Management System.
All users authenticate as MANAGER against the relational database.
"""

import os
import re
import uuid
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from fastapi import HTTPException, Header

from backend.database import get_db_connection, hash_password, verify_password

# In-memory session store mapping session_token -> user dict
SESSIONS: Dict[str, Dict[str, Any]] = {}

def register_user(name: str, email: str, password: str, confirm_password: str, department: Optional[str] = None, phone: Optional[str] = None) -> Tuple[bool, str]:
    if not name or not email or not password or not confirm_password:
        return False, "Please complete all required fields."

    email_clean = email.strip().lower()

    # Validate email format
    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_regex, email_clean):
        return False, "Please enter a valid email address."

    # Password match
    if password != confirm_password:
        return False, "Passwords do not match."

    # Minimum password strength
    if len(password) < 6:
        return False, "Password does not meet the required security criteria."

    # Check duplicate email
    conn = get_db_connection()
    c = conn.cursor()
    existing = c.execute("SELECT id FROM users WHERE LOWER(email) = ? OR LOWER(username) = ?", (email_clean, email_clean)).fetchone()
    if existing:
        conn.close()
        return False, "An account with this email already exists."

    user_id = f"USR-{uuid.uuid4().hex[:6].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pw_hash = hash_password(password)
    default_role = "MANAGER"

    c.execute("""
        INSERT INTO users (id, username, password_hash, name, email, role, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, email_clean, pw_hash, name.strip(), email_clean, default_role, "ACTIVE", now_str))
    conn.commit()
    conn.close()

    return True, "Account created successfully. Please sign in with your registered credentials."

def authenticate_user(email_input: str, password_input: str) -> Tuple[Optional[Dict[str, Any]], str]:
    if not email_input or not password_input:
        return None, "Invalid email or password."

    email_clean = email_input.strip().lower()

    # Authenticate Manager against SQLite DB
    conn = get_db_connection()
    c = conn.cursor()
    row = c.execute("""
        SELECT id, username, password_hash, name, email, role, status 
        FROM users 
        WHERE LOWER(email) = ? OR LOWER(username) = ?
    """, (email_clean, email_clean)).fetchone()
    conn.close()

    if not row:
        return None, "Invalid email or password."

    user = dict(row)
    if user["status"] != "ACTIVE":
        return None, "Invalid email or password."

    if verify_password(password_input, user["password_hash"]):
        token = str(uuid.uuid4())
        session_data = {
            "session_token": token,
            "user_id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "email": user["email"],
            "role": "MANAGER",
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
        }
        SESSIONS[token] = session_data
        return session_data, "Login successful"

    return None, "Invalid email or password."

def get_current_session(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    session = SESSIONS.get(token)
    if not session:
        return None
    if datetime.fromisoformat(session["expires_at"]) < datetime.now():
        del SESSIONS[token]
        return None
    return session

def invalidate_session(token: str) -> bool:
    if token in SESSIONS:
        del SESSIONS[token]
        return True
    return False
