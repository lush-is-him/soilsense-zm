"""Referrals to the lab or to an officer, the shared map, and the admin overview (Nov 2026).

The farmer tests their own soil. When the reading is unusual, or the farmer
prefers it, they ask for a lab test or for an officer to visit. Officers see
these requests, and every shared test appears on the map, so the labs build
up a record of soils across the country instead of losing samples to self-testing.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.access import field_for, visible_farmers_sql
from backend.auth import current_user, require_role
from backend.db import get_db
from backend.schemas import ReferralIn, ReferralPatch

router = APIRouter(tags=["Referrals and map"])

_REFERRAL_SELECT = (
    "SELECT r.*, fl.name AS field, fl.lat, fl.lon, f.farmer_id, f.alias AS farmer, f.village, f.phone, "
    "rd.ph_water AS reading_ph, u.full_name AS handled_by_name "
    "FROM referrals r JOIN fields fl ON fl.field_id = r.field_id "
    "JOIN farmers f ON f.farmer_id = fl.farmer_id "
    "LEFT JOIN readings rd ON rd.reading_id = r.reading_id "
    "LEFT JOIN users u ON u.user_id = r.handled_by ")


@router.post("/referrals", status_code=201)
def create_referral(body: ReferralIn, db=Depends(get_db), user=Depends(current_user)):
    field_for(db, user, body.field_id)
    if body.reading_id is not None and db.execute(
            "SELECT 1 FROM readings WHERE reading_id = ? AND field_id = ?",
            (body.reading_id, body.field_id)).fetchone() is None:
        raise HTTPException(404, f"Reading {body.reading_id} not found for this field")
    open_one = db.execute("SELECT referral_id FROM referrals WHERE field_id = ? AND kind = ? "
                          "AND status IN ('open', 'in_progress')", (body.field_id, body.kind)).fetchone()
    if open_one:
        return get_referral(open_one["referral_id"], db, user)
    with db:
        cur = db.execute("INSERT INTO referrals (field_id, reading_id, kind, reason, created_by) "
                         "VALUES (?, ?, ?, ?, ?)",
                         (body.field_id, body.reading_id, body.kind, body.reason, user["user_id"]))
    return get_referral(cur.lastrowid, db, user)


@router.get("/referrals")
def list_referrals(status: str = "active", db=Depends(get_db), user=Depends(current_user)):
    """Farmers see their own; officers see every referral (that is their work list); admin all."""
    where, params = ("1 = 1", ()) if user["role"] != "farmer" else visible_farmers_sql(user)
    status_sql = {"active": "r.status IN ('open', 'in_progress')", "all": "1 = 1"}.get(status, "r.status = ?")
    status_params = () if status in ("active", "all") else (status,)
    rows = db.execute(f"{_REFERRAL_SELECT} WHERE {where} AND {status_sql} ORDER BY r.referral_id DESC",
                      (*params, *status_params)).fetchall()
    return [_referral_out(r, user) for r in rows]


@router.get("/referrals/{referral_id}")
def get_referral(referral_id: int, db=Depends(get_db), user=Depends(current_user)):
    row = db.execute(f"{_REFERRAL_SELECT} WHERE r.referral_id = ?", (referral_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Referral {referral_id} not found")
    field_for(db, user, row["field_id"])
    return _referral_out(row, user)


@router.patch("/referrals/{referral_id}")
def update_referral(referral_id: int, body: ReferralPatch, db=Depends(get_db), user=Depends(current_user)):
    referral = get_referral(referral_id, db, user)
    changes = body.model_dump(exclude_unset=True)
    if user["role"] == "farmer":
        # a farmer may only cancel their own request
        if set(changes) - {"status"} or changes.get("status") not in (None, "cancelled"):
            raise HTTPException(403, "A farmer can only cancel a request")
    elif "status" in changes:
        changes["handled_by"] = user["user_id"]
    if changes:
        sets = ", ".join(f"{k} = ?" for k in changes)
        with db:
            db.execute(f"UPDATE referrals SET {sets}, updated_at = datetime('now') WHERE referral_id = ?",
                       (*changes.values(), referral["referral_id"]))
    return get_referral(referral_id, db, user)


def _referral_out(row, user):
    out = dict(row)
    if user["role"] == "farmer" or not out.get("phone"):
        out.pop("phone", None)
    return out


# ----- map and overview -----------------------------------------------

@router.get("/map/points")
def map_points(db=Depends(get_db), user=Depends(current_user)):
    """One point per field the user may see: latest probe pH, latest lab pH, open referral."""
    where, params = visible_farmers_sql(user)
    rows = db.execute(
        "SELECT fl.field_id, fl.name AS field, fl.lat, fl.lon, fl.location_source, f.alias AS farmer, f.village, "
        "(SELECT ph_water FROM readings r WHERE r.field_id = fl.field_id AND r.quality_status = 'accepted' "
        " ORDER BY r.reading_id DESC LIMIT 1) AS probe_ph, "
        "(SELECT ts FROM readings r WHERE r.field_id = fl.field_id AND r.quality_status = 'accepted' "
        " ORDER BY r.reading_id DESC LIMIT 1) AS probe_ts, "
        "(SELECT ph FROM lab_results l WHERE l.field_id = fl.field_id ORDER BY l.lab_id DESC LIMIT 1) AS lab_ph, "
        "(SELECT trust_level FROM recommendations rc WHERE rc.field_id = fl.field_id "
        " ORDER BY rc.rec_id DESC LIMIT 1) AS trust_level, "
        "(SELECT ph_mean FROM map_estimates m WHERE m.field_id = fl.field_id) AS map_ph, "
        "EXISTS (SELECT 1 FROM referrals rf WHERE rf.field_id = fl.field_id "
        " AND rf.status IN ('open', 'in_progress')) AS referral_open "
        f"FROM fields fl JOIN farmers f ON f.farmer_id = fl.farmer_id WHERE {where}", params).fetchall()
    return [dict(r, referral_open=bool(r["referral_open"])) for r in rows]


@router.get("/overview")
def overview(db=Depends(get_db), _=Depends(require_role("admin"))):
    """Counts for the admin's overview page."""
    def one(sql, *args):
        return db.execute(sql, args).fetchone()[0]
    return {
        "users": {r["role"]: r["n"] for r in db.execute(
            "SELECT role, COUNT(*) AS n FROM users WHERE active = 1 GROUP BY role")},
        "farmers": one("SELECT COUNT(*) FROM farmers"),
        "farmers_self_testing": one("SELECT COUNT(*) FROM farmers WHERE user_id IS NOT NULL"),
        "farmers_sharing": one("SELECT COUNT(*) FROM farmers WHERE share_consent = 1"),
        "fields": one("SELECT COUNT(*) FROM fields"),
        "readings": {r["quality_status"]: r["n"] for r in db.execute(
            "SELECT quality_status, COUNT(*) AS n FROM readings GROUP BY quality_status")},
        "advice": {r["trust_level"]: r["n"] for r in db.execute(
            "SELECT trust_level, COUNT(*) AS n FROM recommendations GROUP BY trust_level")},
        "referrals_open": one("SELECT COUNT(*) FROM referrals WHERE status IN ('open', 'in_progress')"),
        "lab_results": one("SELECT COUNT(*) FROM lab_results"),
        "calibrations": [dict(r) for r in db.execute(
            "SELECT device_id, date, slope_pct, temp_c, accepted FROM calibrations "
            "ORDER BY calibration_id DESC LIMIT 10")],
    }
