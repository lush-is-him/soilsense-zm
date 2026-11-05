"""Probes and their two-buffer calibrations (S1-4b, spec 2.3)."""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import current_user, require_role
from backend.db import get_db
from backend.schemas import CalibrationIn, DeviceIn
from backend.services.probe import calibrate, mv_to_ph

router = APIRouter(tags=["Devices"], dependencies=[Depends(current_user)])


def device_or_404(db, device_id):
    row = db.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Device {device_id} not found")
    return dict(row)


def latest_calibration(db, device_id):
    row = db.execute("SELECT * FROM calibrations WHERE device_id = ? ORDER BY calibration_id DESC "
                     "LIMIT 1", (device_id,)).fetchone()
    return dict(row) if row else None


@router.post("/devices", status_code=201, dependencies=[Depends(require_role("admin"))])
def create_device(body: DeviceIn, db=Depends(get_db)):
    try:
        with db:
            db.execute("INSERT INTO devices (device_id, label) VALUES (?, ?)",
                       (body.device_id, body.label))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Device already registered")
    return device_or_404(db, body.device_id)


@router.get("/devices")
def list_devices(db=Depends(get_db)):
    return [dict(r, latest_calibration=latest_calibration(db, r["device_id"]))
            for r in db.execute("SELECT * FROM devices ORDER BY device_id")]


@router.post("/devices/{device_id}/calibrations", status_code=201)
def add_calibration(device_id: str, body: CalibrationIn, db=Depends(get_db)):
    device_or_404(db, device_id)
    offset_mv, slope_pct, reasons = calibrate(body.mv_ph7, body.mv_ph4, body.temp_c)
    with db:
        cur = db.execute(
            "INSERT INTO calibrations (device_id, offset_mv, slope_pct, temp_c, accepted, reasons) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (device_id, offset_mv, slope_pct, body.temp_c, int(not reasons), json.dumps(reasons)))
    return {"calibration_id": cur.lastrowid, "accepted": not reasons, "slope_pct": slope_pct,
            "offset_mv": offset_mv, "reasons": reasons}


# ----- live view (demo): the bridge posts each raw reading while it settles ---

class LiveIn(BaseModel):
    mv: float
    temp_c: Optional[float] = None
    settled: bool = False
    field_id: Optional[int] = None


_LIVE = {}      # device_id -> latest live value; in memory only, never stored


@router.post("/devices/{device_id}/live")
def post_live(device_id: str, body: LiveIn, db=Depends(get_db)):
    """A provisional pH while the probe settles. Not a reading: nothing is saved."""
    device_or_404(db, device_id)
    cal = latest_calibration(db, device_id)
    ph = (mv_to_ph(body.mv, cal["offset_mv"], cal["slope_pct"], cal["temp_c"], body.temp_c)
          if cal and cal["accepted"] else None)
    _LIVE[device_id] = {"ph": ph, "temp_c": body.temp_c, "settled": body.settled,
                        "field_id": body.field_id, "ts": datetime.now(timezone.utc).isoformat()}
    return _LIVE[device_id]


@router.get("/devices/{device_id}/live")
def get_live(device_id: str, db=Depends(get_db)):
    device_or_404(db, device_id)
    return _LIVE.get(device_id) or {}
