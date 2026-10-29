"""Translations: every language key exists in English, placeholders match, sheet round trip."""

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import i18n_sheet  # noqa: E402
from engine.i18n import text  # noqa: E402

I18N = Path(__file__).resolve().parent.parent / "i18n"


def keys(code):
    return yaml.safe_load((I18N / f"{code}.yaml").read_text()) or {}


def test_translations_only_use_english_keys_and_placeholders():
    english = keys("en")
    for code in ("ny", "toi"):
        for key, entry in keys(code).items():
            assert key in english, f"{code}: unknown key {key}"
            assert set(re.findall(r"\{(\w+)\}", entry["text"])) == set(re.findall(r"\{(\w+)\}", english[key]["text"]))


def test_engine_uses_only_defined_message_keys():
    english = keys("en")
    for n in range(1, 9):
        assert f"msg.MSG-0{n}" in english
    for n in range(1, 8):
        assert f"ref.REF-0{n}" in english


def test_missing_translation_falls_back_to_english_unreviewed():
    result = text("ref.REF-01", "toi")
    assert result["lang"] == "en" and result["reviewed"] is False


def test_nothing_is_marked_reviewed_yet():
    for code in ("en", "ny", "toi"):
        assert not any(e.get("reviewed") for e in keys(code).values())


def test_sheet_round_trip_marks_reviewed(tmp_path, monkeypatch):
    for code in ("en", "ny", "toi"):
        (tmp_path / f"{code}.yaml").write_text((I18N / f"{code}.yaml").read_text())
    monkeypatch.setattr(i18n_sheet, "I18N", tmp_path)
    sheet = tmp_path / "sheet.csv"
    i18n_sheet.export(sheet)
    rows = sheet.read_text(encoding="utf-8").splitlines()
    import csv
    data = list(csv.DictReader(rows))
    for row in data:
        if row["key"] == "ui.lime":
            row["tonga_final"], row["tonga_reviewer"] = "Laimu", "TR-1"
        if row["key"] == "ref.REF-04":
            row["nyanja_final"] = "pH ndi yokwera kwa {crop}."      # final but no reviewer
    with sheet.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=i18n_sheet.FIELDS)
        writer.writeheader()
        writer.writerows(data)
    assert i18n_sheet.import_sheet(sheet) == 0
    toi = yaml.safe_load((tmp_path / "toi.yaml").read_text())
    ny = yaml.safe_load((tmp_path / "ny.yaml").read_text())
    assert toi["ui.lime"] == {"text": "Laimu", "reviewed": True, "reviewer": "TR-1"}
    assert ny["ref.REF-04"]["reviewed"] is False


def test_sheet_import_rejects_broken_placeholder(tmp_path, monkeypatch):
    for code in ("en", "ny", "toi"):
        (tmp_path / f"{code}.yaml").write_text((I18N / f"{code}.yaml").read_text())
    monkeypatch.setattr(i18n_sheet, "I18N", tmp_path)
    sheet = tmp_path / "sheet.csv"
    sheet.write_text("key,english,nyanja_draft,nyanja_final,nyanja_reviewer,tonga_draft,tonga_final,tonga_reviewer\n"
                     "ref.REF-04,x,,pH yokwera,NR-1,,,\n", encoding="utf-8")
    assert i18n_sheet.import_sheet(sheet) == 1


def test_form_import_ok_accepts_draft_and_corrections(tmp_path, monkeypatch):
    import csv as _csv
    import json

    import i18n_form_import
    for code in ("en", "ny", "toi"):
        (tmp_path / f"{code}.yaml").write_text((I18N / f"{code}.yaml").read_text())
    monkeypatch.setattr(i18n_sheet, "I18N", tmp_path)
    sheet = tmp_path / "review_sheet.csv"
    keys = json.loads(i18n_form_import.KEYS.read_text())
    english = yaml.safe_load((I18N / "en.yaml").read_text())
    s1, s_crop = keys["S"].index("msg.MSG-01") + 1, keys["S"].index("ref.REF-04") + 1
    responses = tmp_path / "responses.csv"
    header = ["Timestamp", "Your name or initials", "May we thank you by name in the dissertation?",
              f"S{s1}. {english['msg.MSG-01']['text']}", f"S{s_crop}. {english['ref.REF-04']['text']}",
              "C1. maize", "W1. lime (agricultural lime for acid soil)"]
    with responses.open("w", newline="", encoding="utf-8") as handle:
        writer = _csv.writer(handle)
        writer.writerow(header)
        writer.writerow(["2026-10-29", "M.B.", "No, keep me anonymous", "OK", "pH ili pamwamba kwa {crop}.", "chimanga", "laimu"])
    assert i18n_form_import.apply(responses, "ny", sheet=sheet) == 0
    ny = yaml.safe_load((tmp_path / "ny.yaml").read_text())
    draft = yaml.safe_load((I18N / "ny.yaml").read_text())["msg.MSG-01"]["text"]
    assert ny["msg.MSG-01"] == {"text": draft, "reviewed": True, "reviewer": "NY-translator"}
    assert ny["ref.REF-04"]["text"] == "pH ili pamwamba kwa {crop}." and ny["ref.REF-04"]["reviewed"]
    assert ny["crop.maize"]["reviewed"]
    assert "laimu" in (tmp_path / "glossary_ny.csv").read_text()
