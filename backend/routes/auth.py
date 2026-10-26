"""POST /auth/login and user management (FR1)."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend.auth import create_token, current_user, hash_password, require_role, verify_password
from backend.db import get_db
from backend.schemas import LoginIn, UserIn

router = APIRouter(tags=["Auth"])


@router.post("/auth/login")
def login(body: LoginIn, db=Depends(get_db)):
    row = db.execute("SELECT * FROM users WHERE username = ?", (body.username,)).fetchone()
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Wrong username or password")
    return {"token": create_token(row["user_id"], row["role"]),
            "user": {"user_id": row["user_id"], "username": row["username"], "role": row["role"]}}


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return user


@router.post("/users", status_code=201)
def create_user(body: UserIn, db=Depends(get_db), _=Depends(require_role("admin"))):
    try:
        with db:
            cur = db.execute("INSERT INTO users (username, role, password_hash) VALUES (?, ?, ?)",
                             (body.username, body.role, hash_password(body.password)))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Username already taken")
    return {"user_id": cur.lastrowid, "username": body.username, "role": body.role}
