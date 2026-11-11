"""Login, farmer sign-up and account management (FR1; self-testing model, Nov 2026)."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend.access import own_farmer_id
from backend.auth import create_token, current_user, hash_password, require_role, verify_password
from backend.db import get_db
from backend.schemas import LoginIn, SignupIn, UserIn, UserPatch

router = APIRouter(tags=["Auth"])


def _user_out(db, row):
    user = {k: row[k] for k in ("user_id", "username", "full_name", "role")}
    if "active" in row.keys():
        user["active"] = bool(row["active"])
    user["farmer_id"] = own_farmer_id(db, user) if user["role"] == "farmer" else None
    return user


@router.post("/auth/login")
def login(body: LoginIn, db=Depends(get_db)):
    row = db.execute("SELECT * FROM users WHERE username = ?", (body.username,)).fetchone()
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Wrong username or password")
    if not row["active"]:
        raise HTTPException(403, "This account has been deactivated; ask the administrator")
    return {"token": create_token(row["user_id"], row["role"]), "user": _user_out(db, row)}


@router.post("/auth/signup", status_code=201)
def signup(body: SignupIn, db=Depends(get_db)):
    """A farmer opens their own account; their farmer profile is created with it."""
    try:
        with db:
            user_id = db.execute(
                "INSERT INTO users (username, full_name, role, password_hash) VALUES (?, ?, 'farmer', ?)",
                (body.username, body.full_name, hash_password(body.password))).lastrowid
            db.execute(
                "INSERT INTO farmers (alias, preferred_language, phone, sms_consent, village, share_consent, "
                "user_id, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (body.full_name, body.preferred_language, body.phone, int(body.sms_consent), body.village,
                 int(body.share_consent), user_id, user_id))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "That username is taken; choose another")
    row = db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return {"token": create_token(user_id, "farmer"), "user": _user_out(db, row)}


@router.get("/auth/me")
def me(user=Depends(current_user), db=Depends(get_db)):
    row = db.execute("SELECT * FROM users WHERE user_id = ?", (user["user_id"],)).fetchone()
    return _user_out(db, row)


# ----- accounts (admin) ---------------------------------------------------

@router.get("/users")
def list_users(db=Depends(get_db), _=Depends(require_role("admin"))):
    rows = db.execute("SELECT * FROM users ORDER BY role, full_name, username").fetchall()
    return [dict(_user_out(db, r), created_at=r["created_at"]) for r in rows]


@router.post("/users", status_code=201)
def create_user(body: UserIn, db=Depends(get_db), admin=Depends(require_role("admin"))):
    try:
        with db:
            user_id = db.execute(
                "INSERT INTO users (username, full_name, role, password_hash) VALUES (?, ?, ?, ?)",
                (body.username, body.full_name, body.role, hash_password(body.password))).lastrowid
            if body.role == "farmer":
                db.execute("INSERT INTO farmers (alias, user_id, created_by) VALUES (?, ?, ?)",
                           (body.full_name, user_id, admin["user_id"]))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Username already taken")
    return _user_out(db, db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone())


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, db=Depends(get_db), admin=Depends(require_role("admin"))):
    row = db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"User {user_id} not found")
    if user_id == admin["user_id"] and (body.active is False or (body.role and body.role != "admin")):
        raise HTTPException(409, "You cannot deactivate or demote your own admin account")
    changes = {}
    if body.full_name is not None:
        changes["full_name"] = body.full_name
    if body.role is not None:
        if body.role == "farmer" or row["role"] == "farmer":
            if body.role != row["role"]:
                raise HTTPException(409, "A farmer account cannot be turned into staff, or the reverse; "
                                         "create a new account instead")
        changes["role"] = body.role
    if body.active is not None:
        changes["active"] = int(body.active)
    if body.password is not None:
        changes["password_hash"] = hash_password(body.password)
    if changes:
        sets = ", ".join(f"{k} = ?" for k in changes)
        with db:
            db.execute(f"UPDATE users SET {sets} WHERE user_id = ?", (*changes.values(), user_id))
    return _user_out(db, db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone())
