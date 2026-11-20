"""The explicitly authorized six-series/ten-cell local pilot, never a campaign.

Prepare freezes selection without model inference. Execute validates the first
two different-series cells before proceeding. STOP_REQUESTED pauses between
durable ensembles; deleting that researcher-created request permits resume.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code/chronos_fpa"))
import bootstrap  # noqa: E402,F401
from run_chronos_microbenchmark import jsonable, memory_usage, write_json


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=ROOT,
                                   text=True, encoding="utf-8")


def utc():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cell_plan(panel):
    from chronos_exploratory import POLICY_VERSION
    from ensemble_store import task_id
    config = panel["config"]
    windows = panel["windows"]
    calibration = [w for w in windows if w["stratum"] == "representative" and w["dataset_id"] in {"m4_daily", "ercot"}]
    first = calibration
    order = first + [w for w in windows if w not in first]
    cells = []
    for window, seed, primary in ([(w, config["primary_seed"], True) for w in order] +
                                  [(w, s, False) for s in config["replication_seeds"] for w in calibration]):
        scope = {k: window[k] for k in ("dataset_id", "series_id", "forecast_origin", "context_sha256")}
        scope.update(model_revision=config["model_revision"], grid_revision=panel["grid_revision"],
                     policy=POLICY_VERSION, sampling_seed=seed)
        cells.append({"scope": scope, "cell_id": task_id(scope), "window_id": window["window_id"],
                      "primary": primary, "stratum": window["stratum"]})
    if len(cells) != 10 or len({c["cell_id"] for c in cells}) != 10:
        raise ValueError("This driver only accepts six primary plus four calibration cells")
    return cells


def prepare(output, config_path):
    import numpy as np
    import torch
    from chronos_pilot_selection import select_panel
    from ensemble_store import task_id
    from huggingface_hub import snapshot_download
    output.mkdir(parents=True, exist_ok=True)
    if (output / "frozen.json").exists():
        verify_freeze(output)
        print("Existing selection/source freeze verified; no selection repeated.", flush=True)
        return
    config = load(config_path)
    panel, contexts = select_panel(ROOT, config)
    write_json(output / "selection_manifest.json", {**panel, "frozen_utc": utc(), "model_draws_before_freeze": 0})
    context_path = output / "selected_contexts.npz"
    with context_path.open("xb") as stream:
        np.savez_compressed(stream, **contexts)
        stream.flush()
        os.fsync(stream.fileno())
    write_json(output / "cell_plan.json", cell_plan(panel))
    # All access is offline. Missing cache is a blocker, never a download.
    cached = Path(snapshot_download(config["model_id"], revision=config["model_revision"], local_files_only=True))
    weights = {p.name: {"path": str(p), "sha256": digest(p), "bytes": p.stat().st_size}
               for p in sorted(cached.iterdir()) if p.is_file()}
    write_json(output / "model_cache.json", {"snapshot": str(cached), "files": weights})
    source_paths = sorted((ROOT / "code/chronos_fpa").rglob("*.py")) + [
        Path(__file__).resolve(), ROOT / "scripts/runs/run_chronos_microbenchmark.py", config_path.resolve()]
    hashes = {}
    for path in source_paths:
        name = path.relative_to(ROOT).as_posix()
        hashes[name] = digest(path)
        destination = output / "source_at_collection" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    write_json(output / "source_manifest.json", {"hashes": hashes, "source_digest": task_id(hashes)})
    write_json(output / "environment.json", {
        "observed_utc": utc(), "python": sys.version, "executable": sys.executable,
        "platform": platform.platform(), "logical_cpus": os.cpu_count(),
        "cuda_available": torch.cuda.is_available(),
        "cuda_devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
        "xpu_available": bool(hasattr(torch, "xpu") and torch.xpu.is_available()),
        "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "memory": memory_usage(), "disk_free_bytes": shutil.disk_usage(output).free,
        "git_branch": git("branch", "--show-current").strip(), "git_head": git("rev-parse", "HEAD").strip(),
        "git_status_before_collection": git("status", "--short"), "gitignore_sha256": digest(ROOT / ".gitignore"),
        "git_index_sha256": digest(ROOT / ".git/index"),
        "network": "HF_HUB_OFFLINE=1, HF_DATASETS_OFFLINE=1, TRANSFORMERS_OFFLINE=1; local_files_only=True"})
    frozen_names = ["selection_manifest.json", "selected_contexts.npz", "cell_plan.json", "source_manifest.json", "environment.json", "model_cache.json"]
    write_json(output / "frozen.json", {"schema": "chronos_pilot_freeze_v1", "frozen_utc": utc(),
                                        "files": {n: digest(output / n) for n in frozen_names}})
    print(json.dumps({"frozen": True, "windows": [(w["dataset_id"], w["series_id"], w["stratum"]) for w in panel["windows"]]}), flush=True)


def verify_freeze(output):
    frozen = load(output / "frozen.json")
    for name, expected in frozen["files"].items():
        if digest(output / name) != expected:
            raise ValueError(f"Frozen input changed: {name}")
    for name, expected in load(output / "source_manifest.json")["hashes"].items():
        if digest(ROOT / name) != expected or digest(output / "source_at_collection" / name) != expected:
            raise ValueError(f"Collection source changed after freeze: {name}")
    for name, expected in load(output / "selection_manifest.json")["source_hashes"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Source dataset changed: {name}")
    return load(output / "selection_manifest.json")


def compare_policy(actual, expected, config, label):
    import torch
    from chronos_exploratory import policy_probabilities
    actual, expected = actual.cpu(), expected.cpu()
    q, other = policy_probabilities(actual, config), policy_probabilities(expected, config)
    row = {"label": label, "logit_abs_max": float((actual - expected).abs().max()),
           "q50_abs_max": float((q - other).abs().max()),
           "logits_close": bool(torch.allclose(actual, expected, atol=1e-5, rtol=1e-4)),
           "q50_close": bool(torch.allclose(q, other, atol=1e-6, rtol=1e-4)),
           "same_support": bool(torch.equal(q > 0, other > 0))}
    if not all(row[k] for k in ("logits_close", "q50_close", "same_support")):
        raise ValueError(f"Decoder correctness gate failed: {row}")
    return row


def capture_paths(output, directory, cell, engine, tokenizer, scale, results, validation, parity):
    import numpy as np
    import torch
    from chronos_decoding import decode_token_samples_to_values
    from ensemble_store import EnsembleStore
    capture_store = EnsembleStore(directory / "captures")
    chosen = []
    for b in (0, 9):
        fork = results["forks"][b]
        roles = [("reference", fork["greedy_token"])]
        if len(fork["selected_tokens"]) > 1:
            roles.append(("alternative", fork["selected_tokens"][1]))
        for role, token in roles:
            manifest, arrays = validation["lookup"][(b, role, token)]
            for i in range(2):
                chosen.append(({"b": b, "role": role, "token": token, "path_index": i,
                                "source_task_id": manifest["task_id"]}, arrays["tokens"][i]))
    profiles = []
    shared_id = None
    # Release full tensors after each small batch. No encoder duplication on disk.
    for begin in range(0, len(chosen), 2):
        selected = chosen[begin:begin + 2]
        identities, tokens = [r[0] for r in selected], np.stack([r[1] for r in selected])
        started = time.perf_counter()
        plain, _ = engine.replay(tokens)
        logits, arrays = engine.replay(tokens, capture=True)
        parity.append(compare_policy(logits, plain, engine.config, f"capture_batch_{begin // 2}"))
        if shared_id is None:
            static = {k: v for k, v in arrays.items() if k.startswith("encoder_")}
            static.update(tokens=tokens, values=decode_token_samples_to_values(tokenizer, torch.from_numpy(tokens), scale).numpy(),
                          encoder_input_ids=engine.input_ids.cpu().numpy(), encoder_attention_mask=engine.attention_mask.cpu().numpy(),
                          token_embedding=engine.model.get_input_embeddings().weight.detach().cpu().numpy(),
                          value_token_ids=np.arange(engine.config.n_special_tokens, engine.config.n_tokens, dtype=np.int64),
                          decoded_value_bins=np.array([tokenizer.token_to_value(i, scale) for i in range(engine.config.n_special_tokens, engine.config.n_tokens)], dtype=np.float32))
            manifest, _ = capture_store.put({**cell["scope"], "capture": "shared_encoder"}, static,
                                             {"all_layers_all_heads": True, "raw_bytes": sum(a.nbytes for a in static.values())})
            shared_id = manifest["task_id"]
            del static
        arrays = {k: a for k, a in arrays.items() if not k.startswith("encoder_")}
        arrays.update(tokens=tokens, values=decode_token_samples_to_values(tokenizer, torch.from_numpy(tokens), scale).numpy(), logits=logits.numpy())
        metadata = {"source_paths": identities, "shared_encoder_task_id": shared_id, "all_layers_heads_queries": True,
                    "query_alignment": "query t predicts token t from start + tokens[:t]; query b before forced token; b+1 after",
                    "fields": sorted(arrays), "raw_bytes": sum(a.nbytes for a in arrays.values()),
                    "shapes": {k: list(a.shape) for k, a in arrays.items()}, "dtype": "float32 activations/int64 tokens"}
        manifest, _ = capture_store.put({**cell["scope"], "capture": "full_all_steps", "batch": begin // 2}, arrays, metadata)
        profiles.append({**metadata, "task_id": manifest["task_id"], "seconds": time.perf_counter() - started})
        del arrays, logits, plain
    write_json(directory / "capture_summary.json", {"selected_paths": len(chosen), "new_stochastic_paths": 0,
               "shared_encoder_task_id": shared_id, "profiles": profiles,
               "all_other_paths": "full tokens/values and replay metadata; hidden/attention/logit arrays omitted"})


def worker(output, index):
    import numpy as np
    import torch
    from chronos_decoding import decode_token_samples_to_values
    from chronos_exploratory import CachedDecoder, policy_probabilities
    from chronos_exploratory_window import collect_window
    from chronos_io import load_chronos_t5_raw
    from chronos_pilot_validation import read_complete_cell, validate_cell
    from ensemble_store import isolated_window_store
    panel = verify_freeze(output)
    config = panel["config"]
    cell = load(output / "cell_plan.json")[index]
    store = isolated_window_store(output, cell["scope"])
    directory = store.directory.parent
    if (directory / "complete.json").exists():
        read_complete_cell(directory, cell["scope"])
        print("Completed cell reused without loading a model", flush=True)
        return
    with np.load(output / "selected_contexts.npz", allow_pickle=False) as archive:
        context = archive[cell["window_id"]].copy()
    device = "cuda" if torch.cuda.is_available() else "xpu" if hasattr(torch, "xpu") and torch.xpu.is_available() else "cpu"
    torch.set_num_interop_threads(1)
    torch.set_num_threads(1)
    started = time.perf_counter()
    model, tokenizer, model_config = load_chronos_t5_raw(config["model_id"], device=device, dtype="float32",
        revision=config["model_revision"], local_files_only=True, attn_implementation="eager")
    load_seconds = time.perf_counter() - started
    ids, mask, scale = tokenizer.context_input_transform(torch.from_numpy(context)[None].to(device))
    if not (output / "hardware_profile.json").exists():
        measurements = []
        for threads in (1, 2, 4):
            torch.set_num_threads(threads)
            begin = time.perf_counter()
            engine = CachedDecoder(model, model_config, ids, mask)
            greedy = engine.greedy(32)
            engine.replay(greedy[None].repeat(8, 1))
            if device == "cuda":
                torch.cuda.synchronize()
            measurements.append({"threads": threads, "seconds": time.perf_counter() - begin})
            del engine
        threads = min(measurements, key=lambda r: r["seconds"])["threads"]
        write_json(output / "hardware_profile.json", {"device": device, "chosen_threads": threads,
                    "deterministic_greedy_no_stochastic_paths": True, "measurements": measurements})
    else:
        profile = load(output / "hardware_profile.json")
        if profile["device"] != device:
            raise ValueError("Hardware backend changed after profiling")
        threads = profile["chosen_threads"]
    torch.set_num_threads(threads)
    engine = CachedDecoder(model, model_config, ids, mask)
    greedy = engine.greedy(32)
    replay, _ = engine.replay(greedy[None])
    parity = [compare_policy(engine.prefix_state(greedy[:t].tolist()).logits, replay[:, t], model_config, f"greedy_prefix_{t}") for t in range(32)]
    # Independently recompute encoder + full decoder at the two sentinel forks.
    with torch.no_grad():
        for b in (0, 9):
            q = policy_probabilities(engine.prefix_state(greedy[:b].tolist()).logits, model_config)[0]
            alternate = int(next(i for i in torch.argsort(q, descending=True, stable=True) if int(i) != int(greedy[b])))
            prefix = greedy[:b].tolist() + [alternate]
            direct = model(input_ids=ids.to(device), attention_mask=mask.to(device),
                           decoder_input_ids=torch.tensor([[engine.start_id] + prefix], device=device), use_cache=False).logits[:, -1]
            parity.append(compare_policy(engine.prefix_state(prefix).logits, direct, model_config, f"independent_encoder_alternative_b{b}"))
    print(f"Cell {index + 1}/10 {cell['scope']['dataset_id']}/{cell['scope']['series_id']} seed={cell['scope']['sampling_seed']}; parity passed; collecting", flush=True)
    provenance = {**cell["scope"], "window_id": cell["window_id"], "experiment": output.name,
                  "model_id": config["model_id"], "source_digest": load(output / "source_manifest.json")["source_digest"],
                  "environment_sha256": digest(output / "environment.json"),
                  "git_head": load(output / "environment.json")["git_head"], "device": device,
                  "dtype": "float32", "attention_backend": "eager", "cpu_threads": threads,
                  "tokenizer_scale": float(scale.reshape(-1)[0])}
    def progress(row):
        write_json(output / "progress.json", {"utc": utc(), "cell_index": index, "cell_id": cell["cell_id"], **row})
        if (output / "STOP_REQUESTED").exists():
            raise InterruptedError("Researcher STOP_REQUESTED: durable ensembles preserved")
    begin = time.perf_counter()
    results = collect_window(engine, tokenizer, scale, context, store, provenance, seed=cell["scope"]["sampling_seed"],
                             samples_per_group=20, direct_samples=60, batch_size=8, progress=progress)
    collection_seconds = time.perf_counter() - begin
    write_json(directory / "results.json", results)
    # Exact raw local logits preserve p_sel and q50 reconstruction at every fork.
    fork_logits = np.stack([engine.prefix_state(greedy[:b].tolist()).logits.cpu().numpy()[0] for b in range(10)])
    with (directory / "fork_logits.npz").open("wb") as stream:
        np.savez_compressed(stream, logits=fork_logits)
        stream.flush()
        os.fsync(stream.fileno())
    validation = validate_cell(directory, cell["scope"], jsonable(results))
    for manifest, arrays in validation["records"]:
        decoded = decode_token_samples_to_values(tokenizer, torch.from_numpy(arrays["tokens"]), scale).numpy()
        np.testing.assert_array_equal(arrays["values"], decoded)
    # Sampled-prefix parity on eight outcome-independent paths, primary and calibration.
    chosen = []
    for b in (0, 9):
        fork = results["forks"][b]
        for token in fork["selected_tokens"][:2]:
            role = "reference" if token == fork["greedy_token"] else "alternative"
            chosen.extend(validation["lookup"][(b, role, token)][1]["tokens"][:2])
    for i, tokens in enumerate(chosen):
        plain, _ = engine.replay(tokens[None])
        for t in range(32):
            parity.append(compare_policy(engine.prefix_state(tokens[:t].tolist()).logits, plain[:, t], model_config, f"saved_path_{i}_prefix_{t}"))
    # Drop sampled-prefix caches before capture; deterministic greedy states rebuilt as needed.
    engine.states.clear()
    if cell["primary"]:
        capture_paths(output, directory, cell, engine, tokenizer, scale, results, validation, parity)
    else:
        write_json(directory / "capture_summary.json", {"selected_paths": 0, "new_stochastic_paths": 0,
                   "all_paths": "full tokens/values retained; exhaustive activations reconstructable from pinned replay"})
    write_json(directory / "parity.json", parity)
    write_json(directory / "timing.json", {"model_load_seconds": load_seconds, "collection_seconds": collection_seconds,
               "worker_seconds": time.perf_counter() - started, "encoder_calls": engine.encoder_calls,
               "decoder_calls": engine.decoder_calls, "device": device, "cpu_threads": threads})
    files = ["results.json", "fork_logits.npz", "parity.json", "capture_summary.json", "timing.json"]
    for path in (directory / "captures").rglob("*") if (directory / "captures").exists() else []:
        if path.is_file():
            files.append(path.relative_to(directory).as_posix())
    marker = {"schema": "chronos_pilot_complete_cell_v1", "status": "complete", "completed_utc": utc(),
              "scope": cell["scope"], "primary": cell["primary"], "files": {n: digest(directory / n) for n in files},
              "validation": {k: v for k, v in validation.items() if k not in {"records", "lookup", "groups_by_position"}}}
    write_json(directory / "complete.json", marker)
    read_complete_cell(directory, cell["scope"])
    print(f"Cell {index + 1} validated: {validation['ensembles']} ensembles / {validation['paths']} paths", flush=True)


def execute(output):
    from chronos_pilot_validation import read_complete_cell
    from windows_job import WindowsJobProcess
    verify_freeze(output)
    cells = load(output / "cell_plan.json")
    if (output / "STOP_REQUESTED").exists():
        raise InterruptedError("STOP_REQUESTED exists; no model started")
    for index, cell in enumerate(cells):
        directory = output / "cells" / cell["cell_id"]
        if (directory / "complete.json").exists():
            read_complete_cell(directory, cell["scope"])
            print(f"Cell {index + 1}/10 already complete; verified, not rerun", flush=True)
        else:
            attempts = output / "attempts"
            attempts.mkdir(exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            stem = f"cell{index:02d}_{stamp}"
            environment = dict(os.environ, HF_HUB_OFFLINE="1", HF_DATASETS_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                               HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false", PYTHONUNBUFFERED="1", GIT_OPTIONAL_LOCKS="0")
            command = [sys.executable, str(Path(__file__).resolve()), "--output", str(output), "--worker", str(index)]
            samples = []
            begin = time.perf_counter()
            with (attempts / (stem + ".log")).open("wb") as log:
                process = WindowsJobProcess(command, ROOT, environment, log, memory_limit=None)
                try:
                    while process.poll() is None:
                        row = {"utc": utc(), "elapsed_seconds": time.perf_counter() - begin,
                               "peak_job_committed_bytes": process.peak_job_memory(), **memory_usage(),
                               "disk_free_bytes": shutil.disk_usage(output).free}
                        samples.append(row)
                        write_json(output / "resources_live.json", {"cell_index": index, **row})
                        time.sleep(1)
                    exit_code = process.wait()
                    peak = process.peak_job_memory()
                except BaseException:
                    process.kill()
                    process.wait()
                    raise
                finally:
                    write_json(attempts / (stem + ".json"), {"cell_index": index, "cell_id": cell["cell_id"],
                               "elapsed_seconds": time.perf_counter() - begin, "exit_code": process.returncode,
                               "peak_job_committed_bytes": process.peak_job_memory(), "samples": samples,
                               "limits": "no inherited time/CPU/memory cap; native kill-on-supervisor-close containment"})
                    process.close()
            if exit_code != 0:
                raise RuntimeError(f"Correctness/execution gate stopped at cell {index + 1}; inspect {attempts / (stem + '.log')}; exit={exit_code}")
            read_complete_cell(directory, cell["scope"])
            print(f"Cell {index + 1}/10 complete and independently validated; process-tree peak={peak} bytes", flush=True)
        if index == 1:
            if (cells[0]["scope"]["dataset_id"], cells[0]["scope"]["series_id"]) == (cells[1]["scope"]["dataset_id"], cells[1]["scope"]["series_id"]):
                raise ValueError("Initial gate needs distinct original series")
            if not (output / "first_two_gate.json").exists():
                write_json(output / "first_two_gate.json", {"status": "passed", "validated_utc": utc(),
                           "complete_sha256": {c["cell_id"]: digest(output / "cells" / c["cell_id"] / "complete.json") for c in cells[:2]}})
            print("First two different-series windows passed; remaining authorized cells may proceed", flush=True)
    if not (output / "pilot_complete.json").exists():
        write_json(output / "pilot_complete.json", {"status": "complete", "completed_utc": utc(), "cells": len(cells),
                   "original_series": 6, "complete_sha256": {c["cell_id"]: digest(output / "cells" / c["cell_id"] / "complete.json") for c in cells},
                   "stopping_gate": "STOP for scientific review after analysis; no larger campaign authorized"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/chronos_local_pilot/pilot_v1.json")
    parser.add_argument("--prepare", action="store_true", help="Offline data selection and freeze only")
    parser.add_argument("--execute", action="store_true", help="Execute/resume the authorized ten-cell plan")
    parser.add_argument("--worker", type=int, choices=range(10), help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / "result").resolve()):
        raise ValueError("Output must stay under repository result/")
    try:
        if args.worker is not None:
            worker(output, args.worker)
        elif args.prepare:
            prepare(output, args.config)
        elif args.execute:
            execute(output)
        else:
            parser.error("Choose --prepare or --execute")
    except BaseException:
        if output.exists():
            write_json(output / ("worker_failure.json" if args.worker is not None else "supervisor_failure.json"),
                       {"utc": utc(), "traceback": traceback.format_exc(), "new_inference_halted": True})
        raise


if __name__ == "__main__":
    main()
