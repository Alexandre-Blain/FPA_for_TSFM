"""The approved pilot must not silently broaden its inference population."""
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from chronos_data import SeriesRecord

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("controlled_pilot", ROOT / "scripts/runs/run_chronos_controlled_pilot.py")
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def test_approved_budget_and_exact_source_windows():
    config = json.loads((ROOT / "configs/chronos_controlled_pilot/phase2.json").read_text())
    series = [SeriesRecord(c["dataset_name"], c["series_id"], np.arange(800, dtype=np.float32), "fixture")
              for c in config["cases"]]
    windows = pilot.select_windows(config, series)
    jobs = pilot.planned_jobs(config, windows)
    assert len(jobs) == 14
    assert sum(pilot.work_units(config, case, b) for _, case, _, b in jobs) == 165000
    assert sum(config["num_samples"] * (case["top_k"] + 1) for _, case, _, _ in jobs) == 3000
    stress = windows[-1][1]
    assert stress.series_id == "currency_5"
    assert stress.context[0] == 96 and stress.context[-1] == 607
    assert stress.future[0] == 608 and len(stress.future) == 64


def test_missing_or_short_approved_window_is_not_replaced():
    config = {"context_len": 512, "horizon": 64, "cases": [
        {"dataset_name": "fixture", "series_id": "0001", "window_id": 0,
         "window_start": 0, "branch_steps": [0], "top_k": 3}]}
    with pytest.raises(ValueError, match="Missing approved series"):
        pilot.select_windows(config, [SeriesRecord("fixture", "1", np.arange(800), "fixture")])
    with pytest.raises(ValueError, match="exceeds series length"):
        pilot.select_windows(config, [SeriesRecord("fixture", "0001", np.arange(500), "fixture")])


def test_half_execution_has_seven_groups_including_one_repeat():
    config = json.loads((ROOT / "configs/chronos_controlled_pilot/phase2.json").read_text())
    plan = json.loads((ROOT / "configs/chronos_controlled_pilot/half_execution.json").read_text())
    series = [SeriesRecord(c["dataset_name"], c["series_id"], np.arange(800, dtype=np.float32), "fixture")
              for c in config["cases"]]
    jobs = pilot.planned_jobs(config, pilot.select_windows(config, series), plan)
    assert len(jobs) == 7
    assert sum(pilot.work_units(config, c, b) for _, c, _, b in jobs) == 78600
    assert sum(config["num_samples"] * (c["top_k"] + 1) for _, c, _, _ in jobs) == 1400
    assert [(seed, w.dataset_name, w.series_id, b) for seed, _, w, b in jobs][:2] == [
        (1729, "ercot", "EAST", 0), (2718, "ercot", "EAST", 0)]
    assert all(c["stratum"] == "main" for _, c, _, _ in jobs)


@pytest.mark.parametrize("defect", ["duplicate", "unknown", "scientific_override", "invalid_budget"])
def test_execution_plan_cannot_broaden_or_change_science(defect):
    config = json.loads((ROOT / "configs/chronos_controlled_pilot/phase2.json").read_text())
    plan = deepcopy(json.loads((ROOT / "configs/chronos_controlled_pilot/half_execution.json").read_text()))
    if defect == "duplicate":
        plan["groups"].append(plan["groups"][0])
    elif defect == "unknown":
        plan["groups"][0]["series_id"] = "not_approved"
    elif defect == "scientific_override":
        plan["temperature"] = .5
    else:
        plan["max_wall_seconds"] = 0
    with pytest.raises(ValueError):
        pilot.selected_groups(config, plan)
