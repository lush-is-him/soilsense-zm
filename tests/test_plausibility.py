"""Probe problem or unusual soil? (engine.plausibility)"""

import pytest

from engine.plausibility import assess


@pytest.mark.parametrize("ph, kw, status", [
    (6.2, dict(map_ph=6.1, calibration_age_hours=2), "ok"),
    (6.2, dict(map_ph=6.1, calibration_age_hours=30), "check_probe"),            # not calibrated today
    (6.2, dict(map_ph=6.1, calibration_age_hours=None), "check_probe"),          # no calibration known
    (8.9, dict(map_ph=8.7, calibration_age_hours=2), "check_probe"),             # extreme, no repeat
    (8.9, dict(map_ph=8.7, calibration_age_hours=2, previous_ph=8.8), "confirm_lab"),  # repeat agrees
    (7.8, dict(map_ph=6.1, calibration_age_hours=2), "check_probe"),             # 1.7 from the map
    (7.8, dict(map_ph=6.1, calibration_age_hours=2, previous_ph=7.7), "confirm_lab"),
    (7.8, dict(map_ph=6.1, calibration_age_hours=2, previous_ph=6.9), "check_probe"),  # repeat disagrees
    (6.9, dict(map_ph=6.2, calibration_age_hours=2), "ok"),                      # 0.7 from the map: normal
    (4.2, dict(map_ph=None, calibration_age_hours=1, previous_ph=4.3), "confirm_lab"),
])
def test_plausibility(ph, kw, status):
    assert assess(ph, **kw).status == status


def test_extreme_without_repeat_suggests_the_lab_and_a_retest():
    result = assess(9.2, map_ph=None, calibration_age_hours=1)
    assert result.refer_lab and "check.retest" in result.reasons and "check.extreme_high" in result.reasons


def test_reasons_are_translatable_keys():
    import yaml
    from pathlib import Path
    english = yaml.safe_load((Path(__file__).resolve().parent.parent / "i18n" / "en.yaml").read_text())
    result = assess(3.9, map_ph=6.0, calibration_age_hours=40, previous_ph=3.9)
    assert result.reasons and all(r in english for r in result.reasons)
