"""Look up user-facing text by key (spec 2.1 Translator, FR12).

Falls back to English when a key is missing in the requested language and
marks the result unreviewed, so the UI can show the marker.
"""

from functools import lru_cache
from pathlib import Path

import yaml

I18N_DIR = Path(__file__).resolve().parent.parent / "i18n"
LANGUAGES = ("en", "ny", "toi")


class _KeepMissing(dict):
    """Leave {placeholders} without a value in place (the dashboard fills them)."""

    def __missing__(self, key):
        return "{" + key + "}"


@lru_cache(maxsize=None)
def _strings(lang):
    path = I18N_DIR / f"{lang}.yaml"
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def text(key, lang="en", **params):
    """Return {"key", "lang", "text", "reviewed"} for one string."""
    entry = _strings(lang).get(key)
    used = lang
    if entry is None:
        entry, used = _strings("en").get(key), "en"
    if entry is None:
        return {"key": key, "lang": used, "text": key, "reviewed": False}
    reviewed = bool(entry.get("reviewed")) and used == lang
    return {"key": key, "lang": used, "text": entry["text"].format_map(_KeepMissing(params)), "reviewed": reviewed}
