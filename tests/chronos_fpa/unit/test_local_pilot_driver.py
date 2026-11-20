from run_chronos_local_pilot import cell_plan


def test_plan_is_ten_cells_first_two_distinct_then_preselected_calibration():
    windows = [{"dataset_id": dataset, "series_id": str(i), "forecast_origin": 512,
                "context_sha256": str(i) * 64, "window_id": dataset + str(i), "stratum": stratum}
               for dataset in ("m4_daily", "ercot", "exchange_rate")
               for i, stratum in enumerate(("representative", "diversity"))]
    panel = {"windows": windows, "grid_revision": "frozen", "config": {
        "primary_seed": 12, "replication_seeds": [13, 14], "model_revision": "pinned"}}
    cells = cell_plan(panel)
    assert len(cells) == len({c["cell_id"] for c in cells}) == 10
    assert [c["scope"]["dataset_id"] for c in cells[:2]] == ["m4_daily", "ercot"]
    assert all(c["primary"] for c in cells[:6])
    assert all(not c["primary"] and c["stratum"] == "representative" for c in cells[6:])
    assert {c["scope"]["sampling_seed"] for c in cells[6:]} == {13, 14}
