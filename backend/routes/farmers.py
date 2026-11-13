"""Farmer profiles, with consent-gated phone numbers (FR2, NFR5).

A profile either belongs to a farmer's own login, or is kept by an officer for
a farmer without a smartphone. What each user sees is decided in backend.access.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.access import farmer_for, own_farmer_id, visible_farmers_sql
from backend.auth import current_user
from backend.db import get_db
from backend.schemas import FarmerIn, FarmerPatch

router = APIRouter(tags=["Farmers"])


def farmer_or_404(db, farmer_id):
    """Unchecked lookup, for code that has already checked access."""
    row = db.execute("SELECT * FROM farmers WHERE farmer_id = ?", (farmer_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Farmer {farmer_id} not found")
    return dict(row, sms_consent=bool(row["sms_consent"]), share_consent=bool(row["share_consent"]))


@router.post("/farmers", status_code=201)
def create_farmer(body: FarmerIn, db=Depends(get_db), user=Depends(current_user)):
    """An officer or admin registers a farmer who has no account of their own."""
    if user["role"] == "farmer":
        raise HTTPException(403, "Farmers already have their own profile; edit it instead")
    with db:
        cur = db.execute(
            "INSERT INTO farmers (alias, preferred_language, phone, sms_consent, village, share_consent, "
            "created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (body.alias, body.preferred_language, body.phone, int(body.sms_consent), body.village,
             int(body.share_consent), user["user_id"]))
    return farmer_or_404(db, cur.lastrowid)


@router.get("/farmers")
def list_farmers(db=Depends(get_db), user=Depends(current_user)):
    where, params = visible_farmers_sql(user)
    rows = db.execute(
        "SELECT f.*, COUNT(fl.field_id) AS field_count, u.full_name AS registered_by FROM farmers f "
        "LEFT JOIN fields fl ON fl.farmer_id = f.farmer_id "
        "LEFT JOIN users u ON u.user_id = f.created_by "
        f"WHERE {where} GROUP BY f.farmer_id ORDER BY f.alias", params).fetchall()
    return [dict(r, sms_consent=bool(r["sms_consent"]), share_consent=bool(r["share_consent"]),
                 own_account=r["user_id"] is not None,
                 mine=r["created_by"] == user["user_id"] or r["user_id"] == user["user_id"]) for r in rows]


@router.get("/farmers/me")
def my_profile(db=Depends(get_db), user=Depends(current_user)):
    farmer_id = own_farmer_id(db, user)
    if farmer_id is None:
        raise HTTPException(404, "This account has no farmer profile")
    return get_farmer(farmer_id, db, user)


@router.get("/farmers/{farmer_id}")
def get_farmer(farmer_id: int, db=Depends(get_db), user=Depends(current_user)):
    farmer = farmer_for(db, user, farmer_id)
    farmer["fields"] = [dict(r) for r in db.execute(
        "SELECT fl.*, (SELECT ph_water FROM readings r WHERE r.field_id = fl.field_id "
        "AND r.quality_status = 'accepted' ORDER BY r.reading_id DESC LIMIT 1) AS latest_ph, "
        "(SELECT ph FROM lab_results l WHERE l.field_id = fl.field_id ORDER BY l.lab_id DESC LIMIT 1) AS lab_ph "
        "FROM fields fl WHERE fl.farmer_id = ? ORDER BY fl.name", (farmer_id,))]
    from backend.routes.fields import sampling_points       # (fields imports nothing from here)
    for field in farmer["fields"]:
        points = sampling_points(db, field["field_id"])
        field["point_count"] = len(points)
        values = sorted(p["ph"] for p in points)
        field["median_ph"] = (values[len(values) // 2] if len(values) % 2
                              else round((values[len(values) // 2 - 1] + values[len(values) // 2]) / 2, 2)) if values else None
    try:
        farmer_for(db, user, farmer_id, edit_profile=True)
        farmer["can_edit"] = True
    except HTTPException:
        farmer["can_edit"] = False
    farmer["own_account"] = farmer["user_id"] is not None
    return farmer


@router.patch("/farmers/{farmer_id}")
def update_farmer(farmer_id: int, body: FarmerPatch, db=Depends(get_db), user=Depends(current_user)):
    farmer = farmer_for(db, user, farmer_id, edit_profile=True)
    changes = body.model_dump(exclude_unset=True)
    if "sms_consent" in changes and not changes["sms_consent"]:
        changes["phone"] = None                    # withdrawing consent removes the number
    phone = changes.get("phone", farmer["phone"])
    consent = changes.get("sms_consent", farmer["sms_consent"])
    if phone and not consent:
        raise HTTPException(422, "a phone number may only be stored with SMS consent (NFR5)")
    for flag in ("sms_consent", "share_consent"):
        if flag in changes:
            changes[flag] = int(changes[flag])
    if changes:
        sets = ", ".join(f"{k} = ?" for k in changes)
        with db:
            db.execute(f"UPDATE farmers SET {sets} WHERE farmer_id = ?", (*changes.values(), farmer_id))
    if "alias" in changes and farmer["user_id"]:
        with db:
            db.execute("UPDATE users SET full_name = ? WHERE user_id = ?", (changes["alias"], farmer["user_id"]))
    return get_farmer(farmer_id, db, user)


@router.delete("/farmers/{farmer_id}/phone")
def delete_phone(farmer_id: int, db=Depends(get_db), user=Depends(current_user)):
    """Remove the phone number and consent (NFR5)."""
    farmer_for(db, user, farmer_id, edit_profile=True)
    with db:
        db.execute("UPDATE farmers SET phone = NULL, sms_consent = 0 WHERE farmer_id = ?", (farmer_id,))
    return farmer_or_404(db, farmer_id)
