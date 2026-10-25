# ============================================================
# SoilSense ZM — Backend
# models.py — Pydantic request/response schemas
# ============================================================

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── SOIL READING (input) ──────────────────────────────────────

class SoilReading(BaseModel):
    """Input from sensor or manual entry."""
    pH: float = Field(..., ge=0, le=14, description="Soil pH value")
    moisture: float = Field(..., ge=0, le=100, description="Soil moisture percentage")
    temperature: float = Field(..., ge=-10, le=60, description="Soil temperature in °C")
    farmer_phone: Optional[str] = Field(None, description="Farmer phone for SMS advisory")
    latitude: Optional[float] = Field(None, description="GPS latitude")
    longitude: Optional[float] = Field(None, description="GPS longitude")


# ── PREDICTION RESPONSE ──────────────────────────────────────

class Advisory(BaseModel):
    """Advisory details for a soil health prediction."""
    summary: str
    lime_recommendation: str
    fertilizer_recommendation: str
    crop_suitability: List[str]
    management_advice: List[str]
    alert_level: str  # green, yellow, orange, red


class PredictionResponse(BaseModel):
    """Response from /predict endpoint."""
    soil_health: str
    confidence: float
    advisory: Advisory
    sms_sent: bool = False
    reading_id: Optional[int] = None


# ── FARMER SCHEMAS ────────────────────────────────────────────

class FarmerCreate(BaseModel):
    """Register a new farmer."""
    name: str = Field(..., min_length=2, description="Full name")
    phone: str = Field(..., description="Phone number (e.g. +260971234567)")
    location: str = Field(..., description="Farm location/area")
    district: str = Field("Kafue", description="District name")
    farm_size_hectares: Optional[float] = Field(None, ge=0, description="Farm size in hectares")


class FarmerResponse(BaseModel):
    """Registered farmer details."""
    id: int
    name: str
    phone: str
    location: str
    district: str
    farm_size_hectares: Optional[float]
    created_at: str
    updated_at: str


class FarmerWithReadings(FarmerResponse):
    """Farmer with their soil reading history."""
    total_readings: int = 0
    latest_prediction: Optional[str] = None
    latest_alert_level: Optional[str] = None


# ── GENERAL ───────────────────────────────────────────────────

class StatusResponse(BaseModel):
    """API status check."""
    status: str
    app: str = "SoilSense ZM"
    version: str = "1.0.0"
    model_loaded: bool
