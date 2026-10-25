# ============================================================
# SoilSense ZM — Backend
# routes/farmers.py — /farmers endpoints
# ============================================================

from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException

from backend.models import FarmerCreate, FarmerResponse, FarmerWithReadings
from backend.database import get_connection

router = APIRouter(tags=["Farmers"])


# ── REGISTER FARMER ───────────────────────────────────────────

@router.post("/farmers", response_model=FarmerResponse, status_code=201)
async def register_farmer(farmer: FarmerCreate):
    """Register a new farmer in the system."""
    conn = get_connection()
    cursor = conn.cursor()

    # Check if phone already exists
    cursor.execute("SELECT id FROM farmers WHERE phone = ?", (farmer.phone,))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Farmer with phone {farmer.phone} already registered (ID: {existing['id']})"
        )

    now = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO farmers (name, phone, location, district, farm_size_hectares, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (farmer.name, farmer.phone, farmer.location,
          farmer.district, farmer.farm_size_hectares, now, now))

    farmer_id = cursor.lastrowid
    conn.commit()

    # Fetch and return
    cursor.execute("SELECT * FROM farmers WHERE id = ?", (farmer_id,))
    row = cursor.fetchone()
    conn.close()

    return FarmerResponse(
        id=row["id"],
        name=row["name"],
        phone=row["phone"],
        location=row["location"],
        district=row["district"],
        farm_size_hectares=row["farm_size_hectares"],
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


# ── LIST ALL FARMERS ──────────────────────────────────────────

@router.get("/farmers", response_model=List[FarmerWithReadings])
async def list_farmers():
    """List all registered farmers with their latest reading status."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT f.*,
               COUNT(r.id) as total_readings,
               (SELECT prediction FROM readings
                WHERE farmer_id = f.id ORDER BY created_at DESC LIMIT 1) as latest_prediction
        FROM farmers f
        LEFT JOIN readings r ON r.farmer_id = f.id
        GROUP BY f.id
        ORDER BY f.created_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    farmers = []
    for row in rows:
        alert_map = {
            "Healthy": "green", "Moderate": "yellow",
            "Degraded": "orange", "Critical": "red"
        }
        latest_pred = row["latest_prediction"]

        farmers.append(FarmerWithReadings(
            id=row["id"],
            name=row["name"],
            phone=row["phone"],
            location=row["location"],
            district=row["district"],
            farm_size_hectares=row["farm_size_hectares"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            total_readings=row["total_readings"],
            latest_prediction=latest_pred,
            latest_alert_level=alert_map.get(latest_pred) if latest_pred else None
        ))

    return farmers


# ── GET SINGLE FARMER ─────────────────────────────────────────

@router.get("/farmers/{farmer_id}", response_model=FarmerWithReadings)
async def get_farmer(farmer_id: int):
    """Get a single farmer's details and reading history."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM farmers WHERE id = ?", (farmer_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Farmer {farmer_id} not found")

    # Count readings
    cursor.execute("SELECT COUNT(*) as cnt FROM readings WHERE farmer_id = ?", (farmer_id,))
    count = cursor.fetchone()["cnt"]

    # Latest prediction
    cursor.execute("""
        SELECT prediction FROM readings
        WHERE farmer_id = ? ORDER BY created_at DESC LIMIT 1
    """, (farmer_id,))
    latest = cursor.fetchone()
    conn.close()

    alert_map = {
        "Healthy": "green", "Moderate": "yellow",
        "Degraded": "orange", "Critical": "red"
    }
    latest_pred = latest["prediction"] if latest else None

    return FarmerWithReadings(
        id=row["id"],
        name=row["name"],
        phone=row["phone"],
        location=row["location"],
        district=row["district"],
        farm_size_hectares=row["farm_size_hectares"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        total_readings=count,
        latest_prediction=latest_pred,
        latest_alert_level=alert_map.get(latest_pred) if latest_pred else None
    )


# ── GET FARMER READINGS ──────────────────────────────────────

@router.get("/farmers/{farmer_id}/readings")
async def get_farmer_readings(farmer_id: int):
    """Get all soil readings for a farmer."""
    conn = get_connection()
    cursor = conn.cursor()

    # Verify farmer exists
    cursor.execute("SELECT id FROM farmers WHERE id = ?", (farmer_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Farmer {farmer_id} not found")

    cursor.execute("""
        SELECT * FROM readings WHERE farmer_id = ?
        ORDER BY created_at DESC
    """, (farmer_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]
