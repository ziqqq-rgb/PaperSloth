import uuid
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr

from core.database import execute_query, execute_write
from core.security import hash_password, verify_password, create_token, get_current_user

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email:    EmailStr
    password: str
    name:     str = ""

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         dict


# ── Ensure users table exists ─────────────────────────────────────────────────

def _ensure_users_table():
    execute_write("""
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            email         VARCHAR(255) UNIQUE NOT NULL,
            name          VARCHAR(255) DEFAULT '',
            password_hash TEXT NOT NULL,
            role          VARCHAR(20) DEFAULT 'student',
            created_at    TIMESTAMP DEFAULT NOW()
        );
    """)

_ensure_users_table()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest):
    # Check if email already exists
    existing = execute_query(
        "SELECT id FROM users WHERE email = %s", (body.email,), fetch="one"
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())
    execute_write(
        "INSERT INTO users (id, email, name, password_hash) VALUES (%s, %s, %s, %s)",
        (user_id, body.email, body.name, hash_password(body.password)),
    )

    token = create_token(user_id, body.email)
    return {
        "access_token": token,
        "user": {"id": user_id, "email": body.email, "name": body.name, "role": "student"},
    }


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    row = execute_query(
        "SELECT id, email, name, password_hash, role FROM users WHERE email = %s",
        (body.email,),
        fetch="one",
    )
    if not row or not verify_password(body.password, row[3]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(row[0], row[1])
    return {
        "access_token": token,
        "user": {"id": row[0], "email": row[1], "name": row[2], "role": row[4]},
    }


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    row = execute_query(
        "SELECT id, email, name, role, created_at FROM users WHERE id = %s",
        (current_user["id"],),
        fetch="one",
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": row[0], "email": row[1], "name": row[2], "role": row[3], "created_at": str(row[4])}