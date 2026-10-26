"""POST /readings from the serial bridge or the operator (FR3, FR4, NFR2)."""

import json

from fastapi import APIRouter, Depends, HTTPException

from backend.auth import current_user
from backend.db import get_db
from backend.routes.devices import device_or_404, latest_calibration
from backend.routes.fields import field_or_404
from backend.schemas import ReadingIn
from backend.services.probe import mv_to_ph
from engine.quality import Calibration, check_reading

router = APIRouter(tags=["Readings"])


def reading_out(row):
    out = dict(row)
    for key in ("replicates", "replicates_mv", "quality_reasons"):
        out[key] = json.loads(out[key]) if out[key] else None
    return out


@router.post("/readings", status_code=201)
def create_reading(body: ReadingIn, db=Depends(get_db), user=Depends(current_user)):
    field_or_404(db, body.field_id)
    calibration_row = None
    if body.device_id:
        device_or_404(db, body.device_id)
        calibration_row = latest_calibration(db, body.device_id)
        if calibration_row is not None and not calibration_row["accepted"]:
            calibration_row = None          # last calibration failed: no valid calibration

    if body.replicates_mv is not None:
        if calibration_row is None:
            replicates = []
        else:
            replicates = [mv_to_ph(mv, calibration_row["offset_mv"], calibration_row["slope_pct"],
                                   calibration_row["temp_c"]) for mv in body.replicates_mv]
    else:
        replicates = body.replicates_ph

    calibration = (Calibration(calibration_row["slope_pct"], calibration_row["temp_c"])
                   if calibration_row else None)
    # No device or no accepted calibration: check_reading rejects (NFR2).
    result = check_reading(replicates, body.temp_c, calibration, body.moisture)

    with db:
        cur = db.execute(
            "INSERT INTO readings (field_id, device_id, operator_id, calibration_id, ph_water, "
            "replicates, replicates_mv, moisture, temp_c, quality_status, quality_reasons) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (body.field_id, body.device_id, user["user_id"],
             calibration_row["calibration_id"] if calibration_row else None,
             result.ph_mean, json.dumps(replicates),
             json.dumps(body.replicates_mv) if body.replicates_mv is not None else None,
             body.moisture, body.temp_c, "accepted" if result.accepted else "rejected",
             json.dumps(result.reasons + result.warnings)))
    return get_reading(cur.lastrowid, db, user)


@router.get("/readings/{reading_id}")
def get_reading(reading_id: int, db=Depends(get_db), user=Depends(current_user)):
    row = db.execute("SELECT * FROM readings WHERE reading_id = ?", (reading_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Reading {reading_id} not found")
    return reading_out(row)
