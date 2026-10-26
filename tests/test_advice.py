"""Spec 6, 10, NFR8: rule engine. Every rule ID fires in at least one test."""

import copy
from datetime import date

import pytest

from engine.advice import AdviceRequest, Advisor
from engine.ruleset import load

AUG = date(2026, 8, 1)      # well before the Nov-Dec window
OCT = date(2026, 10, 25)
DEC = date(2026, 12, 15)

FIRED = set()


@pytest.fixture(scope="module")
def rules():
    return load()


@pytest.fixture
def water_rules(rules):
    """Rules read as water pH, so outcomes are not method-sensitive."""
    fixed = copy.deepcopy(rules)
    fixed["BAND-01"].ph_method = "water"
    return fixed


def advise(ruleset, ph, crop="maize", *, method="water", trust="low", when=AUG,
           texture="loamy", source="field_check", water="rainfed"):
    result = Advisor(ruleset).advise(AdviceRequest(
        ph=ph, ph_method=method, trust_level=trust, crop=crop, as_of_date=when,
        texture=texture, texture_source=source, water=water))
    FIRED.update(r["id"] for r in result["fired_rules"])
    return result


# ----- refusals -----

def test_ref01_failed_reading_gives_no_advice(water_rules):
    result = advise(water_rules, 5.0, trust="none")
    assert result["refusals"] == ["REF-01"] and result["plan_a"] is None


@pytest.mark.parametrize("ph, refused", [(4.49, True), (4.5, False)])
def test_ref02_below_45_refused(water_rules, ph, refused):
    result = advise(water_rules, ph)
    assert ("REF-02" in result["refusals"]) is refused
    if refused:
        assert result["plan_a"] is None and result["plan_c"]["crops"] == []


def test_ref03_no_lime_quantity_without_texture(water_rules):
    lime = advise(water_rules, 5.0, texture=None, source=None)["plan_a"]["lime"]
    assert lime["rate_t_ha"] is None and lime["note"] == "ref.REF-03"


def test_map_texture_only_counts_when_trust_moderate(water_rules):
    low = advise(water_rules, 5.0, texture="Clay Loam", source="map", trust="low")
    moderate = advise(water_rules, 5.0, texture="Clay Loam", source="map", trust="moderate")
    assert "REF-03" in low["refusals"]
    assert moderate["plan_a"]["lime"]["texture_group"] == "clay"


def test_ref04_ph_above_crop_maximum(water_rules):
    result = advise(water_rules, 7.8, crop="maize")
    assert "REF-04" in result["refusals"] and result["plan_a"]["status"] == "ph_too_high"


def test_ref05_too_late_to_lime(water_rules):
    result = advise(water_rules, 5.0, when=DEC)
    assert "REF-05" in result["refusals"] and result["plan_a"]["lime"]["timing"] == "too_late"


def test_ref06_method_sensitive_advice_has_no_quantities(rules):
    result = advise(rules, 5.6)                     # 5.6 water vs 4.8-5.1 if the bands are CaCl2
    assert result["method_sensitive"] and "REF-06" in result["refusals"]
    assert result["plan_a"] == {"status": "lab_test_recommended", "note": "ref.REF-06"}
    assert len(result["alternatives"]) == 3


def test_ref07_severe_clay_clamped(water_rules):
    capped = copy.deepcopy(water_rules)
    capped["LIME-MAX"].data["max_single_application_t_ha"] = 4
    capped["REF-02"].data["refuse_below_ph"] = 4.0
    result = advise(capped, 4.2, texture="clay")
    assert "REF-07" in result["refusals"] and result["plan_a"]["lime"]["rate_t_ha"] == [3.5, 4]


# ----- bands and lime -----

@pytest.mark.parametrize("ph, band", [(4.5, "moderate"), (5.49, "moderate"), (5.5, "slight"),
                                      (6.5, "slight"), (6.51, "suitable")])
def test_band_edges(water_rules, ph, band):
    assert Advisor(water_rules)._band(ph) == band


def test_moderate_loamy_lime_rate_and_per_lima(water_rules):
    lime = advise(water_rules, 5.0)["plan_a"]["lime"]
    assert lime["status"] == "advised" and lime["rate_t_ha"] == [1.5, 2.0]
    assert lime["per_lima"] == {"low": 375.0, "high": 500.0, "unit": "kg"}


def test_slightly_acidic_lime_is_optional(water_rules):
    lime = advise(water_rules, 6.0)["plan_a"]["lime"]
    assert lime["status"] == "optional" and lime["note"] == "lime.optional"


def test_suitable_ph_needs_no_lime(water_rules):
    result = advise(water_rules, 6.8)
    assert result["plan_a"]["lime"]["status"] == "not_needed"
    assert "MSG-01" not in [m["key"].split(".")[1] for m in result["messages"]]


def test_usda_texture_mapped_to_group(water_rules):
    lime = advise(water_rules, 5.0, texture="Sandy Clay Loam", source="lab")["plan_a"]["lime"]
    assert lime["texture_group"] == "loamy"


# ----- lime timing (REF-05, C-7) -----

@pytest.mark.parametrize("when, crop, timing", [
    (AUG, "maize", "ok"), (OCT, "maize", "uncertain"), (DEC, "maize", "too_late"),
    (OCT, "sunflower", "uncertain"), (date(2027, 1, 20), "sunflower", "too_late")])
def test_lime_timing_per_crop(water_rules, when, crop, timing):
    assert advise(water_rules, 5.2, crop=crop, when=when)["plan_a"]["lime"]["timing"] == timing


def test_irrigated_can_lime_any_time(water_rules):
    lime = advise(water_rules, 5.0, when=DEC, water="irrigated")["plan_a"]["lime"]
    assert lime["timing"] == "any_time"


# ----- fertiliser, manure, cautions -----

def test_maize_basal_rate_and_open_top_dress(water_rules):
    fert = advise(water_rules, 5.0)["plan_a"]["fertiliser"]
    assert fert["basal"]["rate_kg_ha"] == 200
    assert fert["top_dress"]["rate_kg_ha"] is None and fert["top_dress"]["note"] == "rate.open"


def test_manure_per_lima_derived_from_tonnes_per_ha(water_rules):
    assert advise(water_rules, 5.0)["plan_a"]["manure"] == {"low": 1.25, "high": 3.75, "unit": "t"}


@pytest.mark.parametrize("crop, msg", [("soybean", "msg.MSG-05"), ("maize", "msg.MSG-06")])
def test_crop_cautions(water_rules, crop, msg):
    keys = [m["key"] for m in advise(water_rules, 6.0, crop=crop)["messages"]]
    assert msg in keys and "msg.MSG-07" in keys and "msg.MSG-08" in keys


def test_lime_messages_when_lime_advised(water_rules):
    keys = [m["key"] for m in advise(water_rules, 5.0)["messages"]]
    assert {"msg.MSG-01", "msg.MSG-02", "msg.MSG-03", "msg.MSG-04"} <= set(keys)


# ----- crops out of scope or without data -----

def test_sorghum_has_no_data(water_rules):
    assert advise(water_rules, 6.0, crop="sorghum")["plan_a"]["status"] == "no_data"


def test_groundnut_pending_supervisor_decision(water_rules):
    assert advise(water_rules, 6.0, crop="groundnut")["plan_a"]["status"] == "crop_not_confirmed"


# ----- Plans B and C -----

def test_plan_b_blocked(water_rules):
    assert advise(water_rules, 5.0)["plan_b"]["status"] == "blocked"


def test_plan_c_millet_first_then_lowest_workable(water_rules):
    assert advise(water_rules, 5.6)["plan_c"]["crops"] == ["millet", "sunflower", "maize", "soybean"]
    assert advise(water_rules, 4.9)["plan_c"]["crops"] == ["millet"]


def test_plan_c_excludes_crops_above_their_maximum(water_rules):
    assert advise(water_rules, 7.8, crop="sunflower")["plan_c"]["crops"] == ["sunflower"]


# ----- method handling (spec 2.6) -----

def test_lab_cacl2_converted_when_rules_are_water(water_rules):
    result = advise(water_rules, 4.8, method="cacl2", trust="high", source="lab")
    assert result["method_sensitive"]          # 5.3 (moderate) vs 5.6 (slight)


def test_not_method_sensitive_when_all_readings_agree(rules):
    result = advise(rules, 6.4)                     # 6.4, 5.9, 5.6: all slight, same Plan C
    assert not result["method_sensitive"] and result["alternatives"] == []
    assert result["plan_a"]["lime"]["rate_t_ha"] == [0.5, 1.0]


def test_advice_records_trust_and_unreviewed(water_rules):
    result = advise(water_rules, 5.0, trust="moderate")
    assert result["trust_level"] == "moderate" and result["unreviewed"]
    assert result["trust_text"]["key"] == "trust.moderate"
    assert all({"id", "status", "source_type"} <= set(r) for r in result["fired_rules"])


def test_borderline_flag(water_rules):
    assert advise(water_rules, 5.4)["borderline"]


# ----- OPEN and CONFLICT items stay stubbed (spec 0 rule 2) -----

@pytest.mark.xfail(strict=True, reason="OPEN: LIME-TRIGGER trigger_ph (C-3, question 3)")
def test_lime_trigger_confirmed(rules):
    assert rules["LIME-TRIGGER"].data["trigger_ph"] != "OPEN"


@pytest.mark.xfail(strict=True, reason="CONFLICT: Plan B lime-at-planting rate (C-2) and priority order (I2)")
def test_plan_b_available(water_rules):
    assert advise(water_rules, 5.0)["plan_b"]["status"] != "blocked"


@pytest.mark.xfail(strict=True, reason="CONFLICT: lime lead time 2-3 vs 1-2 months (C-7, question 4)")
def test_lime_lead_time_resolved(rules):
    assert rules["LIME-LEAD-TIME"].data["lead_time_before_planting_months"] != "CONFLICT"


@pytest.mark.xfail(strict=True, reason="OPEN: maize top-dressing rate (G1, question 8)")
def test_maize_top_dress_rate(water_rules):
    assert advise(water_rules, 5.0)["plan_a"]["fertiliser"]["top_dress"]["rate_kg_ha"]


@pytest.mark.xfail(strict=True, reason="OPEN: household measures (section H, task H3)")
def test_household_measures(rules):
    assert rules["MEAS-HOUSEHOLD"].data["containers"] != "OPEN"


@pytest.mark.xfail(strict=True, reason="OPEN: pH method of the bands and crop table (C-4, question 1)")
def test_ph_method_confirmed(rules):
    assert rules["BAND-01"].ph_method != "unconfirmed"


# ----- NFR8: every rule fires somewhere -----

def test_zz_every_rule_id_fired_in_some_test(rules):
    advise(load(), 5.0, crop="millet")
    advise(load(), 5.0, crop="sunflower")
    missing = set(rules.rules) - FIRED
    assert not missing, f"rules never fired in tests: {sorted(missing)}"
