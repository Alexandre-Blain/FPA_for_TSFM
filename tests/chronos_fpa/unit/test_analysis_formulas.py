"""Numerical oracles for public analysis APIs, without model/runtime imports."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from chronos_analysis import (
    analyze_chronos_named_branches,
    analyze_chronos_token_branches,
    summarize_chronos_branches,
    summarize_chronos_named_branches,
)


@pytest.fixture(params=["token", "named"])
def analysis_api(request):
    if request.param == "token":
        return analyze_chronos_token_branches, summarize_chronos_branches, "token_id", 7
    return analyze_chronos_named_branches, summarize_chronos_named_branches, "branch_id", "alt"


def topology():
    return dict(
        top1_probability=0.8, top2_probability=0.1, top1_top2_margin=0.7,
        token_entropy=0.6, normalized_token_entropy=0.2, top_k_probability_mass=0.9,
    )


def decode_fixture(kind):
    base = np.array([
        [6, 7, 8, 9, 10, 11, 12, 13, 14],
        [16, 17, 18, 19, 20, 21, 22, 23, 24],
        [26, 27, 28, 29, 30, 31, 32, 33, 34],
    ], dtype=float)
    branch = np.array([
        [4, 5, 6, 7, 8, 9, 10, 11, 12],
        [12, 17, 18, 19, 20, 21, 22, 23, 28],
        [29, 30, 31, 32, 33, 34, 35, 36, 37],
    ], dtype=float)
    branches = {}
    for is_base, quantiles in ((True, base), (False, branch)):
        if kind == "token_id":
            identifier = 5 if is_base else 7
            metadata = dict(alternative=SimpleNamespace(
                rank=1 if is_base else 2, probability=0.8 if is_base else 0.1,
                token_surprisal=0.25 if is_base else 2.3, value=float(identifier),
                is_base_token=is_base, **topology(),
            ))
        else:
            identifier = "base" if is_base else "alt"
            metadata = dict(branch=SimpleNamespace(
                forced_tokens=[5, 6] if is_base else [7, 8],
                initial_token_id=5 if is_base else 7,
                initial_token_rank=1 if is_base else 2,
                initial_token_probability=0.8 if is_base else 0.1,
                initial_token_surprisal=0.25 if is_base else 2.3,
                continuation_rank=None if is_base else 3,
                is_base_branch=is_base, branch_kind="bundle", **topology(),
            ))
        branches[identifier] = dict(quantiles=quantiles, **metadata)
    return dict(
        branch_step=1, base_token_at_branch=5, base_branch_id="base", branches=branches,
        # Neither deterministic path is the reference distribution.
        base_values=np.array([999, 999, 999]),
    )


def summary_input(kind, law, width=None, branch_step=0, base=None, branch=None):
    n = len(law)
    frame = pd.DataFrame({
        "forecast_step": range(n), "branch_step": branch_step,
        "relative_step_after_branch": np.arange(n) - branch_step,
        "law_shift_h": law,
        "width_shift_10_90_h": width if width is not None else [0] * n,
        "base_q50": base if base is not None else range(n),
        "branch_q50": branch if branch is not None else range(n),
    })
    if kind == "token_id":
        metadata = dict(
            token_id=7, token_rank=2, token_probability=0.1, token_surprisal=2.3,
            token_value_unit_scale=7.0, is_base_token=False,
        )
    else:
        metadata = dict(
            branch_id="alt", branch_kind="bundle", forced_tokens="7 8",
            initial_token_id=7, initial_token_rank=2, initial_token_probability=0.1,
            initial_token_surprisal=2.3, continuation_rank=3, is_base_branch=False,
        )
    for key, value in dict(**metadata, **topology()).items():
        frame[key] = value
    return frame


def test_per_step_law_is_mean_absolute_quantile_distance(analysis_api):
    analyze, _, key, alternative = analysis_api
    source = decode_fixture(key)
    original = source["branches"][alternative]["quantiles"].copy()
    steps = analyze(source)
    alt = steps.loc[steps[key] == alternative]

    # Nine quantiles: the middle row moves only the two tails by four each.
    np.testing.assert_allclose(alt.law_shift_h, [2, 8 / 9, 3])
    np.testing.assert_allclose(alt.median_shift_h, [2, 0, 3])
    np.testing.assert_allclose(alt.width_shift_10_90_h, [0, 8, 0])
    np.testing.assert_allclose(alt.base_q50, [10, 20, 30])
    np.testing.assert_allclose(alt.branch_q50, [8, 20, 33])
    assert alt.relative_step_after_branch.tolist() == [-1, 0, 1]
    assert alt.top1_top2_margin.tolist() == [0.7] * 3
    assert alt.normalized_token_entropy.tolist() == [0.2] * 3
    base = steps.loc[steps[key] != alternative]
    np.testing.assert_allclose(base[["law_shift_h", "median_shift_h", "width_shift_10_90_h"]], 0)
    np.testing.assert_array_equal(source["branches"][alternative]["quantiles"], original)


def test_summary_post_branch_temporal_metrics_and_score(analysis_api):
    _, summarize, key, _ = analysis_api
    frame = summary_input(
        key, law=[100, 200, 1, 2, 4, 8, 4, 2],
        width=[100, 200, -2, -1, 0, 2, -3, 6], branch_step=2,
    )
    original = frame.copy(deep=True)
    # Unsorted rows must not change post-branch chronology or peak coordinates.
    row = summarize(frame.iloc[::-1]).iloc[0]
    expected = dict(
        n_steps=6, mean_law_shift=3.5, max_law_shift=8, law_first=1, law_last=2,
        positive_law_amplification=2 / 7, last_over_max_law=0.25,
        monotonic_growth_fraction=0.6, max_widening_10_90=6, shape_break=0,
        early_law_shift=1.5, mid_law_shift=6, late_law_shift=3,
        area_under_law_shift=21, peak_law_shift=8, peak_forecast_step=5,
        peak_relative_step_after_branch=3, peak_delay_fraction=0.6,
        late_over_early_law=2, persistence_ratio=0.25, convergence_ratio=2,
        early_widening_10_90=0, mid_widening_10_90=1, late_widening_10_90=3,
        # 0.4*3.5 + 0.25*8 + 0.15*(2/7) + 0.1*0 + 0.1*6.
        token_bin_forking_score=283 / 70,
        # Persistence multiplier .625, monotonic multiplier .8.
        progressive_token_bin_forking_score=283 / 140,
    )
    for name, value in expected.items():
        assert row[name] == pytest.approx(value), name
    assert not bool(row.peak_timing_ambiguous)
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("law,mean,area,peak,amplification,raw_score,progressive_score", [
    ([1, 4, 4, 2], 11 / 4, 11, 4, 4 / 11, 237 / 110, 237 / 176),
    ([3, 3, 3], 3, 9, 3, 0, 1.95, 1.95),
])
def test_ambiguous_peak_timing_preserves_scalar_summary_scores(
    analysis_api, law, mean, area, peak, amplification, raw_score, progressive_score,
):
    _, summarize, key, _ = analysis_api
    # Large pre-branch values must not resolve an otherwise tied post-branch peak.
    frame = summary_input(key, [99, 99] + law, branch_step=2)
    row = summarize(frame.iloc[::-1]).iloc[0]
    assert bool(row.peak_timing_ambiguous)
    for column in ("peak_forecast_step", "peak_relative_step_after_branch", "peak_delay_fraction"):
        assert np.isnan(row[column]), column
    assert row.mean_law_shift == pytest.approx(mean)
    assert row.area_under_law_shift == pytest.approx(area)
    assert row.peak_law_shift == peak
    assert row.positive_law_amplification == pytest.approx(amplification)
    assert row.token_bin_forking_score == pytest.approx(raw_score)
    assert row.progressive_token_bin_forking_score == pytest.approx(progressive_score)


def test_declining_shift_has_no_positive_amplification(analysis_api):
    _, summarize, key, _ = analysis_api
    row = summarize(summary_input(
        key, law=[4, 2, 1], width=[-1, -2, -3], base=[0, 1, 2], branch=[2, 1, 0],
    )).iloc[0]
    assert row.positive_law_amplification == 0
    assert row.monotonic_growth_fraction == 0
    assert row.max_widening_10_90 == 0
    assert row.shape_break == pytest.approx(2)
    assert row.token_bin_forking_score == pytest.approx(32 / 15)
    assert row.progressive_token_bin_forking_score == pytest.approx(2 / 3)


@pytest.mark.parametrize("branch,expected_shape", [([2, 2, 2], 0), ([3, 3, 3], 1)])
def test_constant_median_shape_convention(analysis_api, branch, expected_shape):
    _, summarize, key, _ = analysis_api
    row = summarize(summary_input(key, [1, 1, 1], base=[2, 2, 2], branch=branch)).iloc[0]
    assert row.shape_break == expected_shape


def test_zero_shift_ratios_are_explicit(analysis_api):
    _, summarize, key, _ = analysis_api
    row = summarize(summary_input(key, [0, 0, 0])).iloc[0]
    assert row.token_bin_forking_score == pytest.approx(0, abs=1e-14)
    assert row.progressive_token_bin_forking_score == pytest.approx(0, abs=1e-14)
    assert row.last_over_max_law == 0
    assert row.monotonic_growth_fraction == 1
    for column in ("late_over_early_law", "persistence_ratio", "convergence_ratio"):
        assert np.isnan(row[column]), column
    assert bool(row.peak_timing_ambiguous)
    for column in ("peak_forecast_step", "peak_relative_step_after_branch", "peak_delay_fraction"):
        assert np.isnan(row[column]), column


def test_single_step_temporal_chunks_and_progressive_factor(analysis_api):
    _, summarize, key, _ = analysis_api
    row = summarize(summary_input(key, [3], base=[0], branch=[3])).iloc[0]
    assert row.early_law_shift == 3
    assert np.isnan(row.mid_law_shift)
    assert np.isnan(row.late_law_shift)
    assert not bool(row.peak_timing_ambiguous)
    assert row.peak_forecast_step == 0
    assert row.peak_relative_step_after_branch == 0
    assert row.peak_delay_fraction == 0
    assert row.monotonic_growth_fraction == 1
    assert row.token_bin_forking_score == pytest.approx(2.05)
    assert row.progressive_token_bin_forking_score == pytest.approx(2.05)


@pytest.mark.parametrize("law", [[0, 0, 0], [1, 3, 3]])
def test_tied_law_peak_has_no_arbitrary_timing(analysis_api, law):
    _, summarize, key, _ = analysis_api
    row = summarize(summary_input(key, law)).iloc[0]
    assert row.peak_timing_ambiguous
    for column in ("peak_delay_fraction", "peak_forecast_step", "peak_relative_step_after_branch"):
        assert np.isnan(row[column])


def test_missing_forced_base_is_not_replaced_by_greedy_path(analysis_api):
    analyze, _, key, _ = analysis_api
    source = decode_fixture(key)
    del source["branches"][5 if key == "token_id" else "base"]
    with pytest.raises(ValueError, match="[Bb]ase"):
        analyze(source)
