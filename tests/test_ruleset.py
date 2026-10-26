"""Spec 0 rule 3, S1-7: rule tables load and the validator enforces provenance."""

import pytest
import yaml

from engine.ruleset import RuleError, load

GOOD = {"id": "X-1", "domain": "lime", "status": "draft", "source_type": "proposed",
        "source_doc": None, "reviewer_alias": None, "data": {"value": 1}}


def write(tmp_path, *entries):
    (tmp_path / "test.yaml").write_text(yaml.safe_dump({"rules": list(entries)}))
    return tmp_path


def test_project_rules_load_and_report_open_items():
    ruleset = load()
    assert "BAND-01" in ruleset.rules and ruleset.crop("maize") is not None
    open_paths = {(i["rule"], i["path"]) for i in ruleset.open_items}
    assert ("LIME-TRIGGER", "trigger_ph") in open_paths
    assert ("LIME-PARTIAL", "partial_approach") in open_paths
    assert ("CROP-MAIZE", "top_dress.rate_kg_ha") in open_paths


def test_no_project_rule_is_verified_yet():
    assert all(rule.status != "verified" for rule in load().rules.values())


def test_rule_without_source_type_rejected(tmp_path):
    entry = {k: v for k, v in GOOD.items() if k != "source_type"}
    with pytest.raises(RuleError, match="missing 'source_type'"):
        load(write(tmp_path, entry))


def test_unknown_status_rejected(tmp_path):
    with pytest.raises(RuleError, match="status"):
        load(write(tmp_path, {**GOOD, "status": "approved"}))


def test_agr1_expert_opinion_cannot_be_verified(tmp_path):
    entry = {**GOOD, "status": "verified", "source_type": "expert_opinion", "reviewer_alias": "AGR-1"}
    with pytest.raises(RuleError, match="cannot be 'verified'"):
        load(write(tmp_path, entry))


def test_published_source_or_second_reviewer_can_verify(tmp_path):
    published = {**GOOD, "id": "X-1", "status": "verified", "source_type": "published",
                 "source_doc": "ZARI guide (year)"}
    reviewed = {**GOOD, "id": "X-2", "status": "verified", "source_type": "expert_opinion",
                "reviewer_alias": "AGR-2"}
    assert set(load(write(tmp_path, published, reviewed)).rules) == {"X-1", "X-2"}


def test_ph_rule_must_state_method(tmp_path):
    with pytest.raises(RuleError, match="ph_method"):
        load(write(tmp_path, {**GOOD, "domain": "crop"}))


def test_duplicate_ids_rejected(tmp_path):
    with pytest.raises(RuleError, match="duplicate"):
        load(write(tmp_path, GOOD, GOOD))
