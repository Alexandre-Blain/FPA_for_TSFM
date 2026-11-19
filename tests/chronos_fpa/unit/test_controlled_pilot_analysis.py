"""Independently known sample distances and traceable gallery selection."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("pilot_analysis", ROOT / "scripts/viz/analyze_chronos_controlled_pilot.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def test_spearman_with_ties_works_without_scipy(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def without_scipy(name, *args, **kwargs):
        if name == "scipy" or name.startswith("scipy."):
            raise ModuleNotFoundError("SciPy intentionally unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_scipy)
    x, y = pd.Series([1., 2., 2., 4.]), pd.Series([1., 3., 3., 2.])
    assert analysis.descriptive_correlation(x, y, "spearman") == pytest.approx(1 / 3)
    assert analysis.descriptive_correlation(x, x * -3 + 7, "pearson") == pytest.approx(-1)


def test_log_comparison_limits_use_actual_positive_data():
    assert analysis.comparison_limits([.02, .04], [.08, .1]) == pytest.approx((.016, .125))
    assert analysis.comparison_limits([0, np.nan], [.02, .1]) == pytest.approx((.016, .125))


def test_saved_metrics_known_constant_displacement():
    reference = np.zeros((50, 63))
    alternative = reference + 3
    null = reference.copy()
    metrics, profile, floor = analysis.compare_saved(reference, alternative, null, 20, 2)
    assert metrics["w1_post"] == 3
    assert metrics["ed_post"] == pytest.approx(6)
    assert metrics["w1_post_iqr"] == 1.5
    assert metrics["ed_post_iqr"] == pytest.approx(3)
    assert metrics["null_w1_post"] == 0
    assert np.isnan(metrics["w1_over_null"])
    assert metrics["common_length"] == 47
    assert metrics["w1_first47_iqr"] == 1.5
    assert metrics["reference_end_minus_start_zero_count"] == 20
    np.testing.assert_array_equal(profile, np.full(63, 3.))
    np.testing.assert_array_equal(floor, np.zeros(63))


def test_nested_count_does_not_use_later_paths():
    reference = np.zeros((50, 63))
    alternative = reference.copy()
    alternative[20:] = 10
    small, _, _ = analysis.compare_saved(reference, alternative, reference, 20, 1)
    large, _, _ = analysis.compare_saved(reference, alternative, reference, 50, 1)
    assert small["w1_post"] == 0
    assert large["w1_post"] == 6


def test_gallery_on_partial_population_has_no_duplicate_forks():
    frame = pd.DataFrame([
        dict(dataset_name="fixture", series_id="0001", window_id=0, branch_step=0,
             token_id=i, stratum="main", num_samples=50, w1_post_iqr=i / 10,
             ed_post_iqr=i / 20, w1_over_null=i, ed_over_null=i, direct_jump_iqr=1)
        for i in (2, 3)
    ])
    gallery = analysis.choose_gallery(frame)
    assert len(gallery) == 2
    assert not gallery.duplicated(analysis.IDENTITY).any()
    assert gallery.series_id.eq("0001").all()
