"""Fields with GPS (FR2, FR5), field checks (FR8), lab results (FR9), map estimate (FR6)."""


from fastapi import APIRouter, Depends, HTTPException

from backend import config
from backend.auth import current_user
from backend.db import get_db
from backend.routes.farmers import farmer_or_404
from backend.schemas import FieldCheckIn, FieldIn, LabResultIn
from engine.config import DEFAULT_CONFIG

router = APIRouter(tags=["Fields"], dependencies=[Depends(current_user)])

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


def field_or_404(db, field_id):
    row = db.execute("SELECT * FROM fields WHERE field_id = ?", (field_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Field {field_id} not found")
    return dict(row)


@router.post("/fields", status_code=201)
def create_field(body: FieldIn, db=Depends(get_db)):
    farmer_or_404(db, body.farmer_id)
    if body.location_source == "gps":
        limit = DEFAULT_CONFIG.GPS_MAX_ACCURACY_M
        if body.gps_accuracy_m is None or body.gps_accuracy_m > limit:
            raise HTTPException(422, f"GPS fix accuracy must be {limit:.0f} m or better; "
                                     f"wait for a better fix or drop a manual pin")
    with db:
        cur = db.execute(
            "INSERT INTO fields (farmer_id, name, lat, lon, gps_accuracy_m, location_source, area_lima) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (body.farmer_id, body.name, body.lat, body.lon,
             body.gps_accuracy_m if body.location_source == "gps" else None,
             body.location_source, body.area_lima))
    return field_or_404(db, cur.lastrowid)


@router.get("/fields/{field_id}")
def get_field(field_id: int, db=Depends(get_db)):
    return field_or_404(db, field_id)


@router.get("/fields/{field_id}/history")
def field_history(field_id: int, db=Depends(get_db)):
    field_or_404(db, field_id)
    def rows(sql):
        return [dict(r) for r in db.execute(sql, (field_id,))]
    return {
        "readings": rows("SELECT * FROM readings WHERE field_id = ? ORDER BY ts DESC"),
        "lab_results": rows("SELECT * FROM lab_results WHERE field_id = ? ORDER BY lab_id DESC"),
        "field_checks": rows("SELECT * FROM field_checks WHERE field_id = ? ORDER BY ts DESC"),
        "recommendations": rows(
            "SELECT rec_id, reading_id, trust_level, crop, as_of_date, method_sensitive, created_at "
            "FROM recommendations WHERE field_id = ? ORDER BY rec_id DESC"),
    }


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
def map_estimate(field_id: int, db=Depends(get_db)):
    field = field_or_404(db, field_id)
    estimate = get_or_fetch_map_estimate(db, field)
    if estimate is None:
        if map_service() is None:
            raise HTTPException(503, "Map layers not downloaded; run scripts/fetch_isdasoil.py")
        raise HTTPException(404, "No map value at this location")
    return estimate


@router.post("/fields/{field_id}/checks", status_code=201)
def add_field_check(field_id: int, body: FieldCheckIn, db=Depends(get_db)):
    field_or_404(db, field_id)
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
def add_lab_result(field_id: int, body: LabResultIn, db=Depends(get_db)):
    field_or_404(db, field_id)
    with db:
        cur = db.execute(
            "INSERT INTO lab_results (field_id, ph, ph_method, soil_water_ratio, oc, p, k, texture, "
            "lab_name, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (field_id, body.ph, body.ph_method, body.soil_water_ratio, body.oc, body.p, body.k,
             body.texture, body.lab_name, body.date))
    return dict(db.execute("SELECT * FROM lab_results WHERE lab_id = ?", (cur.lastrowid,)).fetchone())
