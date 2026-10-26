"""SoilSense ZM backend (spec 2, 4).

    uvicorn backend.main:app --reload
    API docs: http://localhost:8000/docs   Dashboard: http://localhost:8000/
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.db import get_db
from backend.routes import advice, auth, devices, farmers, fields, readings, rules
from backend.services.rules_sync import sync_rules

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"



@asynccontextmanager
async def lifespan(app):
    sync_rules(get_db())       # migrate the database and mirror the rule tables
    yield


app = FastAPI(
    lifespan=lifespan,
    title="SoilSense ZM API",
    description="Rule-based soil and crop advice for smallholders in Kafue District, Zambia. "
                "Probe pH is checked against the iSDAsoil map to set a trust level.",
    version="2.0.0",
)

for module in (auth, farmers, fields, devices, readings, advice, rules):
    app.include_router(module.router)


@app.get("/health")
def health():
    return {"status": "online", "app": "SoilSense ZM", "version": app.version}


app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(DASHBOARD_DIR / "index.html")
