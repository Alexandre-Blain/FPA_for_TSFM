"""Hand-computed normalizations, not comparisons between implementation aliases."""

import math

import numpy as np
import pandas as pd
import pytest

from chronos_scales import (
    _attach_normalized_branch_scores,
    _attach_temporal_forking_scores,
    _temporal_shift_metrics,
    compute_base_forecast_quality,
    resolve_score_column,
)


RAW_TOKEN = "token_bin_forking_score"
RAW_PROGRESSIVE = "progressive_token_bin_forking_score"
IQR_TOKEN = "context_iqr_scaled_token_bin_forking_score"
IQR_PROGRESSIVE = "context_iqr_scaled_progressive_token_bin_forking_score"


def score_frame():
    return pd.DataFrame({
        "mean_law_shift": [4.0], "max_law_shift": [8.0],
        "positive_law_amplification": [2.0], "shape_break": [0.5],
        "max_widening_10_90": [6.0], "last_over_max_law": [0.25],
        "monotonic_growth_fraction": [0.5], "context_iqr": [2.0],
        "window_scale": [10.0], RAW_TOKEN: [4.55], RAW_PROGRESSIVE: [2.1328125],
    }, index=[17])


def test_forecast_quality_uses_population_scales_and_linear_iqr():
    result = compute_base_forecast_quality(
        base_values=[1, 6, 3, 12], y_true=[2, 4, 6, 8], context_values=[-4, 0, 4, 8],
    )
    # Errors -1, 2, -3, 4; context quartiles -1, 5; future quartiles 3.5, 6.5.
    expected = {
        "base_mae": 2.5, "base_rmse": math.sqrt(7.5),
        "context_mean_abs": 4, "context_std": math.sqrt(20),
        "context_rms": math.sqrt(24), "context_range": 12, "context_iqr": 6,
        "gt_mean_abs": 5, "gt_std": math.sqrt(5), "gt_rms": math.sqrt(30),
        "gt_range": 6, "gt_iqr": 3, "window_scale": 12,
        "base_mae_over_gt_mean_abs": 0.5, "base_mae_over_window_scale": 5 / 24,
        "base_mae_over_context_iqr": 5 / 12,
        "base_mae_over_context_std": 2.5 / math.sqrt(20),
        "base_mae_over_context_range": 5 / 24,
        "base_mae_over_gt_iqr": 5 / 6,
        "base_mae_over_gt_std": 2.5 / math.sqrt(5),
        "base_mae_over_gt_range": 5 / 12,
    }
    for name, value in expected.items():
        assert result[name] == pytest.approx(value), name


def test_forecast_quality_zero_scales_produce_nan_not_infinity():
    result = compute_base_forecast_quality([0, 0], [0, 0], [0, 0, 0])
    assert result["base_mae"] == 0
    assert result["base_rmse"] == 0
    assert np.isnan(result["window_scale"])
    ratios = [value for name, value in result.items() if name.startswith("base_mae_over_")]
    assert ratios and all(np.isnan(value) for value in ratios)


def test_empty_prediction_keeps_scale_diagnostics_but_has_no_error():
    result = compute_base_forecast_quality([], [2, 4], context_values=None)
    assert result["gt_mean_abs"] == 3
    assert result["gt_std"] == 1
    assert result["gt_iqr"] == 1
    assert result["window_scale"] == pytest.approx(math.sqrt(10))
    assert np.isnan(result["context_iqr"])
    assert np.isnan(result["base_mae"])
    assert np.isnan(result["base_rmse"])


def test_context_diagnostics_ignore_nonfinite_history_without_mutation():
    context = np.array([-4, 0, 4, 8, np.nan, np.inf])
    original = context.copy()
    result = compute_base_forecast_quality([2, 4], [2, 4], context)
    assert result["context_iqr"] == 6
    assert result["context_std"] == pytest.approx(math.sqrt(20))
    np.testing.assert_array_equal(context, original)


def test_normalized_score_scales_only_dimensional_components():
    frame = score_frame()
    original = frame.copy(deep=True)
    out = _attach_normalized_branch_scores(frame)
    # Dimensional weighted sum 4.2, dimensionless contribution .35.
    # IQR score 4.2/2 + .35; progressive factor .625*.75 = .46875.
    assert out.loc[17, IQR_TOKEN] == pytest.approx(2.45)
    assert out.loc[17, IQR_PROGRESSIVE] == pytest.approx(1.1484375)
    assert out.loc[17, "window_scaled_token_bin_forking_score"] == pytest.approx(0.77)
    assert out.loc[17, "window_scaled_progressive_token_bin_forking_score"] == pytest.approx(0.3609375)
    assert out.loc[17, f"{RAW_TOKEN}_over_context_iqr"] == pytest.approx(2.275)
    assert out.loc[17, "mean_law_shift_over_context_iqr"] == 2
    assert out.loc[17, IQR_TOKEN] != out.loc[17, f"{RAW_TOKEN}_over_context_iqr"]
    pd.testing.assert_frame_equal(frame, original)


def test_normalized_composite_is_invariant_to_dimensional_unit_changes():
    frame = score_frame()
    columns = ["mean_law_shift", "max_law_shift", "max_widening_10_90", "context_iqr", "window_scale"]
    frame[columns] *= 1000
    out = _attach_normalized_branch_scores(frame)
    assert out.loc[17, IQR_TOKEN] == pytest.approx(2.45)
    assert out.loc[17, IQR_PROGRESSIVE] == pytest.approx(1.1484375)


@pytest.mark.parametrize("scale", [0, -2, 1e-13, np.nan, np.inf, -np.inf, "bad"])
def test_unusable_normalization_scale_is_not_silently_replaced(scale):
    frame = score_frame()
    frame["context_iqr"] = scale
    out = _attach_normalized_branch_scores(frame)
    assert np.isnan(out.loc[17, IQR_TOKEN])
    assert np.isnan(out.loc[17, IQR_PROGRESSIVE])
    assert out.loc[17, "window_scaled_token_bin_forking_score"] == pytest.approx(0.77)


@pytest.mark.parametrize("factor,expected", [(-2, 0.6125), (3, 2.45)])
def test_progressive_factors_are_clipped_to_unit_interval(factor, expected):
    frame = score_frame()
    frame["last_over_max_law"] = factor
    frame["monotonic_growth_fraction"] = factor
    out = _attach_normalized_branch_scores(frame)
    assert out.loc[17, IQR_PROGRESSIVE] == pytest.approx(expected)


def temporal_frame():
    return pd.DataFrame({
        "early_law_shift": [2.0], "mid_law_shift": [4.0], "late_law_shift": [8.0],
        "peak_law_shift": [10.0], "persistence_ratio": [0.25],
        "late_over_early_law": [4.0], "monotonic_growth_fraction": [0.5],
        "context_iqr": [2.0],
    })


def test_instant_persistent_and_progressive_scores_have_distinct_formulas():
    frame = temporal_frame()
    original = frame.copy(deep=True)
    row = _attach_temporal_forking_scores(frame).iloc[0]
    assert row.early_law_shift_over_context_iqr == 1
    assert row.mid_law_shift_over_context_iqr == 2
    assert row.late_law_shift_over_context_iqr == 4
    assert row.peak_law_shift_over_context_iqr == 5
    assert row.context_iqr_scaled_instant_forking_score == 1
    assert row.context_iqr_scaled_persistent_forking_score == 2.5
    assert row.context_iqr_scaled_progressive_forking_score == 9
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("law,peak,timing,ambiguous", [
    ([], np.nan, [np.nan, np.nan, np.nan], True),
    ([1, 4, 4, 2], 4, [np.nan, np.nan, np.nan], True),
    ([4, 1, 4], 4, [np.nan, np.nan, np.nan], True),
    ([1, -4, 4, 2], 4, [np.nan, np.nan, np.nan], True),
    ([3, 3, 3], 3, [np.nan, np.nan, np.nan], True),
    ([0, 0, 0], 0, [np.nan, np.nan, np.nan], True),
    ([1, 4, 3], 4, [8, 1, 0.5], False),
    ([3], 3, [7, 0, 0], False),
    ([0], 0, [7, 0, 0], False),
    # Only exact ties are ambiguous, not distinct values within np.isclose tolerance.
    ([4, 1, np.nextafter(4.0, np.inf)], np.nextafter(4.0, np.inf), [9, 2, 1], False),
])
def test_temporal_peak_timing_requires_a_unique_absolute_maximum(law, peak, timing, ambiguous):
    result = _temporal_shift_metrics(law, [0] * len(law), branch_step=7)
    assert result["peak_timing_ambiguous"] is ambiguous
    np.testing.assert_allclose(result["peak_law_shift"], peak, equal_nan=True)
    np.testing.assert_allclose([
        result["peak_forecast_step"], result["peak_relative_step_after_branch"],
        result["peak_delay_fraction"],
    ], timing, equal_nan=True)


def test_temporal_progressive_gain_caps_at_ten_and_decline_is_zero():
    frame = temporal_frame()
    frame["late_over_early_law"] = 100
    assert _attach_temporal_forking_scores(frame).iloc[0].context_iqr_scaled_progressive_forking_score == 22.5
    frame["early_law_shift"] = 8
    frame["late_law_shift"] = 2
    frame["late_over_early_law"] = 0.25
    assert _attach_temporal_forking_scores(frame).iloc[0].context_iqr_scaled_progressive_forking_score == 0


def test_incomplete_temporal_frame_is_returned_without_invented_metrics():
    frame = pd.DataFrame({"early_law_shift": [1.0], "context_iqr": [2.0]})
    pd.testing.assert_frame_equal(_attach_temporal_forking_scores(frame), frame)


def test_score_resolution_rejects_undefined_default_and_respects_explicit_override():
    frame = pd.DataFrame({
        IQR_PROGRESSIVE: [np.nan],
        "context_std_scaled_progressive_token_bin_forking_score": [0.3],
        RAW_PROGRESSIVE: [100.0],
    })
    with pytest.raises(ValueError, match="no finite values"):
        resolve_score_column(frame)
    assert resolve_score_column(
        frame, requested="context_std_scaled_progressive_token_bin_forking_score",
    ) == "context_std_scaled_progressive_token_bin_forking_score"
    assert resolve_score_column(frame, requested=RAW_PROGRESSIVE) == RAW_PROGRESSIVE
    assert resolve_score_column(pd.DataFrame()) == IQR_PROGRESSIVE


def test_score_resolution_never_silently_falls_back_to_raw_score():
    with pytest.raises(ValueError, match="missing"):
        resolve_score_column(pd.DataFrame({RAW_PROGRESSIVE: [100.0]}))
    frame = pd.DataFrame({IQR_PROGRESSIVE: [np.nan, 0.3], RAW_PROGRESSIVE: [100.0, 200.0]})
    assert resolve_score_column(frame) == IQR_PROGRESSIVE
