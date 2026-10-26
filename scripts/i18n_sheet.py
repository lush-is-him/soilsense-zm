"""Translation review sheet for native Nyanja and Tonga reviewers (FR12, task H5).

    python scripts/i18n_sheet.py export     # writes docs/translations/review_sheet.csv
    python scripts/i18n_sheet.py import     # reads it back into i18n/ny.yaml and i18n/toi.yaml

The reviewer writes the corrected text in `nyanja_final` / `tonga_final` and
their alias (not their name if they prefer) in `nyanja_reviewer` /
`tonga_reviewer`. On import, a string with both becomes reviewed: true; a
string with only a final text stays reviewed: false. Keep {placeholders}
such as {crop} exactly as they are.
"""

import csv
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "i18n"
SHEET = ROOT / "docs" / "translations" / "review_sheet.csv"
LANGS = {"nyanja": "ny", "tonga": "toi"}
FIELDS = ["key", "english"] + [f"{name}_{part}" for name in LANGS for part in ("draft", "final", "reviewer")]
HEADER = {"ny": "# Nyanja (ny). Imported from docs/translations/review_sheet.csv.\n",
          "toi": "# Tonga (toi). Imported from docs/translations/review_sheet.csv.\n"}


def load(code):
    path = I18N / f"{code}.yaml"
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def placeholders(text):
    return set(re.findall(r"\{(\w+)\}", text or ""))


def export(path=SHEET):
    english = load("en")
    drafts = {code: load(code) for code in LANGS.values()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for key, entry in english.items():
            row = {"key": key, "english": entry["text"]}
            for name, code in LANGS.items():
                current = drafts[code].get(key) or {}
                row[f"{name}_draft"] = current.get("text", "")
                row[f"{name}_final"] = current.get("text", "") if current.get("reviewed") else ""
                row[f"{name}_reviewer"] = current.get("reviewer", "")
            writer.writerow(row)
    print(f"Wrote {path} ({len(english)} strings)")


def import_sheet(path=SHEET):
    english = load("en")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    problems = []
    for name, code in LANGS.items():
        out = {}
        for row in rows:
            key = row["key"]
            if key not in english:
                problems.append(f"{key}: not an English key")
                continue
            final = (row.get(f"{name}_final") or "").strip()
            reviewer = (row.get(f"{name}_reviewer") or "").strip()
            text = final or (row.get(f"{name}_draft") or "").strip()
            if not text:
                continue
            if placeholders(text) != placeholders(english[key]["text"]):
                problems.append(f"{code} {key}: placeholders must be {sorted(placeholders(english[key]['text']))}")
                continue
            entry = {"text": text, "reviewed": bool(final and reviewer)}
            if final and reviewer:
                entry["reviewer"] = reviewer
            out[key] = entry
        if problems:
            continue
        body = yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=1000)
        (I18N / f"{code}.yaml").write_text(HEADER[code] + body, encoding="utf-8")
        reviewed = sum(e["reviewed"] for e in out.values())
        print(f"{code}: {len(out)} strings, {reviewed} reviewed")
    if problems:
        print("Not imported:\n  " + "\n  ".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "export":
        export()
    elif action == "import":
        sys.exit(import_sheet())
    else:
        print(__doc__)
        sys.exit(2)
