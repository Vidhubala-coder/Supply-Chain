"""
backend/auth.py
Authentication & Session Management module.
Supports ADMIN and OPERATIONS MANAGER roles with secure PBKDF2/SHA256 password hashing.
"""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, Header, Depends
from backend.database import get_db_connection, verify_password

# In-memory session store mapping session token -> user dict
SESSIONS: Dict[str, Dict[str, Any]] = {}

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    c = conn.cursor()
    row = c.execute("SELECT id, username, password_hash, name, email, role, status FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not row:
        return None

    user = dict(row)
    if user["status"] != "ACTIVE":
        return None

    if verify_password(password, user["password_hash"]):
        token = str(uuid.uuid4())
        session_data = {
            "session_token": token,
            "user_id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
        }
        SESSIONS[token] = session_data
        return session_data

    return None

def get_current_session(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    session = SESSIONS.get(token)
    if not session:
        return None
    # Check expiry
    if datetime.fromisoformat(session["expires_at"]) < datetime.now():
        del SESSIONS[token]
        return None
    return session

def invalidate_session(token: str) -> bool:
    if token in SESSIONS:
        del SESSIONS[token]
        return True
    return False
