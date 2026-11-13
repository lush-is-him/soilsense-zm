"""GET /i18n/{lang}: all user-facing strings for the dashboard (FR12)."""

import os

from fastapi import APIRouter, HTTPException

from engine.i18n import LANGUAGES, _strings, text

router = APIRouter(tags=["Language"])

NAMES = {"en": "English", "toi": "Tonga", "ny": "Nyanja"}


def offered():
    """Languages shown in the dashboard. Nyanja is a draft no native speaker has checked, so it is
    hidden unless SOILSENSE_SHOW_NYANJA=1 (for example to show the draft in a presentation)."""
    show_ny = os.environ.get("SOILSENSE_SHOW_NYANJA", "").strip().lower() in ("1", "yes", "true", "on")
    return [code for code in ("en", "toi", "ny") if code != "ny" or show_ny]


@router.get("/languages")
def languages():
    return [{"code": code, "name": NAMES[code]} for code in offered()]


@router.get("/i18n/{lang}")
def strings(lang: str):
    if lang not in LANGUAGES:
        raise HTTPException(404, f"Language must be one of {', '.join(LANGUAGES)}")
    return {key: text(key, lang) for key in _strings("en")}
