"""Farmers, with consent-gated phone numbers (FR2, NFR5)."""

from fastapi import APIRouter, Depends, HTTPException

from backend.auth import current_user
from backend.db import get_db
from backend.schemas import FarmerIn

router = APIRouter(tags=["Farmers"], dependencies=[Depends(current_user)])


def farmer_or_404(db, farmer_id):
    row = db.execute("SELECT * FROM farmers WHERE farmer_id = ?", (farmer_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Farmer {farmer_id} not found")
    return dict(row, sms_consent=bool(row["sms_consent"]))


@router.post("/farmers", status_code=201)
def create_farmer(body: FarmerIn, db=Depends(get_db)):
    with db:
        cur = db.execute(
            "INSERT INTO farmers (alias, preferred_language, phone, sms_consent) VALUES (?, ?, ?, ?)",
            (body.alias, body.preferred_language, body.phone, int(body.sms_consent)))
    return farmer_or_404(db, cur.lastrowid)


@router.get("/farmers")
def list_farmers(db=Depends(get_db)):
    rows = db.execute(
        "SELECT f.*, COUNT(fl.field_id) AS field_count FROM farmers f "
        "LEFT JOIN fields fl ON fl.farmer_id = f.farmer_id "
        "GROUP BY f.farmer_id ORDER BY f.alias").fetchall()
    return [dict(r, sms_consent=bool(r["sms_consent"])) for r in rows]


@router.get("/farmers/{farmer_id}")
def get_farmer(farmer_id: int, db=Depends(get_db)):
    farmer = farmer_or_404(db, farmer_id)
    farmer["fields"] = [dict(r) for r in db.execute(
        "SELECT * FROM fields WHERE farmer_id = ? ORDER BY name", (farmer_id,))]
    return farmer


@router.delete("/farmers/{farmer_id}/phone")
def delete_phone(farmer_id: int, db=Depends(get_db)):
    """Remove the phone number and consent after a demonstration (NFR5)."""
    farmer_or_404(db, farmer_id)
    with db:
        db.execute("UPDATE farmers SET phone = NULL, sms_consent = 0 WHERE farmer_id = ?",
                   (farmer_id,))
    return farmer_or_404(db, farmer_id)
