"""Offline scientific contracts for descriptive analyses and plotting inputs."""

import json

import numpy as np
import pandas as pd
import pytest

import chronos_analysis_helpers as helpers
import chronos_scan_visualization as viz
import chronos_scenario_sensitivity as scenarios
import chronos_uncertainty_alignment as uncertainty
from chronos_scales import NORMALIZED_SCORE_COL, RAW_SCORE_COL
from research_schema import ANALYSIS_VERSION, GROUP_KEY_COLS, is_base_branch, read_csv


def branch_key(series="001", token=7):
    return {
        "source": "fixture", "dataset_name": "test", "series_id": series,
        "window_id": 0, "window_start": 12, "context_len": 24, "horizon": 6,
        "branch_mode": "single", "branch_step": 0, "token_id": token,
    }


def branch_steps(base, branch, series="001", token=7):
    base = np.asarray(base, dtype=float)
    branch = np.asarray(branch, dtype=float)
    return pd.DataFrame({
        **branch_key(series, token),
        "forecast_step": np.arange(len(base)),
        "relative_step_after_branch": np.arange(len(base)),
        "base_q10": base - .05, "base_q50": base, "base_q90": base + .05,
        "branch_q10": branch - .05, "branch_q50": branch, "branch_q90": branch + .05,
    })


def decisions(base, branch, scale=1.):
    return {
        row["scenario_name"]: row
        for row in scenarios._scenario_records_for_branch(
            branch_steps(base, branch), pd.Series({"context_iqr": scale}), None,
        )
    }


@pytest.mark.parametrize("contents", [
    "series_id,score\n001,1\n002,2,extra\n",
    "series_id,score\n001,1\n002\n",
])
def test_analysis_csv_never_silently_skips_ragged_records(tmp_path, contents):
    path = tmp_path / "ragged.csv"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed CSV"):
        helpers.read_csv_robust(path)
    with pytest.raises(ValueError, match="Malformed CSV"):
        viz._read_csv_if_exists(path)


def test_read_and_plot_preparation_preserve_identifiers(tmp_path):
    path = tmp_path / "identifiers.csv"
    path.write_text(
        f"series_id,branch_id,window_id,token_id,{NORMALIZED_SCORE_COL}\n"
        "001,branch_A,2,7,1\nNA,branch_B,3,8,2\ncurrency_1,branch_C,4,9,3\n",
        encoding="utf-8",
    )
    frame, warnings = helpers.read_csv_robust(path)
    prepared = viz._prepare_summary_df(frame)
    assert warnings == []
    assert prepared.series_id.tolist() == ["001", "NA", "currency_1"]
    assert prepared.branch_id.tolist() == ["branch_A", "branch_B", "branch_C"]
    assert prepared.window_id.tolist() == [2, 3, 4]
    assert prepared.token_id.tolist() == [7, 8, 9]


def test_one_default_score_and_explicit_invalid_score_raise():
    frame = pd.DataFrame({NORMALIZED_SCORE_COL: [1., np.nan], RAW_SCORE_COL: [2., 3.]})
    assert helpers.resolve_score_column(frame) == NORMALIZED_SCORE_COL
    with pytest.raises(ValueError):
        helpers.resolve_score_column(frame, "typo")
    with pytest.raises(ValueError):
        helpers.resolve_score_column(frame[[RAW_SCORE_COL]])
    frame["undefined_score"] = np.nan
    with pytest.raises(ValueError):
        helpers.resolve_score_column(frame, "undefined_score")
    with pytest.raises(ValueError):
        viz._score_sorted(frame, "typo")


def test_plot_score_choice_is_local_and_does_not_switch_for_nan_subset():
    frame = pd.DataFrame({NORMALIZED_SCORE_COL: [1., np.nan], RAW_SCORE_COL: [2., 3.]})
    frame.attrs["analysis_score_column"] = RAW_SCORE_COL
    subset = frame.iloc[[1]].copy()
    assert viz._preferred_score_col(subset) == RAW_SCORE_COL
    other = frame.copy()
    other.attrs["analysis_score_column"] = NORMALIZED_SCORE_COL
    assert viz._preferred_score_col(other.iloc[[1]].copy()) == NORMALIZED_SCORE_COL
    assert viz._preferred_score_col(frame) == RAW_SCORE_COL
    assert not hasattr(viz, "SCORE_COL_OVERRIDE")


def test_plot_matching_scale_never_uses_another_available_error():
    frame = pd.DataFrame({
        NORMALIZED_SCORE_COL: [1.], "context_std": [2.],
        "base_mae_over_context_std": [.2], "base_mae": [.4],
    })
    assert viz._preferred_scale_col(frame) == "context_iqr"
    assert viz._preferred_error_col(frame) is None
    frame["base_mae_over_context_iqr"] = np.nan
    assert viz._preferred_error_col(frame) == "base_mae_over_context_iqr"
    frame.attrs["analysis_score_column"] = RAW_SCORE_COL
    frame[RAW_SCORE_COL] = 2.
    assert viz._preferred_scale_col(frame) is None
    assert viz._preferred_error_col(frame) == "base_mae"


def test_all_plot_entrypoints_keep_explicit_score_and_matching_scale(tmp_path, monkeypatch):
    selected = "context_std_scaled_progressive_token_bin_forking_score"
    frame = pd.DataFrame({
        "dataset_name": ["first", "second"], "series_id": ["001", "002"],
        NORMALIZED_SCORE_COL: [100., 200.], selected: [1., np.nan],
        "context_iqr": [3., 4.], "context_std": [2., np.nan],
        "base_mae_over_context_iqr": [.4, .5], "base_mae_over_context_std": [.1, np.nan],
    })
    frame.to_csv(tmp_path / "chronos_scan_summary.csv", index=False)
    seen = []

    def capture(*args, **kwargs):
        for argument in args:
            if isinstance(argument, pd.DataFrame) and selected in argument.columns:
                seen.append(argument.copy())
        return None

    for name in dir(viz):
        if name.startswith("plot_") and name != "plot_chronos_scan_outputs":
            monkeypatch.setattr(viz, name, capture)
    assert viz.plot_chronos_scan_outputs(tmp_path, score_col=selected) == []
    assert len(seen) >= 30
    assert any(item.dataset_name.eq("second").all() for item in seen)
    for item in seen:
        assert viz._preferred_score_col(item) == selected
        assert viz._preferred_scale_col(item) == "context_std"
        assert viz._preferred_error_col(item) == "base_mae_over_context_std"


@pytest.mark.parametrize("ranking", [
    {RAW_SCORE_COL: [2.]}, {NORMALIZED_SCORE_COL: [np.nan]},
])
def test_plot_run_rejects_ranking_with_a_mismatched_or_undefined_score(tmp_path, ranking):
    pd.DataFrame({NORMALIZED_SCORE_COL: [1.]}).to_csv(tmp_path / "chronos_scan_summary.csv", index=False)
    pd.DataFrame(ranking).to_csv(tmp_path / "chronos_scan_ranking.csv", index=False)
    with pytest.raises(ValueError):
        viz.plot_chronos_scan_outputs(tmp_path)


def test_plot_component_weights_have_one_shared_definition():
    from chronos_score import SCORE_WEIGHTS

    assert viz.COMPONENT_WEIGHTS is SCORE_WEIGHTS


def test_temporal_and_error_plots_render_the_selected_scale(tmp_path, monkeypatch):
    from matplotlib.figure import Figure

    selected = "context_std_scaled_progressive_token_bin_forking_score"
    frame = pd.DataFrame({
        "dataset_name": ["first", "second"], selected: [1., 2.],
        NORMALIZED_SCORE_COL: [100., 200.],
        "context_std": [2., 4.], "context_iqr": [100., 200.],
        "base_mae_over_context_std": [.1, .2], "base_mae_over_context_iqr": [10., 20.],
        "early_law_shift": [2., 8.], "mid_law_shift": [4., 16.], "late_law_shift": [6., 24.],
    })
    frame.attrs["analysis_score_column"] = selected
    figures = []
    monkeypatch.setattr(Figure, "savefig", lambda figure, *args, **kwargs: figures.append(figure))
    viz.plot_temporal_shift_profile(frame, tmp_path / "temporal.png")
    axis = figures[-1].axes[0]
    assert "context_std" in axis.get_xlabel()
    assert [patch.get_width() for patch in axis.patches] == [2., 1., 4., 2., 6., 3.]
    viz.plot_score_vs_base_error(frame, tmp_path / "error.png")
    axis = figures[-1].axes[0]
    assert axis.get_xlabel() == "base_mae_over_context_std"
    assert axis.get_ylabel() == selected
    expected = {"first": [.1, 1.], "second": [.2, 2.]}
    for collection in axis.collections:
        np.testing.assert_allclose(collection.get_offsets(), [expected[collection.get_label()]])


def test_scenario_threshold_crossing_is_inclusive_but_direction_band_is_strict():
    rows = decisions([0., 0., 0.], [0., .25, .10])
    assert rows["upside_threshold_crossing"]["branch_status"] == "True"
    assert rows["upside_threshold_crossing"]["scenario_changed"]
    assert rows["final_direction"]["branch_status"] == "flat"
    rows = decisions([0., 0., 0.], [0., -.25, -.10])
    assert rows["downside_threshold_crossing"]["branch_status"] == "True"
    assert rows["final_direction"]["branch_status"] == "flat"
    assert scenarios._direction_label(np.nextafter(.10, 1.), .10) == "up"
    assert scenarios._direction_label(np.nextafter(-.10, -1.), .10) == "down"


@pytest.mark.parametrize("scale", [0., -1., np.nan, np.inf, -np.inf, "bad"])
def test_scenario_invalid_scale_has_no_row_fallback(scale):
    summary = pd.Series({"context_iqr": scale, "window_scale": 2., "context_std": 3.})
    assert np.isnan(scenarios._decision_scale(summary))
    assert scenarios._scenario_records_for_branch(
        branch_steps([0., 1., 2.], [0., 2., 3.]), summary, None,
    ) == []
    assert scenarios._decision_scale(summary, "window_scale") == 2.


def test_scenario_timing_ties_are_undefined_even_within_one_bin():
    rows = decisions([0., 1., 2., 3., 4., 5.], [9., 9., 4., 3., 2., 1.])
    timing = rows["peak_timing_bin"]
    assert timing["branch_status"] == "undefined"
    assert not timing["scenario_defined"]
    assert timing["undefined_reason"] == "nonunique_extremum"
    assert np.isnan(timing["scenario_changed"])
    assert np.isnan(timing["scenario_decision_shift_score"])
    assert rows["trough_timing_bin"]["scenario_defined"]
    assert rows["trough_timing_bin"]["scenario_changed"]


def test_undefined_decisions_do_not_enter_change_rate_denominator():
    tied = decisions([0., 1., 2.], [4., 4., 0.])["peak_timing_bin"]
    changed = decisions([0., 1., 2.], [3., 1., 0.])["peak_timing_bin"]
    result = scenarios._summarize_scenarios(pd.DataFrame([tied, changed]), ["scenario_name"]).iloc[0]
    assert result["rows"] == 2
    assert result["defined"] == 1
    assert result["undefined"] == 1
    assert result["changed"] == 1
    assert result["changed_rate"] == 1.
    only_undefined = scenarios._summarize_scenarios(pd.DataFrame([tied]), ["scenario_name"]).iloc[0]
    assert np.isnan(only_undefined["changed_rate"])


def test_scenario_run_records_scale_exclusions_version_and_undefined_counts(tmp_path, monkeypatch):
    steps = pd.concat([
        branch_steps([0., 1., 2.], [3., 3., 0.], "001"),
        branch_steps([0., 1., 2.], [0., 2., 3.], "002"),
    ], ignore_index=True)
    summary = pd.DataFrame([
        {**branch_key("001"), NORMALIZED_SCORE_COL: 1., "context_iqr": 1., "context_std": 2., "context_std_scaled_progressive_token_bin_forking_score": .5},
        {**branch_key("002"), NORMALIZED_SCORE_COL: 2., "context_iqr": 0., "context_std": 2., "context_std_scaled_progressive_token_bin_forking_score": 1.},
    ])
    steps.to_csv(tmp_path / "chronos_scan_steps.csv", index=False)
    summary.to_csv(tmp_path / "chronos_scan_summary.csv", index=False)
    for name in ("_plot_change_rates", "_plot_dataset_heatmap", "_plot_fpa_vs_decision", "_plot_example_branch"):
        monkeypatch.setattr(scenarios, name, lambda *args: None)
    outputs = scenarios.analyze_run_scenario_sensitivity(tmp_path)
    payload = json.loads((outputs.output_dir / "scenario_sensitivity_summary.json").read_text())
    assert payload["analysis_version"] == ANALYSIS_VERSION
    assert payload["decision_scale_column"] == "context_iqr"
    assert payload["branches_excluded"] == 1
    assert payload["exclusion_counts"] == {"invalid_decision_scale": 1}
    assert payload["undefined_scenario_decisions"] == 1
    excluded = read_csv(outputs.output_dir / "scenario_excluded_branches.csv")
    assert excluded.series_id.tolist() == ["002"]
    with pytest.raises(ValueError, match="same normalization"):
        scenarios.analyze_run_scenario_sensitivity(tmp_path, score_col=NORMALIZED_SCORE_COL, scale_col="context_std")
    outputs = scenarios.analyze_run_scenario_sensitivity(tmp_path, scale_col="context_std")
    payload = json.loads((outputs.output_dir / "scenario_sensitivity_summary.json").read_text())
    assert payload["branches_excluded"] == 0
    records = read_csv(outputs.output_dir / "scenario_branch_decisions.csv")
    assert records.decision_scale.eq(2.).all()
    with pytest.raises(ValueError, match="Decision scale"):
        scenarios.analyze_run_scenario_sensitivity(tmp_path, scale_col="typo")
    with pytest.raises(ValueError):
        scenarios.analyze_run_scenario_sensitivity(tmp_path, score_col="typo")


def test_scenarios_do_not_promote_missing_forecasts_to_false():
    steps = branch_steps([0., 1., 2.], [0., 1., 3.])
    steps.loc[1, "branch_q10"] = np.nan
    assert scenarios._scenario_records_for_branch(steps, pd.Series({"context_iqr": 1.}), None) == []
    steps["relative_step_after_branch"] = -1
    assert scenarios._scenario_records_for_branch(steps, pd.Series({"context_iqr": 1.}), None) == []


def test_rank_constants_ties_and_nan_conventions_are_preserved():
    result = uncertainty._rank01(pd.Series([4., 4., np.nan]))
    assert result.iloc[:2].tolist() == [.75, .75]
    assert np.isnan(result.iloc[2])
    assert uncertainty._rank01(pd.Series([4., np.nan])).isna().all()
    assert uncertainty._rank01(pd.Series([1., 1., 2.]), higher_is_more=False).tolist() == [5 / 6, 5 / 6, 1 / 3]


def test_reusable_uncertainty_indices_are_frozen_before_base_exclusion():
    summary = pd.DataFrame({
        NORMALIZED_SCORE_COL: [0., 2., 4.],
        "is_base_token": [True, False, False],
        "normalized_token_entropy": [.1, .2, .3],
        "token_probability": [.8, .15, .05],
    }, index=[10, 20, 30])
    original = summary.copy(deep=True)
    metrics = uncertainty.prepare_uncertainty_metrics(summary)
    frame = uncertainty._prepare_analysis_frame(summary, NORMALIZED_SCORE_COL)
    pd.testing.assert_frame_equal(summary, original)
    pd.testing.assert_series_equal(metrics.model_distribution_uncertainty_index, frame.model_distribution_uncertainty_index)
    alternatives = frame.loc[~is_base_branch(frame)]
    assert alternatives.index.tolist() == [20, 30]
    assert alternatives.model_distribution_uncertainty_index.tolist() == [2 / 3, 1.]
    assert alternatives.forced_token_implausibility_index.tolist() == [2 / 3, 1.]
    assert alternatives.selected_fpa_score.tolist() == [2., 4.]


def test_uncertainty_branch_point_aggregation_is_unweighted_and_keeps_group_identity():
    rows = []
    for series, scores, entropy in [("001", [1., 5.], .2), ("002", [10.], .8)]:
        for i, score in enumerate(scores):
            rows.append({**branch_key(series, i), NORMALIZED_SCORE_COL: score, "normalized_token_entropy": entropy})
    frame = uncertainty._prepare_analysis_frame(pd.DataFrame(rows), NORMALIZED_SCORE_COL)
    points = uncertainty._aggregate_branch_points(frame, [NORMALIZED_SCORE_COL, "selected_fpa_score"])
    assert points.series_id.tolist() == ["001", "002"]
    assert points.branches_aggregated.tolist() == [2, 1]
    assert points.selected_fpa_score.tolist() == [3., 10.]
    assert points.model_distribution_uncertainty_index.tolist() == [.5, 1.]
    assert set(GROUP_KEY_COLS).issubset(points.columns)
    with pytest.raises(ValueError, match="Missing branch-point identifiers"):
        uncertainty._aggregate_branch_points(frame.drop(columns="series_id"), [NORMALIZED_SCORE_COL])


def test_uncertainty_correlations_report_pairwise_counts_and_constant_undefined():
    frame = pd.DataFrame({"score": [1., 2., 3., np.nan], "normalized_token_entropy": [.5] * 4})
    record = uncertainty._corr_records(frame, "global", "all", ["score"])[0]
    assert record["n"] == 3
    assert record["rows_excluded_pairwise"] == 1
    assert record["undefined_reason"] == "constant_metric"
    assert np.isnan(record["pearson_corr"])
    assert np.isnan(record["spearman_corr"])
    frame.normalized_token_entropy = [3., 2., 1., 4.]
    record = uncertainty._corr_records(frame, "global", "all", ["score"])[0]
    assert record["correlation_defined"]
    assert record["spearman_corr"] == pytest.approx(-1.)


@pytest.mark.parametrize("column,value", [
    ("source", "other"), ("dataset_name", "other"), ("series_id", "002"),
    ("window_id", 1), ("window_start", 13), ("context_len", 25),
    ("horizon", 7), ("branch_mode", "bundle"), ("branch_step", 1),
])
def test_branch_point_aggregation_respects_every_shared_group_key(column, value):
    first = {**branch_key(), NORMALIZED_SCORE_COL: 1., "normalized_token_entropy": .2}
    second = {**first, column: value, NORMALIZED_SCORE_COL: 5.}
    frame = uncertainty._prepare_analysis_frame(pd.DataFrame([first, second]), NORMALIZED_SCORE_COL)
    points = uncertainty._aggregate_branch_points(frame, ["selected_fpa_score"])
    assert len(points) == 2
    assert points.branches_aggregated.tolist() == [1, 1]
    assert points.selected_fpa_score.tolist() == [1., 5.]


def test_uncertainty_run_preserves_branch_outputs_and_adds_descriptive_points(tmp_path, monkeypatch):
    rows = []
    for series, entropy in [("001", .1), ("002", .3), ("003", .7)]:
        for token, score in enumerate([0., 2., 4.]):
            rows.append({
                **branch_key(series, token), NORMALIZED_SCORE_COL: score,
                "is_base_token": token == 0, "normalized_token_entropy": entropy,
                "token_probability": [.8, .15, .05][token],
            })
    summary = pd.DataFrame(rows)
    summary.to_csv(tmp_path / "chronos_scan_summary.csv", index=False)
    for name in ("_scatter_plot", "_heatmap", "_dataset_barplot"):
        monkeypatch.setattr(uncertainty, name, lambda *args: None)
    outputs = uncertainty.analyze_run_uncertainty_alignment(tmp_path)
    payload = json.loads((outputs.output_dir / "model_uncertainty_alignment_summary.json").read_text())
    assert payload["analysis_version"] == ANALYSIS_VERSION
    assert payload["rows_base_excluded"] == 3
    assert payload["rows_alternative"] == 6
    assert payload["branch_points"] == 3
    branch_corr = read_csv(outputs.output_dir / "model_uncertainty_fpa_correlations.csv")
    point_corr = read_csv(outputs.output_dir / "model_uncertainty_branch_point_correlations.csv")
    assert branch_corr.observation_level.eq("branch").all()
    assert point_corr.observation_level.eq("branch_point").all()
    branch = branch_corr.query("group_name == 'global' and fpa_metric == 'selected_fpa_score'")
    point = point_corr.query("group_name == 'global' and fpa_metric == 'selected_fpa_score'")
    assert branch.n.eq(6).all()
    assert point.n.eq(3).all()
    points = read_csv(outputs.output_dir / "model_uncertainty_branch_points.csv")
    assert points.series_id.tolist() == ["001", "002", "003"]
    assert points.selected_fpa_score.tolist() == [3., 3., 3.]
    assert points.model_distribution_uncertainty_index.tolist() == pytest.approx([2 / 9, 5 / 9, 8 / 9])
    assert (outputs.output_dir / "model_uncertainty_fpa_quadrant_summary.csv").exists()
