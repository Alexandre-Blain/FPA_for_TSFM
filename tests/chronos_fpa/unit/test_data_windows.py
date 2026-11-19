"""Window boundaries and metadata, using only synthetic local series."""

import numpy as np
import pytest

from chronos_data import SeriesRecord, WindowRecord, iter_sliding_windows


def series(length):
    return SeriesRecord(
        dataset_name="synthetic", series_id="001", source="local",
        target=np.arange(length, dtype=float),
    )


def test_window_record_slices_nonzero_start_without_future_leakage():
    window = WindowRecord(
        dataset_name="synthetic", series_id="001", source="local", window_id=2,
        window_start=3, context_len=4, horizon=2, values=np.arange(12),
    )
    np.testing.assert_array_equal(window.context, [3, 4, 5, 6])
    np.testing.assert_array_equal(window.future, [7, 8])


def test_sliding_windows_include_last_exact_fit_and_preserve_identifiers():
    source = series(12)
    original = source.target.copy()
    windows = list(iter_sliding_windows(source, context_len=4, horizon=2, slide_step=3))
    assert [w.window_start for w in windows] == [0, 3, 6]
    assert [w.window_id for w in windows] == [0, 1, 2]
    for window, context, future in zip(
        windows, ([0, 1, 2, 3], [3, 4, 5, 6], [6, 7, 8, 9]),
        ([4, 5], [7, 8], [10, 11]),
    ):
        np.testing.assert_array_equal(window.context, context)
        np.testing.assert_array_equal(window.future, future)
        assert (window.dataset_name, window.series_id, window.source) == ("synthetic", "001", "local")
        assert (window.context_len, window.horizon) == (4, 2)
    np.testing.assert_array_equal(source.target, original)


@pytest.mark.parametrize("horizon,expected", [(5, [0, 2, 4]), (1, [0, 1, 2, 3, 4])])
def test_default_stride_is_half_horizon_with_minimum_one(horizon, expected):
    windows = list(iter_sliding_windows(series(4 + horizon + 4), 4, horizon))
    assert [w.window_start for w in windows] == expected


@pytest.mark.parametrize("length,expected_count", [(5, 0), (6, 1), (7, 2)])
def test_exact_fit_and_short_series(length, expected_count):
    windows = list(iter_sliding_windows(series(length), 4, 2, slide_step=1))
    assert len(windows) == expected_count


@pytest.mark.parametrize("limit,expected", [(None, [0, 2, 4, 6]), (2, [0, 2]), (0, [])])
def test_window_limit_is_applied_per_series(limit, expected):
    windows = list(iter_sliding_windows(series(12), 4, 2, 2, max_windows_per_series=limit))
    assert [w.window_start for w in windows] == expected


def test_adaptive_context_keeps_entire_horizon_at_minimum_boundary():
    windows = list(iter_sliding_windows(
        series(7), context_len=10, horizon=3, adaptive_context=True, min_context_len=4,
    ))
    assert len(windows) == 1
    assert windows[0].context_len == 4
    np.testing.assert_array_equal(windows[0].context, [0, 1, 2, 3])
    np.testing.assert_array_equal(windows[0].future, [4, 5, 6])


def test_adaptive_context_rejects_less_than_minimum_history():
    assert list(iter_sliding_windows(
        series(6), 10, 3, adaptive_context=True, min_context_len=4,
    )) == []


def test_adaptive_context_does_not_shrink_a_long_series():
    windows = list(iter_sliding_windows(
        series(12), 4, 2, slide_step=3, adaptive_context=True, min_context_len=2,
    ))
    assert [w.context_len for w in windows] == [4, 4, 4]
    assert [w.window_start for w in windows] == [0, 3, 6]


@pytest.mark.parametrize("kwargs", [
    {"context_len": 0}, {"context_len": -1}, {"horizon": 0}, {"horizon": -1},
    {"slide_step": 0}, {"slide_step": -2}, {"min_context_len": 0},
])
def test_nonpositive_window_parameters_fail(kwargs):
    options = dict(context_len=4, horizon=2)
    options.update(kwargs)
    with pytest.raises(ValueError, match="positive"):
        list(iter_sliding_windows(series(12), **options))
