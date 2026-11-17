"""Unit tests for scripts/_indices.py.  Run:  python -m pytest tests -q"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import _indices as ix  # noqa: E402


def test_degree_days_is_zero_when_the_whole_day_is_below_threshold():
    assert ix.degree_days([10.0], [29.0], 30.0)[0] == 0.0


def test_degree_days_equals_mean_excess_when_the_whole_day_is_above():
    assert ix.degree_days([32.0], [38.0], 30.0)[0] == pytest.approx(5.0)


def test_degree_days_registers_a_hot_afternoon_inside_a_mild_day():
    value = ix.degree_days([18.0], [36.0], 30.0)[0]
    assert 0.0 < value < 3.0
    # mean is 27 C, so a mean-based degree day would wrongly report 0


def test_degree_days_matches_the_existing_pipeline_function():
    rng = np.random.default_rng(0)
    tmin = rng.uniform(5, 28, 500)
    tmax = tmin + rng.uniform(0, 18, 500)
    theta = np.arcsin(np.clip((30 - (tmax + tmin) / 2) / np.maximum((tmax - tmin) / 2, 1e-9), -1, 1))
    amp, mid = (tmax - tmin) / 2, (tmax + tmin) / 2
    expected = np.where(tmax <= 30, 0, np.where(
        tmin >= 30, mid - 30,
        ((mid - 30) * (np.pi / 2 - theta) + amp * np.cos(theta)) / np.pi))
    assert np.allclose(ix.degree_days(tmin, tmax, 30.0), np.maximum(expected, 0))


def test_degree_days_propagates_missing_input():
    assert np.isnan(ix.degree_days([np.nan], [35.0], 30.0)[0])


def test_extraterrestrial_radiation_matches_fao56_worked_example():
    # FAO-56 example 8: 20 S on 3 September (day 246) gives 32.2 MJ m-2 day-1
    assert ix.extraterrestrial_radiation(-20.0, 246) == pytest.approx(32.2, abs=0.1)


def test_hargreaves_et0_is_plausible_and_zero_without_a_diurnal_range():
    summer = ix.hargreaves_et0([20.0], [32.0], -12.5, 15)[0]
    assert 4.0 < summer < 8.0
    assert ix.hargreaves_et0([25.0], [25.0], -12.5, 15)[0] == 0.0


def test_rolling_sum_is_nan_until_the_window_fills():
    out = ix.rolling_sum([1, 2, 3, 4], 3)
    assert np.isnan(out[:2]).all()
    assert list(out[2:]) == [6.0, 9.0]


def _monthly(years: int = 40, seed: int = 1):
    rng = np.random.default_rng(seed)
    months = np.tile(np.arange(1, 13), years)
    seasonal = 120 + 100 * np.cos(2 * np.pi * (months - 1) / 12)
    precip = rng.gamma(2.0, seasonal / 2.0)
    et0 = 110 + 40 * np.cos(2 * np.pi * (months - 1) / 12) + rng.normal(0, 8, len(months))
    return precip, et0, months


@pytest.mark.parametrize("scale", [3, 6])
def test_spi_and_spei_are_standardised(scale):
    precip, et0, months = _monthly()
    for index in (ix.spi(precip, months, scale), ix.spei(precip, et0, months, scale)):
        valid = index[np.isfinite(index)]
        assert len(valid) == len(months) - (scale - 1)
        assert abs(valid.mean()) < 0.15
        assert 0.8 < valid.std() < 1.2
        assert np.abs(valid).max() <= ix.Z_LIMIT


def test_spei_ranks_dry_periods_below_wet_ones():
    precip, et0, months = _monthly()
    index = ix.spei(precip, et0, months, 3)
    balance = ix.rolling_sum(precip - et0, 3)
    january = (months == 1) & np.isfinite(index)
    assert np.corrcoef(index[january], balance[january])[0, 1] > 0.95


def test_spi_handles_months_that_are_often_completely_dry():
    precip, _, months = _monthly()
    precip = np.where(np.isin(months, [6, 7, 8]) & (np.arange(len(months)) // 12 % 3 > 0), 0.0, precip)
    index = ix.spi(precip, months, 1)
    assert np.isfinite(index[months == 7]).all()
    assert index[(months == 7) & (precip == 0)].max() < 0


def test_spi_returns_nan_when_the_record_is_too_short():
    precip, _, months = _monthly(years=10)
    assert np.isnan(ix.spi(precip, months, 3)).all()


def test_standardise_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        ix.spi([1.0, 2.0], [1], 1)


def test_longest_run_and_spell_days():
    flags = [1, 1, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1]
    assert ix.longest_run(flags) == 6
    assert ix.spell_days(flags, 6) == 6
    assert ix.spell_days(flags, 3) == 9
    assert ix.longest_run([]) == 0
    assert ix.spell_days([1] * 7, 6) == 7


def test_rolling_max_sum_finds_the_wettest_five_days():
    rain = [0, 0, 10, 20, 30, 5, 0, 0, 0, 50]
    assert ix.rolling_max_sum(rain, 5) == 65.0
    assert ix.rolling_max_sum(rain, 1) == 50.0
    assert np.isnan(ix.rolling_max_sum([1, 2], 5))


def test_saxton_rawls_reproduces_published_texture_class_values():
    # Saxton & Rawls (2006) Table 3, 2.5% organic matter
    loam = ix.saxton_rawls(40, 20, 2.5)
    assert loam["wp"] == pytest.approx(0.14, abs=0.01)
    assert loam["fc"] == pytest.approx(0.28, abs=0.01)
    sand = ix.saxton_rawls(88, 5, 2.5)
    assert sand["wp"] == pytest.approx(0.05, abs=0.01)
    assert sand["fc"] == pytest.approx(0.10, abs=0.01)
    clay = ix.saxton_rawls(20, 50, 2.5)
    assert clay["awc"] == pytest.approx(0.12, abs=0.02)


def test_saxton_rawls_available_water_is_never_negative():
    sand = np.linspace(5, 95, 10)
    out = ix.saxton_rawls(sand, 100 - sand - 2, 0.5)
    assert (out["awc"] >= 0).all()


def test_rolling_sum_missing_value_only_affects_windows_that_contain_it():
    out = ix.rolling_sum([1, 2, np.nan, 4, 5, 6], 2)
    assert np.isnan(out[[0, 2, 3]]).all()
    assert list(out[[1, 4, 5]]) == [3.0, 9.0, 11.0]


def test_rolling_max_sum_does_not_treat_missing_days_as_dry():
    assert np.isnan(ix.rolling_max_sum([1, np.nan, np.nan], 2))
    assert ix.rolling_max_sum([1, np.nan, 3, 4], 2) == 7.0
