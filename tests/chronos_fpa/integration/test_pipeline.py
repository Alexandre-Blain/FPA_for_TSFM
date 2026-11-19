"""The real orchestration and math, with a tiny offline model instead of weights."""
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd
import pytest
import torch

from chronos_io import ChronosConfigLite, create_tokenizer_from_config
from research_schema import read_csv


class TinyForecastModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(()))
        self.config = SimpleNamespace(decoder_start_token_id=0)

    def forward(self, input_ids, attention_mask, decoder_input_ids, **kwargs):
        logits = torch.full((*decoder_input_ids.shape, 16), -10.)
        for i, prefix in enumerate(decoder_input_ids):
            preferred = 8 if int(prefix[-1]) < 2 else min(int(prefix[-1]) + 1, 15)
            logits[i, -1] = -torch.abs(torch.arange(16, dtype=torch.float32) - preferred)
            logits[i, -1, :2] = 100.  # decoding MUST mask special tokens
        return SimpleNamespace(logits=logits)


def load_tiny(**kwargs):
    config = ChronosConfigLite(
        tokenizer_class="MeanScaleUniformBins", tokenizer_kwargs={"low_limit": -2., "high_limit": 2.},
        context_length=8, prediction_length=4, n_tokens=16, n_special_tokens=2,
        pad_token_id=0, eos_token_id=1, use_eos_token=True, model_type="seq2seq",
    )
    return TinyForecastModel(), create_tokenizer_from_config(config), config


def test_controlled_pilot_offline_analysis_of_partial_run(tmp_path, monkeypatch):
    import importlib.util
    import numpy as np
    from checkpoint_store import GroupStore
    from chronos_benchmark_scan import scan_window
    from chronos_data import WindowRecord

    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("partial_pilot_analysis", root / "scripts/viz/analyze_chronos_controlled_pilot.py")
    analysis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analysis)
    monkeypatch.setattr(analysis, "ROOT", tmp_path)
    run_dir = tmp_path / "pilot"
    run_dir.mkdir()
    config = {"seeds": [1729, 2718], "nested_sample_counts": [20, 50],
              "probability_thresholds": [0., .001, .01, .05], "cases": [
                  {"dataset_name": "demo", "series_id": "001", "window_id": 0,
                   "branch_steps": [0, 2], "stratum": "main"}]}
    (run_dir / "config.json").write_text(json.dumps(config))
    stores = {seed: GroupStore(run_dir / f"seed_{seed}") for seed in config["seeds"]}
    for store in stores.values():
        store.recover()
    model, tokenizer, chronos_config = load_tiny()
    window = WindowRecord("demo", "001", "synthetic", 0, 0, 8, 4, np.arange(1, 13, dtype=np.float32))
    steps, summary = scan_window(
        model, tokenizer, chronos_config, window, branch_steps=[0], branch_modes=["single"],
        top_k=3, num_samples=50, trajectory_options={"sampling_seed": 1729,
            "output_dir": run_dir / "seed_1729/trajectories", "provenance": {}},
    )
    stores[1729].commit(steps, summary)
    analysis.analyze(run_dir)
    output = run_dir / "analysis"
    protocol = json.loads((output / "analysis_protocol.json").read_text())
    assert protocol["observed_fork_point_seed_groups"] == 1
    assert protocol["planned_fork_point_seed_groups"] == 4
    assert len(protocol["missing_approved_groups"]) == 3
    assert protocol["observed_original_series"] == 1
    effects = read_csv(output / "branch_effects.csv")
    assert len(effects) == 4 and effects.series_id.eq("001").all()
    assert set(effects.num_samples) == {20, 50}
    assert set(effects.seed) == {1729}
    correlations = read_csv(output / "descriptive_correlations.csv")
    assert correlations.coefficient.isna().all()
    figures = list((output / "figures").rglob("*.png"))
    assert len(figures) == 4 and all(p.stat().st_size > 1000 for p in figures)


def test_pilot_reduced_resume_preserves_completed_group_and_old_analysis(tmp_path, monkeypatch):
    import numpy as np
    import run_chronos_controlled_pilot as pilot
    import analyze_chronos_controlled_pilot as analysis
    import chronos_benchmark_scan
    import chronos_io

    monkeypatch.setattr(pilot, "ROOT", tmp_path)
    monkeypatch.setattr(analysis, "ROOT", tmp_path)
    monkeypatch.setattr(torch, "set_num_interop_threads", lambda _: None)
    def fake_loader(*args, **kwargs):
        model, tokenizer, config = load_tiny()
        model.config._commit_hash = "fake"
        return model, tokenizer, config
    monkeypatch.setattr(chronos_io, "load_chronos_t5_raw", fake_loader)
    data = tmp_path / "data"
    data.mkdir()
    (data / "demo.jsonl").write_text(json.dumps({"dataset_name": "demo", "series_id": "001",
        "source_repo": "synthetic", "target": np.arange(1, 13).tolist()}) + "\n")
    config = {"model_id": "fake", "model_revision": "fake", "benchmark_folder": str(data),
              "context_len": 8, "horizon": 4, "temperature": 1, "sample_top_k": 50,
              "num_samples": 50, "nested_sample_counts": [20, 50], "seeds": [1729, 2718],
              "cpu_threads": 1, "max_wall_seconds": 999999, "timing_safety_factor": 1.5,
              "probability_thresholds": [0., .001, .01, .05], "cases": [
                  {"dataset_name": "demo", "series_id": "001", "window_id": 0, "window_start": 0,
                   "branch_steps": [0, 2], "top_k": 3, "stratum": "main"}]}
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    real_scan = chronos_benchmark_scan.scan_window
    def interrupted(*args, **kwargs):
        callback = kwargs["checkpoint_callback"]
        def commit_and_stop(*parts):
            callback(*parts)
            raise KeyboardInterrupt("stop after first committed pilot group")
        kwargs["checkpoint_callback"] = commit_and_stop
        return real_scan(*args, **kwargs)
    monkeypatch.setattr(chronos_benchmark_scan, "scan_window", interrupted)
    with pytest.raises(KeyboardInterrupt):
        pilot.run(config_path)
    run_dir = next((tmp_path / "result").iterdir())
    old_manifest = next((run_dir / "seed_1729/trajectories").glob("*/manifest.json"))
    old_bytes = old_manifest.read_bytes(), old_manifest.with_name("ensembles.npz").read_bytes()
    old_config = (run_dir / "config.json").read_bytes()
    (run_dir / "analysis").mkdir()
    sentinel = run_dir / "analysis/snapshot.txt"
    sentinel.write_text("preserve original partial analysis")
    plan = {"version": 1, "reason": "explicitly reduced test scope", "max_wall_seconds": 999999,
            "groups": [{"seed": s, "dataset_name": "demo", "series_id": "001", "window_id": 0,
                        "branch_step": 0} for s in (1729, 2718)]}
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    calls = []
    def tracked(*args, **kwargs):
        calls.append((kwargs["trajectory_options"]["sampling_seed"], kwargs["branch_steps"]))
        return real_scan(*args, **kwargs)
    monkeypatch.setattr(chronos_benchmark_scan, "scan_window", tracked)
    pilot.run(config_path, run_dir, plan_path)
    assert calls == [(2718, [0])]
    assert (run_dir / "config.json").read_bytes() == old_config
    assert old_bytes == (old_manifest.read_bytes(), old_manifest.with_name("ensembles.npz").read_bytes())
    assert json.loads((run_dir / "progress.json").read_text())["completed_groups"] == 2
    assert (run_dir / "progress_before_execution_plan.json").exists()
    monkeypatch.setattr(chronos_io, "load_chronos_t5_raw", lambda *a, **k: pytest.fail("Completed resume must not load a model"))
    pilot.run(config_path, run_dir)
    analysis.analyze(run_dir)
    final = json.loads((run_dir / "analysis_half/analysis_protocol.json").read_text())
    assert final["planned_fork_point_seed_groups"] == final["observed_fork_point_seed_groups"] == 2
    assert final["missing_approved_groups"] == []
    assert sentinel.read_text() == "preserve original partial analysis"


@pytest.fixture
def launchers(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "runs"))
    scan = importlib.import_module("run_chronos_benchmark_scan")
    refine = importlib.import_module("run_chronos_targeted_refinement")
    monkeypatch.setattr(scan, "load_chronos_t5_raw", load_tiny)
    monkeypatch.setattr(refine, "load_chronos_t5_raw", load_tiny)
    return scan, refine


def parameters(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "example.jsonl").write_text(json.dumps({
        "dataset_name": "demo", "series_id": "001", "source_repo": "synthetic",
        "target": [1., 2., 3., 4., 3., 2., 1., 2., 3., 4., 5., 4.],
    }) + "\n", encoding="utf-8")
    return ["--benchmark-folder", str(data), "--context-len", "8", "--min-context-len", "4",
            "--horizon", "4", "--branch-steps", "0,2", "--branch-modes", "single",
            "--top-k", "2", "--num-samples", "3", "--sample-top-k", "0",
            "--max-total-windows", "1", "--no-progress", "--output-root", str(tmp_path / "result")]


def test_scan_interrupt_resume_matches_uninterrupted_and_keeps_initial_config(tmp_path, launchers, monkeypatch):
    scan, _ = launchers
    args = parameters(tmp_path)
    actual_scan = scan.scan_window
    def interrupted(**kwargs):
        callback = kwargs["checkpoint_callback"]
        def stop_after_commit(*parts):
            callback(*parts)
            raise KeyboardInterrupt("hardware interruption after one completed group")
        kwargs["checkpoint_callback"] = stop_after_commit
        return actual_scan(**kwargs)
    monkeypatch.setattr(scan, "scan_window", interrupted)
    torch.manual_seed(42)
    with pytest.raises(KeyboardInterrupt):
        scan.run(args + ["--run-name", "interrupted"])
    run_dir = next((tmp_path / "result").glob("interrupted_*"))
    original_config = (run_dir / "input_config.json").read_bytes()
    assert len(list((run_dir / "branch_groups").glob("*/manifest.json"))) == 1
    monkeypatch.setattr(scan, "scan_window", actual_scan)
    scan.run(["--resume-from", str(run_dir)])
    assert (run_dir / "input_config.json").read_bytes() == original_config
    torch.manual_seed(42)
    scan.run(args + ["--run-name", "continuous"])
    continuous = next((tmp_path / "result").glob("continuous_*"))
    columns = ["branch_step", "token_id", "series_id"]
    for name in ("steps", "summary"):
        a = read_csv(run_dir / f"chronos_scan_{name}.csv")
        b = read_csv(continuous / f"chronos_scan_{name}.csv")
        sort = columns + (["forecast_step"] if name == "steps" else [])
        pd.testing.assert_frame_equal(a.sort_values(sort).reset_index(drop=True), b.sort_values(sort).reset_index(drop=True))
    assert json.loads((run_dir / "checkpoint.json").read_text())["status"] == "complete"


def test_scan_auto_refinement_and_offline_analysis(tmp_path, launchers):
    scan, _ = launchers
    args = parameters(tmp_path)
    scan.run(args + ["--run-name", "automatic", "--auto-refinement", "--refinement-global-top-windows", "1",
                     "--refinement-per-dataset-top-windows", "1", "--refinement-branch-steps", "0,2",
                     "--refinement-top-k", "3", "--refinement-num-samples", "3"])
    run_dir = next((tmp_path / "result").glob("automatic_*"))
    refinement = next((run_dir / "refinement").iterdir())
    summary = read_csv(refinement / "chronos_scan_summary.csv")
    assert len(summary) == 6
    assert summary.series_id.unique().tolist() == ["001"]
    assert json.loads((refinement / "checkpoint.json").read_text())["status"] == "complete"
    from chronos_uncertainty_alignment import analyze_run_uncertainty_alignment
    from chronos_scenario_sensitivity import analyze_run_scenario_sensitivity
    uncertainty = analyze_run_uncertainty_alignment(refinement)
    scenarios = analyze_run_scenario_sensitivity(refinement)
    assert uncertainty.csv_paths and scenarios.csv_paths
    assert all(path.stat().st_size for path in uncertainty.csv_paths + scenarios.csv_paths)
    # Resuming the parent run must reuse its original refinement, not create
    # another expensive experiment with the same settings.
    scan.run(["--resume-from", str(run_dir)])
    assert len(list((run_dir / "refinement").iterdir())) == 1


def test_resolved_error_remains_logged_without_blocking_completion(tmp_path, launchers, monkeypatch):
    scan, _ = launchers
    real_scan = scan.scan_window
    monkeypatch.setattr(scan, "scan_window", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("temporary compute failure")))
    scan.run(parameters(tmp_path) + ["--run-name", "retry"])
    run_dir = next((tmp_path / "result").glob("retry_*"))
    assert json.loads((run_dir / "checkpoint.json").read_text())["status"] == "partial"
    monkeypatch.setattr(scan, "scan_window", real_scan)
    scan.run(["--resume-from", str(run_dir)])
    assert json.loads((run_dir / "checkpoint.json").read_text())["status"] == "complete"
    assert len(read_csv(run_dir / "chronos_scan_errors.csv")) == 1


def test_parent_resume_continues_interrupted_refinement_in_same_folder(tmp_path, launchers, monkeypatch):
    scan, refinement = launchers
    real_refine = refinement.scan_window
    def interrupt(**kwargs):
        callback = kwargs["checkpoint_callback"]
        def save_and_interrupt(*parts):
            callback(*parts)
            raise KeyboardInterrupt("refinement interrupted after commit")
        kwargs["checkpoint_callback"] = save_and_interrupt
        return real_refine(**kwargs)
    monkeypatch.setattr(refinement, "scan_window", interrupt)
    args = parameters(tmp_path) + ["--run-name", "parent", "--auto-refinement",
                                  "--refinement-global-top-windows", "1", "--refinement-per-dataset-top-windows", "1",
                                  "--refinement-branch-steps", "0,2", "--refinement-top-k", "3", "--refinement-num-samples", "3"]
    with pytest.raises(KeyboardInterrupt):
        scan.run(args)
    run_dir = next((tmp_path / "result").glob("parent_*"))
    original_refinement = Path(json.loads((run_dir / "refinement_state.json").read_text())["run_dir"])
    assert json.loads((run_dir / "checkpoint.json").read_text())["status"] == "refinement_running"
    assert len(list((original_refinement / "branch_groups").glob("*/manifest.json"))) == 1
    monkeypatch.setattr(refinement, "scan_window", real_refine)
    scan.run(["--resume-from", str(run_dir)])
    assert list((run_dir / "refinement").iterdir()) == [original_refinement]
    assert json.loads((original_refinement / "checkpoint.json").read_text())["status"] == "complete"


def test_single_and_bundle_exports_keep_both_schemas_through_resume(tmp_path, launchers):
    scan, _ = launchers
    scan.run(parameters(tmp_path) + ["--run-name", "mixed", "--branch-modes", "single,bundle"])
    run_dir = next((tmp_path / "result").glob("mixed_*"))
    summary = read_csv(run_dir / "chronos_scan_summary.csv")
    assert set(summary.branch_mode) == {"single", "bundle"}
    assert len(list((run_dir / "branch_groups").glob("*/manifest.json"))) == 3
    assert summary.loc[summary.branch_mode.eq("single"), "token_id"].notna().all()
    assert summary.loc[summary.branch_mode.eq("bundle"), "branch_id"].notna().all()
    scan.run(["--resume-from", str(run_dir)])
    assert len(read_csv(run_dir / "chronos_scan_summary.csv")) == len(summary)


def test_paper1_exports_roundtrip_distances_and_independent_null(tmp_path, launchers):
    import numpy as np
    from chronos_distances import empirical_w1_by_horizon, energy_distance_v
    from trajectory_export import load_fork_ensembles
    scan, _ = launchers
    config = tmp_path / 'paper1.json'
    config.write_text(json.dumps({'parameters': {'save_trajectories': True, 'sampling_seed': 71}}))
    scan.run(parameters(tmp_path) + ['--config', str(config), '--run-name', 'paper1'])
    run_dir = next((tmp_path / 'result').glob('paper1_*'))
    summary = read_csv(run_dir / 'chronos_scan_summary.csv')
    steps = read_csv(run_dir / 'chronos_scan_steps.csv')
    assert summary.series_id.unique().tolist() == ['001']
    assert summary.post_fork_length.tolist() == summary.branch_step.map({0: 3, 2: 1}).tolist()
    assert steps.loc[steps.forecast_step <= steps.branch_step, 'w1_post_h'].isna().all()
    assert summary.trajectory_manifest.nunique() == 2
    for link in summary.trajectory_manifest.unique():
        manifest, arrays = load_fork_ensembles(run_dir / link)
        base = arrays[manifest['reference_array_key']]
        assert base.shape[0] == 3
        assert base.dtype == np.float32
        assert manifest['window']['series_id'] == '001'
        assert manifest['post_fork_start'] == manifest['branch_step'] + 1
        assert manifest['provenance']['model_id'] == 'amazon/chronos-t5-mini'
        assert manifest['provenance']['code_version']['source_sha256']
        group = summary[summary.trajectory_manifest == link]
        for entry in manifest['ensembles']:
            samples = arrays[entry['array_key']]
            row = group[group.token_id == entry['token_id']].iloc[0]
            assert row.w1_post == pytest.approx(empirical_w1_by_horizon(base, samples).mean())
            assert row.ed_post == pytest.approx(energy_distance_v(base, samples))
            assert row.w1_post_over_context_iqr == pytest.approx(row.w1_post / manifest['context_iqr'])
        assert manifest['same_token_null']['rng']['stream_id'] != group.reference_rng_stream_id.iloc[0]
        assert group.same_token_null_ed_post.iloc[0] == pytest.approx(energy_distance_v(base, arrays['same_token_null']))
    before = {p: p.read_bytes() for p in (run_dir / 'trajectories').rglob('*') if p.is_file()}
    scan.run(['--resume-from', str(run_dir)])
    assert all(p.read_bytes() == content for p, content in before.items())


def test_paper1_resume_and_continuous_ensembles_match(tmp_path, launchers, monkeypatch):
    from trajectory_export import load_fork_ensembles
    import numpy as np
    scan, _ = launchers
    arguments = parameters(tmp_path) + ['--save-trajectories', '--sampling-seed', '81']
    original = scan.scan_window
    def interrupted(**kwargs):
        callback = kwargs['checkpoint_callback']
        def stop(*parts):
            callback(*parts)
            raise KeyboardInterrupt('after the first archive and group are durable')
        kwargs['checkpoint_callback'] = stop
        return original(**kwargs)
    monkeypatch.setattr(scan, 'scan_window', interrupted)
    with pytest.raises(KeyboardInterrupt):
        scan.run(arguments + ['--run-name', 'paused'])
    paused = next((tmp_path / 'result').glob('paused_*'))
    monkeypatch.setattr(scan, 'scan_window', original)
    torch.manual_seed(99999)
    scan.run(['--resume-from', str(paused)])
    scan.run(arguments + ['--run-name', 'continuous_paper1'])
    continuous = next((tmp_path / 'result').glob('continuous_paper1_*'))
    for name in ('summary', 'steps'):
        a, b = read_csv(paused / f'chronos_scan_{name}.csv'), read_csv(continuous / f'chronos_scan_{name}.csv')
        pd.testing.assert_frame_equal(a, b)
    for file in (paused / 'trajectories').glob('*/manifest.json'):
        ma, aa = load_fork_ensembles(file)
        mb, ab = load_fork_ensembles(continuous / file.relative_to(paused))
        assert ma == mb
        for key in aa:
            np.testing.assert_array_equal(aa[key], ab[key])
    with pytest.raises(ValueError, match='Incompatible resume'):
        scan.run(['--resume-from', str(paused), '--sampling-seed', '82'])


def test_paper1_checkpoint_rejects_missing_or_corrupt_raw_arrays(tmp_path, launchers):
    from checkpoint_store import GroupStore
    from trajectory_export import load_fork_ensembles
    import numpy as np
    import zipfile
    scan, _ = launchers
    scan.run(parameters(tmp_path) + ['--save-trajectories', '--run-name', 'integrity'])
    directory = next((tmp_path / 'result').glob('integrity_*'))
    archive = next((directory / 'trajectories').glob('*/ensembles.npz'))
    contents = archive.read_bytes()
    archive.unlink()
    with pytest.raises(FileNotFoundError):
        GroupStore(directory).recover()
    archive.write_bytes(contents[:40])
    with pytest.raises(zipfile.BadZipFile):
        GroupStore(directory).recover()
    archive.write_bytes(contents)
    manifest_path = archive.with_name('manifest.json')
    manifest, arrays = load_fork_ensembles(manifest_path)
    array_name = manifest['reference_array_key']
    arrays[array_name][0, 0] += 1.
    np.savez_compressed(archive, **arrays)
    with pytest.raises(ValueError, match='checksum'):
        GroupStore(directory).recover()
    archive.write_bytes(contents)
    manifest['window']['series_id'] = 'wrong-series'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError, match='window identity'):
        GroupStore(directory).recover()


def test_paper1_metrics_without_raw_saving_and_no_default_schema_changes(tmp_path, launchers):
    scan, _ = launchers
    args = parameters(tmp_path)
    scan.run(args + ['--run-name', 'old_path'])
    historical = next((tmp_path / 'result').glob('old_path_*'))
    assert 'w1_post' not in read_csv(historical / 'chronos_scan_summary.csv')
    state_path = historical / 'run_state.json'
    state = json.loads(state_path.read_text())
    for key in ['trajectory_metrics', 'save_trajectories', 'sampling_seed']:
        state['args'].pop(key)
    state_path.write_text(json.dumps(state))
    with pytest.raises(ValueError, match='Incompatible resume'):
        scan.run(['--resume-from', str(historical), '--save-trajectories'])
    scan.run(args + ['--trajectory-metrics', '--run-name', 'metrics_only'])
    measured = next((tmp_path / 'result').glob('metrics_only_*'))
    assert 'w1_post' in read_csv(measured / 'chronos_scan_summary.csv')
    assert not (measured / 'trajectories').exists()
    with pytest.raises(ValueError, match='single'):
        scan.run(args + ['--save-trajectories', '--branch-modes', 'bundle'])


def test_paper1_auto_refinement_keeps_options_and_raw_exports(tmp_path, launchers):
    scan, _ = launchers
    scan.run(parameters(tmp_path) + ['--save-trajectories', '--sampling-seed', '18', '--run-name', 'auto_paper1',
        '--auto-refinement', '--refinement-global-top-windows', '1', '--refinement-per-dataset-top-windows', '1',
        '--refinement-branch-steps', '0', '--refinement-top-k', '2', '--refinement-num-samples', '3'])
    directory = next((tmp_path / 'result').glob('auto_paper1_*'))
    refinement = next((directory / 'refinement').iterdir())
    summary = read_csv(refinement / 'chronos_scan_summary.csv')
    assert summary.trajectory_manifest.notna().all()
    state = json.loads((refinement / 'run_state.json').read_text())
    assert state['args']['sampling_seed'] == 18 and state['args']['save_trajectories']


def test_paper1_archive_published_before_interruption_is_reused(tmp_path, launchers, monkeypatch):
    scan, _ = launchers
    original = scan.scan_window
    def interrupted(**kwargs):
        def stop_before_commit(*parts):
            raise KeyboardInterrupt('archive exists but the group is not committed')
        kwargs['checkpoint_callback'] = stop_before_commit
        return original(**kwargs)
    monkeypatch.setattr(scan, 'scan_window', interrupted)
    with pytest.raises(KeyboardInterrupt):
        scan.run(parameters(tmp_path) + ['--save-trajectories', '--run-name', 'uncommitted'])
    directory = next((tmp_path / 'result').glob('uncommitted_*'))
    before = {p: p.read_bytes() for p in (directory / 'trajectories').rglob('*') if p.is_file()}
    assert before
    assert not list((directory / 'branch_groups').glob('*/manifest.json'))
    monkeypatch.setattr(scan, 'scan_window', original)
    scan.run(['--resume-from', str(directory)])
    assert all(p.read_bytes() == content for p, content in before.items())
    assert len(list((directory / 'branch_groups').glob('*/manifest.json'))) == 2
