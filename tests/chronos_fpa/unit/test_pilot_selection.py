import copy
import json

import numpy as np
import pytest

from chronos_pilot_selection import FEATURES, choose_pair, context_features, eligible_row, rank_features, select_panel


def test_selection_features_never_depend_on_future_values():
    row = {"series_id": "A", "target": (np.sin(np.arange(600) / 11) + np.arange(600) / 90).tolist()}
    original, context = eligible_row(row, "fake", [])
    changed = copy.deepcopy(row)
    changed["target"][-32:] = [float("nan")] * 32
    actual, second = eligible_row(changed, "fake", [])
    assert actual == original
    np.testing.assert_array_equal(context, second)
    scaled = context_features(context * 4)
    for feature in FEATURES:
        assert scaled[feature] == pytest.approx(original[feature], abs=1e-7)
    assert scaled["context_iqr"] == pytest.approx(4 * original["context_iqr"])
    with pytest.raises(ValueError, match="previously_studied"):
        eligible_row(row, "fake", ["A"])
    with pytest.raises(ValueError):
        eligible_row({"series_id": "A", "target": [1.] * 544}, "fake", [])


def test_rank_ties_and_farthest_nonextreme_diversity_are_deterministic():
    records = [{"series_id": str(i), **{feature: float(i // 2) for feature in FEATURES}} for i in range(12)]
    ranks = rank_features(records)
    np.testing.assert_allclose(ranks[0], .5 / 11)
    pair = choose_pair(records, "fake", 13)
    assert pair == choose_pair(list(reversed(records)), "fake", 13)
    rep, diverse = [int(r["series_id"]) for r in pair]
    # choose_pair uses lexical series ordering, as recorded in its contract.
    ordered = sorted(records, key=lambda r: r["series_id"])
    ranks = rank_features(ordered)
    rep_index = next(i for i, r in enumerate(ordered) if int(r["series_id"]) == rep)
    radius = ((ranks - np.median(ranks, axis=0)) ** 2).mean(axis=1)
    distance = ((ranks - ranks[rep_index]) ** 2).mean(axis=1)
    candidates = [i for i in range(12) if i != rep_index and radius[i] <= np.quantile(radius, .9)]
    expected = min(candidates, key=lambda i: (-distance[i], ordered[i]["series_id"]))
    assert diverse == int(ordered[expected]["series_id"])


def test_panel_freezes_six_distinct_series_and_rejection_provenance(tmp_path):
    folder = tmp_path / "data/raw/chronos_benchmark"
    folder.mkdir(parents=True)
    config = {"datasets": ["a", "b", "c"], "known_studied_series": {"a": ["old"]}, "selection_seed": 99}
    for dataset in config["datasets"]:
        rows = [{"series_id": str(i), "target": (np.sin(np.arange(600) / (i + 2)) + np.arange(600) / 100).tolist()}
                for i in range(5)]
        rows += [{"series_id": "bad_scale", "target": [0.] * 600}, {"series_id": "old", "target": [1.] * 600}]
        (folder / f"autogluon_chronos_datasets__{dataset}__train.jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    panel, contexts = select_panel(tmp_path, config)
    assert panel == select_panel(tmp_path, config)[0]
    assert len(panel["windows"]) == len(contexts) == 6
    assert len({(r["dataset_id"], r["series_id"]) for r in panel["windows"]}) == 6
    assert len(panel["rejections"]) == 6
    for window in panel["windows"]:
        assert window["forecast_origin"] == 568
        assert window["context_start"] == 56
        assert len(contexts[window["window_id"]]) == 512
