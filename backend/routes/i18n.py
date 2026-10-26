"""GET /i18n/{lang}: all user-facing strings for the dashboard (FR12)."""

from fastapi import APIRouter, HTTPException

from engine.i18n import LANGUAGES, _strings, text

router = APIRouter(tags=["Language"])


@router.get("/i18n/{lang}")
def strings(lang: str):
    if lang not in LANGUAGES:
        raise HTTPException(404, f"Language must be one of {', '.join(LANGUAGES)}")
    return {key: text(key, lang) for key in _strings("en")}
