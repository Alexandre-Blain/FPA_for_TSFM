"""Run the explicitly budgeted Phase 2 design, never a benchmark sweep."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code" / "chronos_fpa"))
import bootstrap  # noqa: E402,F401

from chronos_data import WindowRecord, iter_benchmark_folder_series
from controlled_pilot_plan import selected_groups
from research_schema import window_key
from results_io import save_json


def select_windows(config, series):
    requested = {(case["dataset_name"], case["series_id"]) for case in config["cases"]}
    found = {}
    for item in series:
        key = item.dataset_name, item.series_id
        if key in requested:
            if key in found:
                raise ValueError(f"Ambiguous source series: {key}")
            found[key] = item
        if set(found) == requested:
            break
    if set(found) != requested:
        raise ValueError(f"Missing approved series: {requested - set(found)}")
    windows = []
    for case in config["cases"]:
        item = found[(case["dataset_name"], case["series_id"])]
        end = case["window_start"] + config["context_len"] + config["horizon"]
        if end > len(item.target):
            raise ValueError(f"Approved window exceeds series length: {case}")
        windows.append((case, WindowRecord(
            item.dataset_name, item.series_id, item.source, case["window_id"],
            case["window_start"], config["context_len"], config["horizon"], item.target,
        )))
    return windows


def planned_jobs(config, windows, execution_plan=None):
    by_window = {(w.dataset_name, w.series_id, w.window_id): (case, w) for case, w in windows}
    jobs = []
    for group in selected_groups(config, execution_plan):
        case, window = by_window[(group["dataset_name"], group["series_id"], group["window_id"])]
        jobs.append((group["seed"], case, window, group["branch_step"]))
    return jobs


def work_units(config, case, step):
    # Approximate timing only: includes one extra, independently sampled null.
    return config["num_samples"] * (case["top_k"] + 1) * (config["horizon"] - step - 1)


def run(config_path, resume_from=None, execution_plan_path=None):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    # This pilot is deliberately offline and CPU-only, with a single model.
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        os.environ[name] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    import numpy as np
    import torch
    from checkpoint_store import GroupStore
    from chronos_benchmark_scan import scan_window
    from chronos_io import load_chronos_t5_raw
    from trajectory_export import trajectory_options_from_args

    torch.set_num_threads(config["cpu_threads"])
    torch.set_num_interop_threads(1)
    started = time.monotonic()
    resuming = resume_from is not None
    run_dir = Path(resume_from) if resuming else ROOT / "result" / (
        "phase2_controlled_pilot_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    if resuming:
        saved = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
        if saved != config:
            raise ValueError("Pilot config differs from saved config; resume refused")
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        save_json(run_dir / "config.json", config)
    plan_path = run_dir / "execution_plan.json"
    saved_plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else None
    plan = json.loads(Path(execution_plan_path).read_text(encoding="utf-8")) if execution_plan_path else saved_plan
    selected_groups(config, plan)
    if saved_plan is not None and plan != saved_plan:
        raise ValueError("Execution plan differs from the saved amendment; resume refused")
    wall_budget = plan["max_wall_seconds"] if plan else config["max_wall_seconds"]
    print(f"Pilot outputs: {run_dir}", flush=True)
    windows = select_windows(config, iter_benchmark_folder_series(
        ROOT / config["benchmark_folder"], dataset_names={c["dataset_name"] for c in config["cases"]}))
    selection = [{"window_key": list(window_key(window)), "stratum": case["stratum"],
                  "branch_steps": case["branch_steps"], "top_k": case["top_k"],
                  "context_sha256": hashlib.sha256(np.asarray(window.context, dtype=np.float32).tobytes()).hexdigest()}
                 for case, window in windows]
    selection_path = run_dir / "selection.json"
    if resuming and json.loads(selection_path.read_text(encoding="utf-8")) != selection:
        raise ValueError("Source contexts or selection changed; resume refused")
    if not resuming:
        save_json(selection_path, selection)
    timing_path = run_dir / "progress.json"
    previous = json.loads(timing_path.read_text(encoding="utf-8")) if resuming and timing_path.exists() else {}
    previous_elapsed = previous.get("elapsed_wall_seconds", 0.0)
    timings = previous.get("groups", [])
    stores, completed = {}, {}
    for seed in config["seeds"]:
        seed_dir = run_dir / f"seed_{seed}"
        seed_dir.mkdir(exist_ok=True)
        stores[seed] = GroupStore(seed_dir)
        _, completed[seed] = stores[seed].recover()
    jobs = planned_jobs(config, windows, plan)
    expected = {(seed, *window_key(window), "single", step) for seed, _, window, step in jobs}
    actual = {(seed, *key) for seed, keys in completed.items() for key in keys}
    if not actual.issubset(expected):
        raise ValueError("Execution plan would exclude committed groups; keep them in the selected scope")
    if plan is not None and saved_plan is None:
        if timing_path.exists():
            save_json(run_dir / "progress_before_execution_plan.json", previous)
        save_json(plan_path, plan)
    todo = [(seed, case, window, step) for seed, case, window, step in jobs
            if (*window_key(window), "single", step) not in completed[seed]]

    def progress(status, message=""):
        save_json(timing_path, {
            "status": status, "message": message,
            "elapsed_wall_seconds": previous_elapsed + time.monotonic() - started,
            "completed_groups": sum(len(keys) for keys in completed.values()),
            "planned_groups": len(jobs), "groups": timings,
            "pid": os.getpid(), "max_wall_seconds": wall_budget,
            "execution_plan": "execution_plan.json" if plan else None,
        })

    if not todo:
        progress("complete", "All approved groups already committed; no inference")
        return run_dir
    if previous_elapsed >= wall_budget:
        progress("budget_stopped", "Budget exhausted; request approval before more inference")
        return run_dir
    progress("loading_model")
    try:
        model, tokenizer, chronos_config = load_chronos_t5_raw(config["model_id"], device="cpu")
        if getattr(model.config, "_commit_hash", None) != config["model_revision"]:
            raise ValueError("Cached model revision differs from the approved revision")
        options = {}
        for seed in config["seeds"]:
            args = SimpleNamespace(trajectory_metrics=True, save_trajectories=True,
                                   sampling_seed=seed, model_id=config["model_id"],
                                   temperature=config["temperature"], sample_top_k=config["sample_top_k"])
            options[seed] = trajectory_options_from_args(args, run_dir / f"seed_{seed}", model, chronos_config)
            options[seed]["provenance"]["cpu_threads"] = config["cpu_threads"]
            if plan:
                options[seed]["provenance"]["execution_plan_sha256"] = hashlib.sha256(plan_path.read_bytes()).hexdigest()
        for index, (seed, case, window, step) in enumerate(todo):
            elapsed = previous_elapsed + time.monotonic() - started
            remaining_work = sum(work_units(config, c, b) for _, c, _, b in todo[index:])
            unit_cost = max((t["seconds"] / t["work_units"] for t in timings), default=0.0)
            projected = elapsed + config["timing_safety_factor"] * unit_cost * remaining_work
            if elapsed >= wall_budget or projected > wall_budget:
                progress("budget_stopped", f"Conservative total estimate {projected:.0f}s exceeds budget")
                print(f"Stopped with checkpoints: estimated total {projected:.0f}s", flush=True)
                return run_dir
            print(f"Group {sum(map(len, completed.values()))+1}/{len(jobs)}: seed={seed} "
                  f"{window.dataset_name}/{window.series_id} w={window.window_id} b={step} "
                  f"K={case['top_k']} N={config['num_samples']}", flush=True)
            group_started = time.monotonic()
            progress("running", f"seed={seed} {window.dataset_name}/{window.series_id} w={window.window_id} b={step}")

            def commit(steps, summary, *_):
                key = stores[seed].commit(steps, summary)
                completed[seed].add(key)

            scan_window(model, tokenizer, chronos_config, window, branch_steps=[step],
                        branch_modes=["single"], top_k=case["top_k"], num_samples=config["num_samples"],
                        temperature=config["temperature"], sample_top_k=config["sample_top_k"],
                        show_progress=True, checkpoint_callback=commit, trajectory_options=options[seed])
            seconds = time.monotonic() - group_started
            timings.append({"seed": seed, "dataset_name": window.dataset_name, "series_id": window.series_id,
                            "window_id": window.window_id, "branch_step": step,
                            "seconds": seconds, "work_units": work_units(config, case, step)})
            progress("running")
            print(f"Committed in {seconds:.1f}s; elapsed {previous_elapsed + time.monotonic()-started:.1f}s", flush=True)
        progress("complete")
    except BaseException as error:
        progress("interrupted", f"{type(error).__name__}: {error}")
        raise
    return run_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Defaults to the saved config on resume, otherwise the approved phase2.json.")
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--execution-plan", type=Path, help="Explicit subset and revised execution budget; original science config stays immutable.")
    args = parser.parse_args()
    config_path = args.config or (args.resume_from / "config.json" if args.resume_from else ROOT / "configs/chronos_controlled_pilot/phase2.json")
    directory = run(config_path, args.resume_from, args.execution_plan)
    state = json.loads((directory / "progress.json").read_text(encoding="utf-8"))
    if state["status"] == "complete":
        import subprocess
        save_json(directory / "analysis_status.json", {"status": "running"})
        try:
            subprocess.run([sys.executable, str(ROOT / "scripts/viz/analyze_chronos_controlled_pilot.py"), str(directory)], check=True)
        except BaseException as error:
            save_json(directory / "analysis_status.json", {"status": "failed", "error": str(error)})
            raise
        save_json(directory / "analysis_status.json", {"status": "complete"})
