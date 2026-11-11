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
def unconfirmed_rules(rules):
    """Rules as before AGR-2 answered: pH method unconfirmed, so method-sensitive."""
    variant = copy.deepcopy(rules)
    variant["BAND-01"].ph_method = "unconfirmed"
    return variant


@pytest.fixture
def water_rules(rules):
    """Rules read as water pH, so outcomes are not method-sensitive."""
    fixed = copy.deepcopy(rules)
    fixed["BAND-01"].ph_method = "water"
    return fixed


def advise(ruleset, ph, crop="maize", *, method="water", trust="low", when=AUG,
           texture="loamy", source="field_check", water="rainfed", budget="low"):
    result = Advisor(ruleset).advise(AdviceRequest(
        ph=ph, ph_method=method, trust_level=trust, crop=crop, as_of_date=when,
        texture=texture, texture_source=source, water=water, budget_band=budget))
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
    assert moderate["plan_a"]["lime"]["texture_group"] == "loamy"      # AGR-2: Clay Loam is loamy


def test_ref04_ph_above_crop_maximum(water_rules):
    result = advise(water_rules, 7.8, crop="maize")
    assert "REF-04" in result["refusals"] and result["plan_a"]["status"] == "ph_too_high"


def test_ref05_too_late_to_lime(water_rules):
    result = advise(water_rules, 5.0, when=DEC)
    assert "REF-05" in result["refusals"] and result["plan_a"]["lime"]["timing"] == "too_late"


def test_ref06_method_sensitive_advice_has_no_quantities(unconfirmed_rules):
    result = advise(unconfirmed_rules, 5.6)                     # 5.6 water vs 4.8-5.1 if the bands are CaCl2
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
    per_lima = lime["per_lima"]
    assert (per_lima["low"], per_lima["high"], per_lima["unit"]) == (375.0, 500.0, "kg")
    assert per_lima["household"] == [{"container": "50 kg bag", "low": 7.5, "high": 10.0}]
    assert per_lima["cost"] is None                  # prices OPEN (H4)


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

def test_maize_fertiliser_rates_from_agr2(water_rules):
    fert = advise(water_rules, 5.0)["plan_a"]["fertiliser"]
    assert fert["basal"]["rate_kg_ha"] == [200, 350] and fert["top_dress"]["rate_kg_ha"] == [150, 350]
    assert fert["basal"]["per_lima"]["low"] == 50.0 and fert["basal"]["per_lima"]["high"] == 87.5


def test_soybean_needs_no_top_dressing(water_rules):
    top = advise(water_rules, 6.0, crop="soybean")["plan_a"]["fertiliser"]["top_dress"]
    assert top["none"] and top["note"] == "fert.none"                 # AGR-2 follow-up N6


@pytest.mark.parametrize("crop, ph, status", [
    ("maize", 5.4, "advised"), ("maize", 5.6, "optional"),
    ("millet", 5.2, "optional"), ("millet", 4.9, "advised"),          # millet trigger 5.0
    ("groundnut", 5.6, "advised"), ("groundnut", 5.9, "optional"),    # groundnut trigger 5.8
    ("soybean", 5.6, "optional"), ("sunflower", 5.4, "advised")])
def test_lime_trigger_per_crop(water_rules, crop, ph, status):
    assert advise(water_rules, ph, crop=crop)["plan_a"]["lime"]["status"] == status


def test_manure_per_lima_derived_from_tonnes_per_ha(water_rules):
    manure = advise(water_rules, 5.0)["plan_a"]["manure"]
    assert (manure["low"], manure["high"], manure["unit"]) == (1.25, 3.75, "t")
    assert manure["household"] is None               # manure containers not weighed yet


@pytest.mark.parametrize("crop, msg", [("soybean", "msg.MSG-05"), ("maize", "msg.MSG-06")])
def test_crop_cautions(water_rules, crop, msg):
    keys = [m["key"] for m in advise(water_rules, 6.0, crop=crop)["messages"]]
    assert msg in keys and "msg.MSG-07" in keys and "msg.MSG-08" in keys


def test_lime_messages_when_lime_advised(water_rules):
    keys = [m["key"] for m in advise(water_rules, 5.0)["messages"]]
    assert {"msg.MSG-01", "msg.MSG-02", "msg.MSG-03", "msg.MSG-04"} <= set(keys)


# ----- crops out of scope or without data -----

def test_crop_without_data_gives_no_plan(water_rules):
    no_data = copy.deepcopy(water_rules)
    no_data["CROP-MILLET"].data["ph"] = "OPEN"
    assert advise(no_data, 6.0, crop="millet")["plan_a"]["status"] == "no_data"


def test_crop_not_in_scope_gives_no_plan(water_rules):
    pending = copy.deepcopy(water_rules)
    pending["CROP-MILLET"].data["in_scope"] = "pending_supervisor_decision"
    assert advise(pending, 6.0, crop="millet")["plan_a"]["status"] == "crop_not_confirmed"


def test_groundnut_in_scope(water_rules):
    result = advise(water_rules, 6.0, crop="groundnut")
    assert result["plan_a"]["status"] == "ok"
    assert result["plan_a"]["fertiliser"]["top_dress"]["rate_kg_ha"] == [200, 400]


def test_sorghum_removed(rules):
    assert rules.crop("sorghum") is None


# ----- Plans B and C -----

def test_plan_b_blocked_without_priority_order(water_rules):
    blocked = copy.deepcopy(water_rules)
    blocked["PLAN-B"].data["priority_order"] = "OPEN"
    assert advise(blocked, 5.0)["plan_b"]["status"] == "blocked"


def test_plan_b_budget_reach_from_agr2(water_rules):
    low = advise(water_rules, 5.0)["plan_b"]
    assert low["status"] == "ok" and low["mode"] == "budget"
    assert [i["item"] for i in low["items"]] == ["seed", "fertiliser"] and low["left_out"] == ["lime", "manure"]
    plan_b = advise(water_rules, 5.0, budget="medium")["plan_b"]
    assert [i["item"] for i in plan_b["items"]] == ["seed", "fertiliser", "lime"]
    lime = plan_b["items"][2]                     # 15 g x 53,333 stations/ha = 800 kg/ha
    assert lime["g_per_station"] == [15, 15] and lime["per_lima"]["low"] == pytest.approx(200, abs=0.1)
    fertiliser = plan_b["items"][1]               # low end of the basal range
    assert fertiliser["per_lima"]["low"] == fertiliser["per_lima"]["high"] == 50.0


def test_plan_c_millet_first_then_lowest_workable(water_rules):
    assert advise(water_rules, 5.6)["plan_c"]["crops"] == ["millet", "groundnut", "sunflower", "maize", "soybean"]
    assert advise(water_rules, 4.9)["plan_c"]["crops"] == ["millet"]


def test_plan_c_excludes_crops_above_their_maximum(water_rules):
    assert advise(water_rules, 7.8, crop="sunflower")["plan_c"]["crops"] == ["sunflower"]


def with_plan_b(ruleset, partial, order=("lime", "fertiliser", "seed", "manure"), counts=None):
    filled = copy.deepcopy(ruleset)
    filled["PLAN-B"].data.update(priority_order=list(order), items_by_budget=counts or {"low": 2, "medium": 3})
    filled["LIME-PARTIAL"].data["partial_approach"] = partial
    return filled


def test_plan_b_per_station_lime_and_priority(water_rules):
    ruleset = with_plan_b(water_rules, {"method": "per_station", "g_per_station": [4, 8]})
    plan_b = advise(ruleset, 5.0)["plan_b"]
    assert plan_b["status"] == "ok" and [i["item"] for i in plan_b["items"]] == ["lime", "fertiliser"]
    assert plan_b["left_out"] == ["seed", "manure"]
    lime = plan_b["items"][0]                        # 53,333 stations/ha at 75 x 25 cm
    assert lime["per_lima"]["low"] == pytest.approx(53.33, abs=0.01)
    assert lime["per_lima"]["high"] == pytest.approx(106.67, abs=0.01)


def test_plan_b_station_lime_uses_the_experts_spacing(water_rules):
    for crop in ("maize", "soybean", "sunflower"):
        lime = next(i for i in advise(water_rules, 5.0, crop=crop, budget="medium")["plan_b"]["items"] if i["item"] == "lime")
        assert lime["per_lima"]["low"] == pytest.approx(200, abs=0.1), crop


def test_plan_b_medium_budget_gets_more_items(water_rules):
    ruleset = with_plan_b(water_rules, {"method": "per_hectare", "kg_ha": [200, 400]})
    plan_b = Advisor(ruleset).advise(AdviceRequest(5.0, "water", "low", "soybean", AUG, budget_band="medium",
                                                   texture="loamy", texture_source="field_check"))["plan_b"]
    assert [i["item"] for i in plan_b["items"]] == ["lime", "fertiliser", "seed"]
    assert plan_b["items"][0]["per_lima"]["low"] == 50.0


def test_plan_b_not_applicable_when_refused(water_rules):
    ruleset = with_plan_b(water_rules, {"method": "per_hectare", "kg_ha": [200, 400]})
    assert advise(ruleset, 4.2)["plan_b"]["status"] == "not_applicable"


def test_plan_b_no_quantities_when_method_sensitive(unconfirmed_rules):
    ruleset = with_plan_b(unconfirmed_rules, {"method": "per_hectare", "kg_ha": [200, 400]})
    assert advise(ruleset, 5.6)["plan_b"]["status"] == "lab_test_recommended"


def test_household_measures_and_cost_when_supplied(water_rules):
    filled = copy.deepcopy(water_rules)
    bucket = next(c for c in filled["MEAS-HOUSEHOLD"].data["containers"] if c["id"] == "bucket_20l")
    bucket["kg"]["lime"] = 25.0
    filled["PRICE-INPUTS"].data["items"]["lime"]["zmw_per_kg"] = 2.0
    per_lima = advise(filled, 5.0)["plan_a"]["lime"]["per_lima"]
    assert {"container": "20 litre bucket", "low": 15.0, "high": 20.0} in per_lima["household"]
    assert per_lima["cost"]["low"] == 750 and per_lima["cost"]["high"] == 1000


def test_basal_per_lima_in_bags(water_rules):
    basal = advise(water_rules, 5.0)["plan_a"]["fertiliser"]["basal"]
    assert basal["per_lima"]["household"] == [{"container": "50 kg bag", "low": 1.0, "high": 2.0}]


# ----- method handling (spec 2.6) -----

def test_lab_cacl2_converted_when_rules_are_water(water_rules):
    result = advise(water_rules, 4.8, method="cacl2", trust="high", source="lab")
    assert result["method_sensitive"]          # 5.3 (moderate) vs 5.6 (slight)


def test_not_method_sensitive_when_all_readings_agree(unconfirmed_rules):
    result = advise(unconfirmed_rules, 6.4)                     # 6.4, 5.9, 5.6: all slight, same Plan C
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

def test_answers_from_agr2_resolve_c3_c4_c7_and_plan_b(rules):
    assert rules["BAND-01"].ph_method == "water"                                   # C-4
    assert rules["LIME-TRIGGER"].data["trigger_ph"] == 5.5                         # C-3 (maize)
    assert rules["LIME-LEAD-TIME"].data["lead_time_before_planting_months"] == [2, 3]   # C-7
    assert rules["LIME-PARTIAL"].data["partial_approach"]["g_per_station"] == [15, 15]  # C-2
    assert rules["PLAN-B"].data["priority_order"] == ["seed", "fertiliser", "lime", "manure"]  # I2


def test_real_rules_are_no_longer_method_sensitive(rules):
    result = advise(rules, 5.6)
    assert not result["method_sensitive"] and result["plan_a"]["status"] == "ok"


def test_plan_b_budget_bands(rules):
    assert rules["PLAN-B"].data["items_by_budget"] == {"low": 2, "medium": 3}   # AGR-2 follow-up B1-B2


@pytest.mark.xfail(strict=True, reason="OPEN: household measures (section H, task H3)")
def test_household_measures(rules):
    bucket = next(c for c in rules["MEAS-HOUSEHOLD"].data["containers"] if c["id"] == "bucket_20l")
    assert bucket["kg"]["lime"] != "OPEN"


@pytest.mark.xfail(strict=True, reason="OPEN: input prices (task H4)")
def test_prices_supplied(rules):
    assert rules["PRICE-INPUTS"].data["items"]["lime"]["zmw_per_kg"] != "OPEN"


# ----- NFR8: every rule fires somewhere -----

def test_zz_every_rule_id_fired_in_some_test(rules):
    advise(load(), 5.0, crop="millet")
    advise(load(), 5.0, crop="sunflower")
    missing = set(rules.rules) - FIRED
    assert not missing, f"rules never fired in tests: {sorted(missing)}"
