"""Spec 2.3 / S1-5: boundary tests for the reading quality check."""

import pytest

from engine.quality import Calibration, check_calibration, check_reading

GOOD_CAL = Calibration(slope_pct=100.0, temp_c=25.0)
GOOD_REPS = [5.40, 5.45, 5.50]


@pytest.mark.parametrize("slope, ok", [(94.0, False), (95.0, True), (105.0, True), (106.0, False)])
def test_calibration_slope_boundaries(slope, ok):
    assert (check_calibration(slope) == []) is ok
    result = check_reading(GOOD_REPS, 25.0, Calibration(slope, 25.0))
    assert result.accepted is ok


@pytest.mark.parametrize("reps, ok", [([5.40, 5.45, 5.50], True), ([5.40, 5.45, 5.51], False)])
def test_replicate_spread_010_passes_011_fails(reps, ok):
    assert check_reading(reps, 25.0, GOOD_CAL).accepted is ok


def test_accepted_reading_returns_mean():
    result = check_reading(GOOD_REPS, 25.0, GOOD_CAL)
    assert result.accepted and result.ph_mean == 5.45 and result.reasons == []


def test_wrong_number_of_replicates_rejected():
    result = check_reading([5.4, 5.45], 25.0, GOOD_CAL)
    assert not result.accepted and "expected 3 replicates" in result.reasons[0]


@pytest.mark.parametrize("temp, ok", [(30.0, True), (20.0, True), (30.1, False), (19.9, False)])
def test_temperature_inside_calibration_range(temp, ok):
    assert check_reading(GOOD_REPS, temp, GOOD_CAL).accepted is ok


def test_missing_temperature_rejected():
    assert not check_reading(GOOD_REPS, None, GOOD_CAL).accepted


@pytest.mark.parametrize("ph, ok", [(3.4, False), (3.5, True), (9.5, True), (9.6, False)])
def test_implausible_ph_is_probe_fault(ph, ok):
    assert check_reading([ph, ph, ph], 25.0, GOOD_CAL).accepted is ok


def test_no_calibration_rejected():
    result = check_reading(GOOD_REPS, 25.0, None)
    assert not result.accepted and "no valid calibration" in result.reasons


def test_rejected_reading_has_no_ph_and_lists_all_reasons():
    result = check_reading([5.0, 5.5, 5.0], 40.0, Calibration(90.0, 25.0))
    assert result.ph_mean is None and len(result.reasons) == 3


@pytest.mark.xfail(strict=True, reason="OPEN: moisture thresholds need a two-point sensor calibration (spec 2.3)")
def test_waterlogged_reading_rejected():
    result = check_reading(GOOD_REPS, 25.0, GOOD_CAL, moisture=1000)
    assert not result.accepted
