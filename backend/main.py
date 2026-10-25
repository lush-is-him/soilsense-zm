# ============================================================
# SoilSense ZM — Backend
# main.py — FastAPI application entry point
#
# Run with: uvicorn backend.main:app --reload
# Docs at:  http://localhost:8000/docs
#
# Author: Lushomo Sibalwa — 202301072 — ZCAS University
# ============================================================

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.routes.predict import router as predict_router
from backend.routes.farmers import router as farmers_router
from backend.models import StatusResponse


# ── APP SETUP ─────────────────────────────────────────────────

app = FastAPI(
    title="SoilSense ZM API",
    description=(
        "Soil health monitoring and advisory system for Kafue District, Zambia. "
        "Predicts soil health from sensor readings using a Random Forest ML model "
        "and provides Zambia-specific crop and management recommendations."
    ),
    version="1.0.0",
    contact={
        "name": "Lushomo Sibalwa",
        "email": "202301072@zcas.edu.zm"
    },
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────
# Allow frontend dashboard to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ROUTES ────────────────────────────────────────────────────
app.include_router(predict_router)
app.include_router(farmers_router)

# ── STATIC FILES & DASHBOARD ──────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")

# Mount dashboard directory for static files (js, css)
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")

@app.get("/dashboard")
async def get_dashboard():
    """Serve the Web Dashboard index page."""
    return FileResponse(os.path.join(DASHBOARD_DIR, "index.html"))

# ── ROOT ENDPOINT ─────────────────────────────────────────────


@app.get("/", response_model=StatusResponse)
async def root():
    """API status check."""
    from backend.routes.predict import model
    return StatusResponse(
        status="online",
        app="SoilSense ZM",
        version="1.0.0",
        model_loaded=model is not None
    )


# ── STARTUP EVENT ─────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    print("\n" + "=" * 55)
    print("  SoilSense ZM API — Starting up")
    print("=" * 55)
    print("  📡 API docs:  http://localhost:8000/docs")
    print("  📡 ReDoc:     http://localhost:8000/redoc")
    print("=" * 55 + "\n")
