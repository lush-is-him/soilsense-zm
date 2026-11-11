"""Fields with GPS (FR2, FR5), field checks (FR8), lab results (FR9), map estimate (FR6)."""

import json


from fastapi import APIRouter, Depends, HTTPException

from backend import config
from backend.access import farmer_for, field_for, own_farmer_id, require_field_edit
from backend.auth import current_user
from backend.db import get_db
from backend.schemas import FieldCheckIn, FieldIn, FieldPatch, LabResultIn
from engine.config import DEFAULT_CONFIG

router = APIRouter(tags=["Fields"])

_map_service = None


def map_service():
    """The iSDAsoil lookup, or None when the layers have not been downloaded."""
    global _map_service
    if _map_service is None:
        try:
            from engine.map_service import MapService
            _map_service = MapService(config.MAP_DATA_DIR)
        except (FileNotFoundError, ImportError):
            return None
    return _map_service


def set_map_service(service):
    global _map_service
    _map_service = service


def reading_out(row):
    out = dict(row)
    for key in ("replicates", "replicates_mv", "quality_reasons"):
        out[key] = json.loads(out[key]) if out[key] else None
    return out


def field_or_404(db, field_id):
    """Unchecked lookup, for code that has already checked access."""
    row = db.execute("SELECT * FROM fields WHERE field_id = ?", (field_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Field {field_id} not found")
    return dict(row)


def _check_gps(source, accuracy):
    if source == "gps":
        limit = DEFAULT_CONFIG.GPS_MAX_ACCURACY_M
        if accuracy is None or accuracy > limit:
            raise HTTPException(422, f"GPS fix accuracy must be {limit:.0f} m or better; "
                                     f"wait for a better fix or drop a manual pin")


@router.post("/fields", status_code=201)
def create_field(body: FieldIn, db=Depends(get_db), user=Depends(current_user)):
    if user["role"] == "farmer":
        mine = own_farmer_id(db, user)
        if body.farmer_id not in (None, mine):
            raise HTTPException(404, f"Farmer {body.farmer_id} not found")
        body.farmer_id = mine
    if body.farmer_id is None:
        raise HTTPException(422, "farmer_id is required")
    farmer_for(db, user, body.farmer_id)
    _check_gps(body.location_source, body.gps_accuracy_m)
    with db:
        cur = db.execute(
            "INSERT INTO fields (farmer_id, name, lat, lon, gps_accuracy_m, location_source, area_lima) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (body.farmer_id, body.name, body.lat, body.lon,
             body.gps_accuracy_m if body.location_source == "gps" else None,
             body.location_source, body.area_lima))
    return field_or_404(db, cur.lastrowid)


@router.get("/fields/{field_id}")
def get_field(field_id: int, db=Depends(get_db), user=Depends(current_user)):
    return field_for(db, user, field_id)


@router.patch("/fields/{field_id}")
def update_field(field_id: int, body: FieldPatch, db=Depends(get_db), user=Depends(current_user)):
    field = field_for(db, user, field_id)
    require_field_edit(db, user, field)
    changes = body.model_dump(exclude_unset=True)
    moved = any(k in changes for k in ("lat", "lon", "location_source", "gps_accuracy_m"))
    if moved:
        source = changes.get("location_source", field["location_source"])
        accuracy = changes.get("gps_accuracy_m", field["gps_accuracy_m"])
        _check_gps(source, accuracy)
        if source == "manual":
            changes["gps_accuracy_m"] = None
    if changes:
        sets = ", ".join(f"{k} = ?" for k in changes)
        with db:
            db.execute(f"UPDATE fields SET {sets} WHERE field_id = ?", (*changes.values(), field_id))
            if moved:                         # the map value belongs to the old spot
                db.execute("DELETE FROM map_estimates WHERE field_id = ?", (field_id,))
    return field_or_404(db, field_id)


@router.delete("/fields/{field_id}", status_code=204)
def delete_field(field_id: int, db=Depends(get_db), user=Depends(current_user)):
    field = field_for(db, user, field_id)
    require_field_edit(db, user, field)
    with db:
        for table in ("recommendation_rules", "sms_messages"):
            db.execute(f"DELETE FROM {table} WHERE rec_id IN "
                       "(SELECT rec_id FROM recommendations WHERE field_id = ?)", (field_id,))
        for table in ("recommendations", "lab_results", "referrals", "readings", "field_checks", "map_estimates"):
            db.execute(f"DELETE FROM {table} WHERE field_id = ?", (field_id,))
        db.execute("DELETE FROM fields WHERE field_id = ?", (field_id,))


@router.get("/fields/{field_id}/history")
def field_history(field_id: int, db=Depends(get_db), user=Depends(current_user)):
    field_for(db, user, field_id)
    def rows(sql):
        return [dict(r) for r in db.execute(sql, (field_id,))]
    return {
        "readings": [reading_out(r) for r in db.execute(
            "SELECT * FROM readings WHERE field_id = ? ORDER BY reading_id DESC", (field_id,))],
        "lab_results": rows("SELECT * FROM lab_results WHERE field_id = ? ORDER BY lab_id DESC"),
        "field_checks": rows("SELECT * FROM field_checks WHERE field_id = ? ORDER BY ts DESC"),
        "recommendations": rows(
            "SELECT rec_id, reading_id, trust_level, crop, as_of_date, method_sensitive, created_at "
            "FROM recommendations WHERE field_id = ? ORDER BY rec_id DESC"),
        "referrals": rows("SELECT * FROM referrals WHERE field_id = ? ORDER BY referral_id DESC"),
        "points": sampling_points(db, field_id),
    }


POINT_DAYS = 365      # a sampling point's latest reading counts for the field for a year


def sampling_points(db, field_id):
    """The latest accepted reading of each sampling point in the field (a reading without a
    point label is its own point). Used for whole-field advice and the field's point map."""
    rows = db.execute(
        "SELECT * FROM readings WHERE field_id = ? AND quality_status = 'accepted' "
        "AND ts >= datetime('now', ?) ORDER BY reading_id DESC", (field_id, f"-{POINT_DAYS} days")).fetchall()
    seen, points = set(), []
    for r in rows:
        key = r["point_label"] or f"#{r['reading_id']}"
        if key in seen:
            continue
        seen.add(key)
        points.append({"label": r["point_label"], "reading_id": r["reading_id"], "ph": r["ph_water"],
                       "lat": r["point_lat"], "lon": r["point_lon"], "ts": r["ts"],
                       "calibration_id": r["calibration_id"]})
    return sorted(points, key=lambda p: (p["label"] is None, p["label"] or "", p["reading_id"]))


def get_or_fetch_map_estimate(db, field):
    row = db.execute("SELECT * FROM map_estimates WHERE field_id = ?",
                     (field["field_id"],)).fetchone()
    if row is not None:
        return dict(row)
    service = map_service()
    if service is None:
        return None
    estimate = service.lookup(field["lat"], field["lon"])
    if estimate is None:
        return None
    with db:
        db.execute(
            "INSERT INTO map_estimates (field_id, ph_mean, ph_sd, ph_method, oc, p, k, texture, depth_cm) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (field["field_id"], estimate.ph_mean, estimate.ph_sd, estimate.ph_method,
             estimate.oc_g_kg, estimate.p_ppm, estimate.k_ppm, estimate.texture, estimate.depth_cm))
    return dict(db.execute("SELECT * FROM map_estimates WHERE field_id = ?",
                           (field["field_id"],)).fetchone())


@router.get("/fields/{field_id}/map-estimate")
def map_estimate(field_id: int, db=Depends(get_db), user=Depends(current_user)):
    field = field_for(db, user, field_id)
    estimate = get_or_fetch_map_estimate(db, field)
    if estimate is None:
        if map_service() is None:
            raise HTTPException(503, "Map layers not downloaded; run scripts/fetch_isdasoil.py")
        raise HTTPException(404, "No map value at this location")
    return estimate


@router.post("/fields/{field_id}/checks", status_code=201)
def add_field_check(field_id: int, body: FieldCheckIn, db=Depends(get_db), user=Depends(current_user)):
    field_for(db, user, field_id)
    def flag(value):
        return None if value is None else int(value)
    with db:
        cur = db.execute(
            "INSERT INTO field_checks (field_id, texture_by_feel, colour, waterlogging, previous_crop, "
            "manure_available) VALUES (?, ?, ?, ?, ?, ?)",
            (field_id, body.texture_by_feel, body.colour, flag(body.waterlogging),
             body.previous_crop, flag(body.manure_available)))
    return dict(db.execute("SELECT * FROM field_checks WHERE check_id = ?", (cur.lastrowid,)).fetchone())


@router.post("/fields/{field_id}/lab-results", status_code=201)
def add_lab_result(field_id: int, body: LabResultIn, db=Depends(get_db), user=Depends(current_user)):
    """A farmer may type in their own lab report; an officer enters results for a referral."""
    field_for(db, user, field_id)
    if body.referral_id is not None:
        ref = db.execute("SELECT * FROM referrals WHERE referral_id = ? AND field_id = ?",
                         (body.referral_id, field_id)).fetchone()
        if ref is None:
            raise HTTPException(404, f"Referral {body.referral_id} not found for this field")
    with db:
        cur = db.execute(
            "INSERT INTO lab_results (field_id, ph, ph_method, soil_water_ratio, oc, p, k, texture, "
            "lab_name, date, referral_id, entered_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (field_id, body.ph, body.ph_method, body.soil_water_ratio, body.oc, body.p, body.k,
             body.texture, body.lab_name, body.date, body.referral_id, user["user_id"]))
        if body.referral_id is not None:
            db.execute("UPDATE referrals SET status = 'done', handled_by = COALESCE(handled_by, ?), "
                       "updated_at = datetime('now') WHERE referral_id = ?", (user["user_id"], body.referral_id))
    return dict(db.execute("SELECT * FROM lab_results WHERE lab_id = ?", (cur.lastrowid,)).fetchone())
