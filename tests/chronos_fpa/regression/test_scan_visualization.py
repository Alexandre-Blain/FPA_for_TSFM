"""Identifiers survive preparation, and each plotted group owns its coordinates."""

import numpy as np
import pandas as pd
import pytest

import chronos_scan_visualization as visualization


RAW_SCORE = "progressive_token_bin_forking_score"
NORMALIZED_SCORE = "context_iqr_scaled_progressive_token_bin_forking_score"


@pytest.fixture
def summary():
    # Interleaving rows and using non-default indices catches global/group index mixups.
    return pd.DataFrame({
        "source": ["local"] * 6,
        "dataset_name": ["exchange", "energy", "exchange", "energy", "exchange", "energy"],
        "series_id": ["currency_1", "meter_2", "currency_1", "meter_2", "currency_2", "meter_3"],
        "branch_id": ["alt_a", "alt_b", "alt_c", "alt_d", "alt_e", "alt_f"],
        "base_branch_id": ["base"] * 6,
        "branch_mode": ["bundle"] * 6,
        "forced_tokens": ["7 8"] * 6,
        "window_id": [0, 0, 0, 0, 1, 1],
        "window_start": [0, 0, 0, 0, 4, 4],
        "branch_step": [0, 0, 1, 1, 0, 0],
        "is_base_branch": [False] * 6,
        "context_iqr": [10.0] * 6,
        RAW_SCORE: [20.0, 70.0, 50.0, 30.0, 90.0, 40.0],
        NORMALIZED_SCORE: [2.0, 7.0, 5.0, 3.0, 9.0, 4.0],
        "base_mae_over_context_iqr": [0.1, 0.2, 0.1, 0.2, 0.4, 0.3],
        "normalized_token_entropy": [0.11, 0.22, 0.33, 0.44, 0.55, 0.66],
    }, index=[41, 12, 88, 5, 63, 19])


@pytest.fixture
def plotted_figures(monkeypatch):
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure

    figures = []
    savefig = Figure.savefig

    def capture(figure, *args, **kwargs):
        figures.append(figure)
        return savefig(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture)
    yield figures
    plt.close("all")


def assert_scatter_groups(axis, expected):
    collections = {collection.get_label(): collection for collection in axis.collections}
    assert set(collections) == set(expected)
    for label, coordinates in expected.items():
        actual = np.asarray(collections[label].get_offsets(), dtype=float)
        actual = actual[np.lexsort((actual[:, 1], actual[:, 0]))]
        coordinates = np.asarray(coordinates, dtype=float)
        coordinates = coordinates[np.lexsort((coordinates[:, 1], coordinates[:, 0]))]
        np.testing.assert_allclose(actual, coordinates, err_msg=label)


@pytest.mark.parametrize("dtype", [object, "string"])
def test_prepare_summary_preserves_text_identifiers_and_input(summary, dtype):
    text_columns = [
        "source", "dataset_name", "series_id", "branch_id", "base_branch_id",
        "branch_mode", "forced_tokens",
    ]
    summary[text_columns] = summary[text_columns].astype(dtype)
    # Numeric-looking identifiers must not lose leading zeroes either.
    summary.loc[41, "series_id"] = "00017"
    summary.loc[41, "branch_id"] = "00007"
    summary["token_id"] = ["7", "8", "9", "10", "11", "12"]
    summary["window_id"] = summary.window_id.astype(str)
    summary[NORMALIZED_SCORE] = ["2", "7", "5", "3", "bad", "inf"]
    original = summary.copy(deep=True)

    prepared = visualization._prepare_summary_df(summary)

    pd.testing.assert_frame_equal(prepared[text_columns], original[text_columns])
    pd.testing.assert_frame_equal(summary, original)
    assert prepared.token_id.tolist() == [7, 8, 9, 10, 11, 12]
    assert prepared.window_id.tolist() == [0, 0, 0, 0, 1, 1]
    np.testing.assert_allclose(prepared[NORMALIZED_SCORE], [2, 7, 5, 3, np.nan, np.nan], equal_nan=True)


def test_grouped_error_scatter_has_one_point_per_distinct_series_window(summary, tmp_path, plotted_figures):
    frame = visualization._prepare_summary_df(summary)
    output = tmp_path / "error.png"
    assert visualization.plot_score_vs_base_error(frame, output) == output
    assert output.is_file()
    assert len(plotted_figures) == 1
    assert_scatter_groups(plotted_figures[0].axes[0], {
        "energy": [[0.2, 7], [0.3, 4]],
        "exchange": [[0.1, 5], [0.4, 9]],
    })


def test_raw_normalized_scatter_pairs_each_dataset_values(summary, tmp_path, plotted_figures):
    frame = visualization._prepare_summary_df(summary)
    output = tmp_path / "normalization.png"
    assert visualization.plot_raw_vs_normalized_score(frame, output) == output
    assert_scatter_groups(plotted_figures[0].axes[0], {
        "energy": [[70, 7], [30, 3], [40, 4]],
        "exchange": [[20, 2], [50, 5], [90, 9]],
    })


def test_logit_scatter_filters_base_without_misaligning_groups(summary, tmp_path, plotted_figures):
    summary.loc[12, "is_base_branch"] = True
    frame = visualization._prepare_summary_df(summary)
    output = tmp_path / "entropy.png"
    assert visualization.plot_score_vs_logit_metric(
        frame, output, metric_col="normalized_token_entropy", title="Entropy", xlabel="entropy",
    ) == output
    assert_scatter_groups(plotted_figures[0].axes[0], {
        "energy": [[0.44, 3], [0.66, 4]],
        "exchange": [[0.11, 2], [0.33, 5], [0.55, 9]],
    })


def test_window_overview_labels_keep_series_and_max_score_together(summary, tmp_path, plotted_figures):
    frame = visualization._prepare_summary_df(summary)
    output = tmp_path / "windows.png"
    assert visualization.plot_window_score_overview(frame, output) == output
    axis = plotted_figures[0].axes[0]
    labels = [label.get_text() for label in axis.get_yticklabels()]
    values = [patch.get_width() for patch in axis.patches]
    assert dict(zip(labels, values)) == {
        "energy/meter_2 @ 0": 7,
        "energy/meter_3 @ 4": 4,
        "exchange/currency_1 @ 0": 5,
        "exchange/currency_2 @ 4": 9,
    }
