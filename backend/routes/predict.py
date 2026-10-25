# ============================================================
# SoilSense ZM — Backend
# routes/predict.py — /predict endpoint
# ============================================================

import os
import numpy as np
import pandas as pd
import joblib
from datetime import datetime
from fastapi import APIRouter, HTTPException

from backend.models import SoilReading, PredictionResponse, Advisory
from backend.advisory import get_advisory
from backend.sms import send_sms, format_advisory_sms
from backend.database import get_connection

router = APIRouter(tags=["Predictions"])

# ── LOAD MODEL ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "soil_model_v2.pkl")
ENCODER_PATH = os.path.join(BASE_DIR, "label_encoder_v2.pkl")

model = None
label_encoder = None

try:
    model = joblib.load(MODEL_PATH)
    label_encoder = joblib.load(ENCODER_PATH)
    print(f"   ✅ ML model (v2, 3-feature) loaded from {MODEL_PATH}")
except Exception as e:
    print(f"   ⚠️ Model not loaded: {e}")
    print(f"   Run train_model.py first to generate soil_model_v2.pkl")


# ── PREDICT ENDPOINT ──────────────────────────────────────────

@router.post("/predict", response_model=PredictionResponse)
async def predict_soil_health(reading: SoilReading):
    """
    Predict soil health from sensor readings.

    Accepts pH, moisture, and temperature from the Arduino sensor.
    Returns soil health label, confidence, and Zambia-specific advisory.
    """
    if model is None or label_encoder is None:
        raise HTTPException(
            status_code=503,
            detail="ML model not loaded. Run train_model.py first."
        )

    # Prepare input features — 3 sensor-measured values only
    features = {
        "pH": reading.pH,
        "moisture": reading.moisture,
        "temperature": reading.temperature,
    }

    X = pd.DataFrame([features])

    # Predict
    pred_encoded = model.predict(X)[0]
    pred_label = label_encoder.inverse_transform([pred_encoded])[0]
    proba = model.predict_proba(X)[0]
    confidence = round(float(max(proba)) * 100, 1)

    # Get advisory
    advisory_data = get_advisory(pred_label, pH=reading.pH, moisture=reading.moisture)
    advisory = Advisory(**advisory_data)

    # Save reading to database
    reading_id = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Find farmer by phone if provided
        farmer_id = None
        if reading.farmer_phone:
            cursor.execute("SELECT id FROM farmers WHERE phone = ?", (reading.farmer_phone,))
            row = cursor.fetchone()
            if row:
                farmer_id = row["id"]

        cursor.execute("""
            INSERT INTO readings
            (farmer_id, pH, moisture, temperature, nitrogen, phosphorus,
             organic_carbon, prediction, confidence, advisory, latitude, longitude, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            farmer_id,
            reading.pH, reading.moisture, reading.temperature,
            None, None, None,  # Nutrient sensors not available on Arduino hardware
            pred_label, confidence, advisory_data["summary"],
            reading.latitude, reading.longitude,
            datetime.now().isoformat()
        ))

        reading_id = cursor.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"   ⚠️ Failed to save reading: {e}")

    # Send SMS if phone provided
    sms_sent = False
    if reading.farmer_phone:
        sms_message = format_advisory_sms(pred_label, confidence, advisory_data["summary"])
        result = send_sms(reading.farmer_phone, sms_message)
        sms_sent = result.get("status") in ("sent", "stubbed")

    return PredictionResponse(
        soil_health=pred_label,
        confidence=confidence,
        advisory=advisory,
        sms_sent=sms_sent,
        reading_id=reading_id
    )


@router.get("/model/status")
async def model_status():
    """Check if the ML model is loaded and ready."""
    return {
        "model_loaded": model is not None,
        "encoder_loaded": label_encoder is not None,
        "model_path": MODEL_PATH,
        "classes": list(label_encoder.classes_) if label_encoder else []
    }
