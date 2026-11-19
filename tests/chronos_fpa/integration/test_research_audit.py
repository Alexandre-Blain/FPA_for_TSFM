import json

import pandas as pd
import pytest

from audit_research_runs import DataInventory, audit_run, snapshot, compare_manifests
from fpa_test_tables import group_tables


def make_run(tmp_path, branch_steps="0"):
    directory = tmp_path / "example"
    directory.mkdir()
    (directory / "config.json").write_text(json.dumps({"args": {
        "source": "benchmark-folder", "branch_modes": "single", "branch_steps": branch_steps,
        "context_len": 4, "horizon": 3, "max_total_windows": 1,
        "benchmark_folder": str(tmp_path / "unavailable_data"),
    }}))
    steps, summary = group_tables()
    steps.to_csv(directory / "chronos_scan_steps.csv", index=False)
    summary.to_csv(directory / "chronos_scan_summary.csv", index=False)
    return directory


def test_audit_preserves_incomplete_experiment_and_separates_integrity(tmp_path):
    directory = make_run(tmp_path, "0,1")
    before = snapshot({"result": tmp_path})
    result = audit_run(directory, tmp_path, DataInventory())
    assert result["completion"]["status"] == "partial"
    assert result["integrity"]["status"] == "consistent"
    assert result["pairing"]["summary_branches"] == 2
    assert compare_manifests(before, snapshot({"result": tmp_path}))["preserved"]


def test_audit_reports_ragged_rows_without_erasing_them(tmp_path):
    directory = make_run(tmp_path)
    path = directory / "chronos_scan_summary.csv"
    with path.open("a") as stream:
        stream.write("broken,row\n")
    original = path.read_bytes()
    result = audit_run(directory, tmp_path, DataInventory())
    assert result["integrity"]["status"] == "inconsistent"
    assert result["tables"][path.name]["rejected_count"] == 1
    assert result["tables"][path.name]["rejected_rows"][0]["line"] == 4
    assert path.read_bytes() == original


def test_audit_pairs_steps_and_summaries_and_detects_missing_horizon(tmp_path):
    directory = make_run(tmp_path)
    steps, _ = group_tables()
    steps.iloc[:-1].to_csv(directory / "chronos_scan_steps.csv", index=False)
    result = audit_run(directory, tmp_path, DataInventory())
    assert len(result["pairing"]["incomplete_horizons"]) == 1
    assert result["completion"]["status"] == "partial"
    assert result["integrity"]["status"] == "inconsistent"
