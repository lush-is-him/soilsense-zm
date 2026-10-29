"""Read a translator's Google Form answers into the translation files.

    python scripts/i18n_form_import.py RESPONSES.csv --lang ny
    python scripts/i18n_form_import.py RESPONSES.csv --lang toi --row 2

RESPONSES.csv is the form's response sheet, downloaded with
File > Download > Comma-separated values. --row picks the translator
(1 = first response, the default). Answers go into
docs/translations/review_sheet.csv (an answer of "OK" accepts the draft)
and from there into i18n/<lang>.yaml, marked reviewed under the
translator's alias. Key words go to docs/translations/glossary_<lang>.csv.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import i18n_sheet  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KEYS = ROOT / "docs" / "translations" / "form_keys.json"
CODE = re.compile(r"^([WCS])(\d+)\.")
COLUMN = {"ny": "nyanja", "toi": "tonga"}


def answers_from(row):
    """{('S', 7): 'answer', ...} from one response row."""
    found = {}
    for title, value in row.items():
        match = CODE.match((title or "").strip())
        if match and (value or "").strip():
            found[(match.group(1), int(match.group(2)))] = value.strip()
    return found


def translator_alias(row, lang, given):
    if given:
        return given
    name = next((v for k, v in row.items() if k and k.startswith("Your name")), "").strip()
    anonymous = any(k and k.startswith("May we thank") and (v or "").startswith("No") for k, v in row.items())
    if name and not anonymous:
        return name
    return f"{lang.upper()}-translator"


def apply(responses_path, lang, row_number=1, alias=None, sheet=i18n_sheet.SHEET):
    keys = json.loads(KEYS.read_text(encoding="utf-8"))
    with open(responses_path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not 1 <= row_number <= len(rows):
        raise SystemExit(f"{responses_path} has {len(rows)} responses; --row must be 1 to {len(rows)}")
    row = rows[row_number - 1]
    answers = answers_from(row)
    who = translator_alias(row, lang, alias)
    column = COLUMN[lang]

    if not sheet.exists():
        i18n_sheet.export(sheet)
    with sheet.open(newline="", encoding="utf-8") as handle:
        sheet_rows = list(csv.DictReader(handle))
    by_key = {r["key"]: r for r in sheet_rows}

    updated = 0
    for kind in ("C", "S"):
        for number, key in enumerate(keys[kind], 1):
            answer = answers.get((kind, number))
            if not answer or key not in by_key:
                continue
            draft = by_key[key].get(f"{column}_draft", "")
            final = draft if answer.strip().lower() in {"ok", "ok.", "correct"} and draft else answer
            by_key[key][f"{column}_final"] = final
            by_key[key][f"{column}_reviewer"] = who
            updated += 1
    with sheet.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=i18n_sheet.FIELDS)
        writer.writeheader()
        writer.writerows(sheet_rows)

    glossary_path = sheet.parent / f"glossary_{lang}.csv"
    with glossary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["code", "english", lang, "translator"])
        for number, word in enumerate(keys["W"], 1):
            writer.writerow([f"W{number}", word, answers.get(("W", number), ""), who])

    print(f"{lang}: {updated} strings from {who}; key words in {glossary_path.name}")
    return i18n_sheet.import_sheet(sheet)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("responses")
    parser.add_argument("--lang", choices=sorted(COLUMN), required=True)
    parser.add_argument("--row", type=int, default=1)
    parser.add_argument("--alias", help="name or alias to record as the reviewer")
    args = parser.parse_args()
    return apply(args.responses, args.lang, args.row, args.alias)


if __name__ == "__main__":
    sys.exit(main())
