"""Bounded, local-only Prompt-2 benchmark with a supervising process deadline."""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code/chronos_fpa"))
import bootstrap  # noqa: E402,F401


def jsonable(value):
    if hasattr(value, "tolist"):
        return jsonable(value.tolist())
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    if isinstance(value, float) and not __import__("math").isfinite(value):
        return None
    return value


def write_json(path, value):
    # Supervisor stays dependency-free: no Torch/model import before deadline starts.
    path = Path(path)
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(jsonable(value), stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    for attempt in range(9):
        try:
            temporary.replace(path)
            break
        except PermissionError as error:
            if getattr(error, "winerror", None) not in {5, 32, 33} or attempt == 8:
                error.add_note(f"Complete metadata temporary preserved: {temporary}")
                raise
            time.sleep(min(.125 * 2 ** attempt, 2.))


def memory_usage():
    if os.name != "nt":
        raise RuntimeError("This benchmark resource supervisor is validated for native Windows only")
    from ctypes import wintypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
            (name, ctypes.c_ulonglong) for name in ("total", "available", "total_page", "available_page", "total_virtual", "available_virtual", "extended")]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError()
    return {"system_free_bytes": status.available}


def start_model_process(command, output_root, environment, log, memory_limit):
    from windows_job import WindowsJobProcess
    return WindowsJobProcess(command, output_root, environment, log, memory_limit)


def supervise(config_path, output, replay_only=False, n20=False):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output = output.resolve()
    if not output.is_relative_to((ROOT / "result").resolve()):
        raise ValueError("Benchmark output must remain under this repository's result directory")
    output.mkdir(parents=True, exist_ok=True)
    target_summary = ("n20_" if n20 else "") + ("resource_replay.json" if replay_only else "summary.json")
    if (output / target_summary).exists():
        print("Existing completed benchmark preserved; no model launched.", flush=True)
        return 0
    ledger = output / "budget.json"
    previous = json.loads(ledger.read_text()) if ledger.exists() else {"spent_model_seconds": 0.}
    if "peak_working_set_bytes" in previous:
        previous["superseded_redirector_peak_invalid_bytes"] = previous.pop("peak_working_set_bytes")
    if previous.get("status") == "running":
        raise RuntimeError("A previous model reservation is unresolved; refusing another process")
    remaining = config["model_wall_seconds"] - previous["spent_model_seconds"]
    started_utc = datetime.fromisoformat(config["task_started_utc"].replace("Z", "+00:00"))
    task_remaining = config["task_wall_seconds"] - (datetime.now(timezone.utc) - started_utc).total_seconds()
    ceiling = min(remaining, task_remaining)
    if ceiling <= 0:
        raise RuntimeError("Approved model or task budget exhausted")
    if memory_usage()["system_free_bytes"] < max(config["minimum_system_free_bytes"], 1024 ** 3):
        raise RuntimeError("Less than 1 GiB system RAM free before model loading")
    environment = {**os.environ, "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
                   "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
                   "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "GIT_OPTIONAL_LOCKS": "0"}
    ledger_data = {**previous, "status": "running", "reserved_seconds": ceiling,
                   "started_utc": datetime.now(timezone.utc).isoformat(),
                   "monitor_version": "native_windows_job_v1"}
    write_json(ledger, ledger_data)
    command = [sys.executable, str(Path(__file__).resolve()), "--config", str(config_path),
               "--output", str(output), "--worker"]
    if replay_only:
        command.append("--resource-replay")
    if n20:
        command.append("--n20-validation")
    started, last_print = time.monotonic(), -10.
    peak, disk_peak, reason = 0, 0, None
    with (output / "worker.log").open("a", encoding="utf-8") as log:
        process = start_model_process(command, ROOT, environment, log, config["max_process_bytes"])
        try:
            while process.poll() is None:
                elapsed = time.monotonic() - started
                usage = memory_usage()
                disk = 0
                for path in output.rglob("*"):
                    try:
                        if path.is_file():
                            disk += path.stat().st_size
                    except FileNotFoundError:
                        pass  # An atomically published temporary may disappear during enumeration.
                peak, disk_peak = max(peak, process.peak_job_memory()), max(disk_peak, disk)
                if elapsed >= ceiling:
                    reason = "hard_model_or_task_deadline"
                elif peak > config["max_process_bytes"]:
                    reason = "process_memory_ceiling"
                elif usage["system_free_bytes"] < config["minimum_system_free_bytes"]:
                    reason = "system_memory_floor"
                elif disk > config["max_output_bytes"]:
                    reason = "output_storage_ceiling"
                if reason:
                    process.kill()
                    break
                if elapsed - last_print >= 10:
                    print(f"Model work {elapsed:.0f}/{ceiling:.0f}s; job peak committed {peak / 1024**2:.0f} MiB; outputs {disk / 1024**2:.1f} MiB", flush=True)
                    last_print = elapsed
                time.sleep(.5)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            peak = max(peak, process.peak_job_memory())
            elapsed = time.monotonic() - started
            write_json(ledger, {**ledger_data, "status": "stopped" if reason else "finished",
                               "spent_model_seconds": previous["spent_model_seconds"] + elapsed,
                               "last_process_seconds": elapsed, "exit_code": process.returncode,
                               "stop_reason": reason, "last_job_peak_committed_bytes": peak,
                               "peak_job_committed_bytes": max(peak, previous.get("peak_job_committed_bytes", 0)),
                               "peak_output_bytes": disk_peak})
            attempt_path = output / ("supervision_" + ("n20_" if n20 else "") + ("replay" if replay_only else "collection") + ".json")
            if not attempt_path.exists():
                write_json(attempt_path, json.loads(ledger.read_text()))
            process.close()
    print(json.dumps(json.loads(ledger.read_text()), indent=2), flush=True)
    return 2 if reason else process.returncode


def worker(config_path, output):
    import importlib.metadata
    import numpy as np
    import torch
    from chronos_io import load_chronos_t5_raw
    from chronos_decoding import _mask_to_chronos_value_tokens, decode_tokens_manual, decode_token_samples_to_values
    from chronos_exploratory import CachedDecoder, POLICY_VERSION, policy_probabilities, select_candidates
    from chronos_exploratory_window import collect_window
    from ensemble_store import EnsembleStore, read_snapshot

    config = json.loads(config_path.read_text(encoding="utf-8"))
    torch.set_num_threads(config["cpu_threads"])
    torch.set_num_interop_threads(config["cpu_threads"])
    context = None
    data_path = ROOT / config["context_path"]
    with data_path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if str(row["series_id"]) == config["series_id"]:
                context = np.asarray(row["target"][:512], dtype=np.float32)
                break
    if context is None or hashlib.sha256(context.tobytes()).hexdigest() != config["context_sha256"]:
        raise ValueError("The approved local C512 context/hash is unavailable")
    source_files = sorted((ROOT / "code/chronos_fpa").rglob("*.py")) + [Path(__file__).resolve()]
    source_hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    source_digest = hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest()
    provenance = {"experiment": output.name, "model_id": config["model_id"], "model_revision": config["model_revision"],
                  "device": config["device"], "dtype": config["dtype"], "backend": config["attn_implementation"],
                  "source_digest": source_digest, "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()}
    print("Loading pinned cached model with local_files_only=True", flush=True)
    started = time.perf_counter()
    model, tokenizer, chronos_config = load_chronos_t5_raw(
        config["model_id"], device="cpu", dtype="float32", revision=config["model_revision"],
        local_files_only=True, attn_implementation=config["attn_implementation"])
    load_seconds = time.perf_counter() - started
    ids, mask, scale = tokenizer.context_input_transform(torch.from_numpy(context.copy())[None])
    engine = CachedDecoder(model, chronos_config, ids, mask)
    print("Checking greedy paths, all-prefix logits/q50 and all-layer replay before stochastic sampling", flush=True)
    started = time.perf_counter()
    greedy = decode_tokens_manual(model, chronos_config, ids, mask, 32, do_sample=False, show_progress=False)[0]
    optimized = engine.greedy(32)
    if not torch.equal(greedy, optimized):
        raise ValueError("Cached/reference greedy paths differ")
    parity = []

    def compare(logits, reference, label):
        q, expected = policy_probabilities(logits, chronos_config), policy_probabilities(reference, chronos_config)
        row = {"label": label, "max_logit_abs_error": float((logits - reference).abs().max()),
               "max_q50_abs_error": float((q - expected).abs().max()),
               "same_q50_support": bool(torch.equal(q > 0, expected > 0)),
               "logits_close": bool(torch.allclose(logits, reference, atol=1e-5, rtol=1e-4)),
               "q50_close": bool(torch.allclose(q, expected, atol=1e-6, rtol=1e-4))}
        parity.append(row)
        if not all(row[k] for k in ("same_q50_support", "logits_close", "q50_close")):
            write_json(output / "parity.json", parity)
            raise ValueError(f"Policy parity failed: {row}")

    with torch.no_grad():
        for t in range(32):
            prefix = greedy[:t].tolist()
            reference = model(input_ids=ids, attention_mask=mask,
                              decoder_input_ids=torch.tensor([[engine.start_id] + prefix]), use_cache=False).logits[:, -1]
            compare(engine.prefix_state(prefix).logits, reference, f"greedy_prefix_{t}")
        for b in (0, 9):
            prefix = greedy[:b].tolist()
            alternatives = _mask_to_chronos_value_tokens(engine.prefix_state(prefix).logits, chronos_config).argsort(descending=True)[0]
            alternative = int(next(t for t in alternatives if int(t) != int(greedy[b])))
            changed = prefix + [alternative] + greedy[b + 1:b + 3].tolist()
            reference = model(input_ids=ids, attention_mask=mask,
                              decoder_input_ids=torch.tensor([[engine.start_id] + changed]), use_cache=False).logits[:, -1]
            compare(engine.prefix_state(changed).logits, reference, f"alternative_prefix_b{b}")
    plain, _ = engine.replay(greedy[None])
    captured, first_capture = engine.replay(greedy[None], capture=True)
    compare(captured, plain, "full_greedy_replay_with_all_capture")
    parity_seconds = time.perf_counter() - started
    write_json(output / "parity.json", parity)
    print("Parity passed; timing reference/encoder reuse/KV and batch sizes", flush=True)
    timings = []
    timing_store = EnsembleStore(output / "timing_samples")

    def timed(label, function, paths):
        identity = {**provenance, "timing_variant": label, "sample_count": paths}
        previous = timing_store.get(identity)
        if previous is not None:
            manifest, arrays = previous
            timings.append({**manifest["metadata"], "reused": True})
            return torch.from_numpy(arrays["tokens"].copy())
        begin = time.perf_counter()
        result = function()
        row = {"variant": label, "seconds": time.perf_counter() - begin, "paths": paths, "horizon": 32, "b": 0}
        timing_store.put(identity, {"tokens": result.numpy(),
                                   "values": decode_token_samples_to_values(tokenizer, result, scale).numpy(),
                                   "context": context, "greedy_tokens": greedy.numpy()}, row)
        timings.append({**row, "reused": False})
        return result

    prefix = [int(greedy[0])]
    base = timed("reference_no_encoder_or_KV_reuse_N2", lambda: decode_tokens_manual(
        model, chronos_config, ids, mask, 32, num_samples=2, forced_prefix_tokens=prefix,
        top_k=50, temperature=1., generator=torch.Generator().manual_seed(config["seed"]), show_progress=False), 2)
    encoder_only = timed("encoder_reuse_only_N2", lambda: engine.sample_encoder_only(
        prefix, 32, 2, torch.Generator().manual_seed(config["seed"])), 2)
    cached = timed("encoder_and_KV_reuse_N2", lambda: engine.sample(
        prefix, 32, 2, torch.Generator().manual_seed(config["seed"])), 2)
    for batch in (1, 2, 4, 8):
        timed(f"cached_N8_batch{batch}", lambda batch=batch: engine.sample(
            prefix, 32, 8, torch.Generator().manual_seed(config["seed"] + 1), batch_size=batch), 8)
    timed("cached_N20_reference_batch8", lambda: engine.sample(
        prefix, 32, 20, torch.Generator().manual_seed(config["seed"] + 2), batch_size=8), 20)
    root_q = policy_probabilities(engine.prefix_state([]).logits, chronos_config)[0]
    root_candidates = select_candidates(root_q, int(greedy[0]))
    if root_candidates.residual_mass > 0:
        timed("cached_N20_residual", lambda: engine.sample_residual(
            [], root_q, root_candidates, 32, 20, torch.Generator().manual_seed(config["seed"] + 3)), 20)
    print("Collecting one dense micro window: N2 branch groups, direct N60 and overlap calibration", flush=True)
    store = EnsembleStore(output / "ensembles")
    window_started = time.perf_counter()
    window = collect_window(engine, tokenizer, scale, context, store, provenance,
                            samples_per_group=config["micro_samples_per_group"], direct_samples=config["direct_samples"],
                            seed=config["seed"], batch_size=config["batch_size"], overlap_positions=config["overlap_positions"])
    window_seconds = time.perf_counter() - window_started
    write_json(output / "window_results.json", window)
    snapshot = read_snapshot(output / "ensembles")
    write_json(output / "snapshot.json", {k: v for k, v in snapshot.items() if k != "records"})
    print("Profiling complete white-box replay; encoder tensors stored once", flush=True)
    capture_store = EnsembleStore(output / "captures")
    encoder_arrays = {k: a for k, a in first_capture.items() if k.startswith("encoder_")}
    encoder_arrays.update(tokens=greedy[None].numpy(), values=decode_token_samples_to_values(tokenizer, greedy[None], scale).numpy())
    encoder_arrays.update(context=context, encoder_input_ids=ids.numpy(), encoder_attention_mask=mask.numpy(),
                          token_embedding=model.get_input_embeddings().weight.detach().cpu().numpy(),
                          value_token_ids=np.arange(chronos_config.n_special_tokens, chronos_config.n_tokens, dtype=np.int64),
                          decoded_value_bins=np.asarray([tokenizer.token_to_value(t, float(scale.reshape(-1)[0]))
                                                         for t in range(chronos_config.n_special_tokens, chronos_config.n_tokens)], dtype=np.float32))
    encoder_manifest, _ = capture_store.put({**provenance, "capture_profile": "shared_encoder"}, encoder_arrays,
                                           {"all_encoder_layers_heads": True, "encoder_token_count": ids.shape[1]})
    captures = []
    for profile in ("minimal", "exhaustive-forks", "exhaustive-all-steps"):
        begin = time.perf_counter()
        logits, arrays = engine.replay(cached, capture=profile != "minimal")
        compare(logits, engine.replay(cached, capture=False)[0], f"{profile}_sampled_replay")
        arrays = {k: a for k, a in arrays.items() if not k.startswith("encoder_")}
        query_positions = [0, 1, 9, 10] if profile == "exhaustive-forks" else list(range(32))
        if profile == "exhaustive-forks":
            arrays = {k: a[:, query_positions] if "hidden" in k else a[:, :, query_positions, :]
                      for k, a in arrays.items()}
        arrays.update(tokens=cached.numpy(), values=decode_token_samples_to_values(tokenizer, cached, scale).numpy(),
                      logits=logits[:, query_positions].numpy())
        record = {"profile": profile, "seconds_including_serialization": None,
                  "raw_tensor_bytes": sum(a.nbytes for a in arrays.values()), "query_positions": query_positions,
                  "tensor_shapes": {k: list(a.shape) for k, a in arrays.items()},
                  "shared_encoder_task_id": encoder_manifest["task_id"],
                  "captured_fields": sorted(arrays), "dtype": "float32 activations; int64 tokens",
                  "alignment": "query t predicts token t using start and tokens[:t]; full key axis retains causal zeros",
                  "omitted_fields": ["hidden_states", "attentions"] if profile == "minimal" else []}
        manifest, _ = capture_store.put({**provenance, "capture_profile": profile}, arrays, record)
        record["seconds_including_serialization"] = time.perf_counter() - begin
        record["task_id"] = manifest["task_id"]
        captures.append(record)
    write_json(output / "parity.json", parity)
    result = {"status": "complete", "config": config, "provenance": provenance, "source_hashes": source_hashes,
              "software": {name: importlib.metadata.version(name) for name in ("numpy", "torch", "transformers")},
              "model_load_seconds": load_seconds, "encoder_seconds": engine.encoder_seconds,
              "parity_seconds": parity_seconds, "parity_checks": len(parity),
              "max_logit_abs_error": max(p["max_logit_abs_error"] for p in parity),
              "max_q50_abs_error": max(p["max_q50_abs_error"] for p in parity),
              "timings": timings, "window_seconds": window_seconds, "capture_profiles": captures,
              "shared_encoder_raw_bytes": sum(a.nbytes for a in encoder_arrays.values()),
              "encoder_calls_including_capture": engine.encoder_calls, "decoder_calls": engine.decoder_calls,
              "new_sampled_paths_in_timing_profiles": sum(row["paths"] for row in timings if not row["reused"]),
              "timing_profiles_are_not_independent_seed_replications": True,
              "same_seed_token_match": {"encoder_only": bool(torch.equal(base, encoder_only)), "cached": bool(torch.equal(base, cached))},
              "collection_accounting": window["accounting"], "snapshot_id": snapshot["snapshot_id"],
              "limitations": ["One selected original context, CPU float32/eager only", "Dense branches use micro N2, not campaign N20",
                              "N60 direct estimates do not calibrate N2 mixtures", "No formal change-point inference or scientific effect claim",
                              "Replay capture covers two timing-profile paths; other saved paths retain explicit replayable omissions"]}
    write_json(output / "summary.json", result)
    print("Benchmark complete; no production campaign launched", flush=True)


def n20_validation(config_path, output):
    """Target-N20 technical cell on the same approved context; no panel expansion."""
    import numpy as np
    import torch
    from chronos_io import load_chronos_t5_raw
    from chronos_exploratory import CachedDecoder, policy_probabilities
    from chronos_exploratory_window import collect_window
    from ensemble_store import EnsembleStore, read_snapshot

    config = json.loads(config_path.read_text(encoding="utf-8"))
    previous = json.loads((output / "summary.json").read_text())
    for name, digest in previous["source_hashes"].items():
        if name.startswith("code/") and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Sampling source changed since validated micro run: {name}")
    source = read_snapshot(output / "ensembles")["records"][0][1]
    context = source["context"]
    if hashlib.sha256(context.tobytes()).hexdigest() != config["context_sha256"]:
        raise ValueError("N20 context mismatch")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    model, tokenizer, chronos_config = load_chronos_t5_raw(
        config["model_id"], device="cpu", dtype="float32", revision=config["model_revision"],
        local_files_only=True, attn_implementation="eager")
    ids, mask, scale = tokenizer.context_input_transform(torch.from_numpy(context.copy())[None])
    engine = CachedDecoder(model, chronos_config, ids, mask)
    greedy = engine.greedy(32)
    if not np.array_equal(greedy.numpy(), source["greedy_tokens"]):
        raise ValueError("N20 reference greedy path changed")
    full_logits, _ = engine.replay(greedy[None])
    for t in range(32):
        cached = engine.prefix_state(greedy[:t].tolist()).logits.cpu()
        expected = full_logits[:, t]
        q, reference_q = policy_probabilities(cached, chronos_config), policy_probabilities(expected, chronos_config)
        if not torch.allclose(cached, expected, atol=1e-5, rtol=1e-4) or not torch.allclose(q, reference_q, atol=1e-6, rtol=1e-4) or not torch.equal(q > 0, reference_q > 0):
            raise ValueError("N20 pre-sampling parity gate failed")
    provenance = {**previous["provenance"], "experiment": output.name + "/target_N20_validation",
                  "scope": "single_context_target_N20_micro_validation"}
    directory = output / "n20_validation/ensembles"
    started = time.perf_counter()
    result = collect_window(engine, tokenizer, scale, context, EnsembleStore(directory), provenance,
                            samples_per_group=20, direct_samples=60, seed=config["seed"],
                            batch_size=8, overlap_positions=config["overlap_positions"])
    elapsed = time.perf_counter() - started
    write_json(output / "n20_window_results.json", result)
    snapshot = read_snapshot(directory)
    write_json(output / "n20_snapshot.json", {k: v for k, v in snapshot.items() if k != "records"})
    write_json(output / "n20_summary.json", {
        "status": "complete", "provenance": provenance, "collection_accounting": result["accounting"],
        "window_seconds": elapsed, "samples_per_group": 20, "direct_samples": 60,
        "context_sha256": config["context_sha256"], "snapshot_id": snapshot["snapshot_id"],
        "sampling_source_hashes": {k: v for k, v in previous["source_hashes"].items() if k.startswith("code/")},
        "limitations": ["Same selected original series/context; no population inference",
                        "Full token/value paths saved; exhaustive replay capture is bounded to named paths",
                        "This single engineering cell does not implement or approve a production panel"]})


def resource_replay(config_path, output, n20=False):
    """Capture actual b0/b9 branch paths and validate job resources without draws."""
    import numpy as np
    import torch
    from chronos_io import load_chronos_t5_raw
    from chronos_exploratory import CachedDecoder, policy_probabilities
    from ensemble_store import EnsembleStore, read_snapshot

    config = json.loads(config_path.read_text(encoding="utf-8"))
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    previous = json.loads((output / ("n20_summary.json" if n20 else "summary.json")).read_text())
    window = json.loads((output / ("n20_window_results.json" if n20 else "window_results.json")).read_text())
    source_snapshot = read_snapshot(output / ("n20_validation/ensembles" if n20 else "ensembles"))
    context = source_snapshot["records"][0][1]["context"]
    if hashlib.sha256(context.tobytes()).hexdigest() != config["context_sha256"]:
        raise ValueError("Replay source context differs")
    selected, roles, queries = [], [], []
    for b in (0, 9):
        row = window["forks"][b]
        alternative = next((t for t in row["selected_tokens"] if t != row["greedy_token"]), None)
        for role in ("reference", "alternative"):
            candidates = [(m, a) for m, a in source_snapshot["records"]
                          if m["identity"]["position"] == b and m["identity"]["role"] == role
                          and (role == "reference" or m["identity"]["token"] == alternative)]
            if not candidates:
                raise ValueError("Requested actual fork replay paths unavailable")
            manifest, arrays = candidates[0]
            arrays = {**arrays, "tokens": arrays["tokens"][:2], "values": arrays["values"][:2]}
            selected.append(arrays)
            roles.extend([{"b": b, "role": role, "source_task_id": manifest["task_id"], "path_index": i}
                          for i in range(len(arrays["tokens"]))])
            queries.extend([[b, b + 1]] * len(arrays["tokens"]))
    tokens = np.concatenate([a["tokens"] for a in selected])
    values = np.concatenate([a["values"] for a in selected])
    print(f"Resource validation: replaying {len(tokens)} saved actual b0/b9 paths; no new stochastic draws", flush=True)
    model, tokenizer, chronos_config = load_chronos_t5_raw(
        config["model_id"], device="cpu", dtype="float32", revision=config["model_revision"],
        local_files_only=True, attn_implementation="eager")
    ids, mask, _ = tokenizer.context_input_transform(torch.from_numpy(context.copy())[None])
    engine = CachedDecoder(model, chronos_config, ids, mask)
    capture_store = EnsembleStore(output / ("n20_resource_captures" if n20 else "resource_captures"))
    baseline, _ = engine.replay(tokens, capture=False)
    profiles, encoder_id = [], None
    row_ids = np.arange(len(tokens))[:, None]
    query_matrix = np.asarray(queries)
    for profile in ("minimal", "exhaustive-forks", "exhaustive-all-steps"):
        started = time.perf_counter()
        logits, captured = engine.replay(tokens, capture=profile != "minimal")
        q, expected = policy_probabilities(logits, chronos_config), policy_probabilities(baseline, chronos_config)
        if not torch.allclose(logits, baseline, atol=1e-5, rtol=1e-4) or not torch.allclose(q, expected, atol=1e-6, rtol=1e-4) or not torch.equal(q > 0, expected > 0):
            raise ValueError("Actual fork replay/capture policy parity failed")
        if captured and encoder_id is None:
            encoder_arrays = {k: a for k, a in captured.items() if k.startswith("encoder_")}
            encoder_arrays.update(tokens=tokens[:1], values=values[:1], encoder_input_ids=ids.numpy(),
                                  encoder_attention_mask=mask.numpy())
            manifest, _ = capture_store.put({"source_snapshot": source_snapshot["snapshot_id"], "profile": "shared_encoder"}, encoder_arrays,
                                            {"all_layers_heads": True, "source_model_revision": config["model_revision"]})
            encoder_id = manifest["task_id"]
        arrays = {k: a for k, a in captured.items() if not k.startswith("encoder_")}
        if profile == "exhaustive-forks":
            arrays = {k: a[row_ids, query_matrix] if "hidden" in k else
                      np.stack([np.take(a[i], pair, axis=1) for i, pair in enumerate(queries)]) for k, a in arrays.items()}
            logit_arrays = logits.numpy()[row_ids, query_matrix]
        else:
            logit_arrays = logits.numpy()
        arrays.update(tokens=tokens, values=values, logits=logit_arrays)
        details = {"profile": profile, "saved_paths": len(tokens), "source_paths": roles,
                   "raw_tensor_bytes": sum(a.nbytes for a in arrays.values()),
                   "query_positions_per_path": queries if profile == "exhaustive-forks" else [list(range(32))] * len(tokens),
                   "tensor_shapes": {k: list(a.shape) for k, a in arrays.items()},
                   "shared_encoder_task_id": encoder_id, "all_layers_heads": profile != "minimal",
                   "max_logit_abs_error": float((logits - baseline).abs().max()),
                   "max_q50_abs_error": float((q - expected).abs().max()), "same_q50_support": True,
                   "alignment": "query b is before forced token b; query b+1 includes forced token b"}
        capture_store.put({"source_snapshot": source_snapshot["snapshot_id"], "profile": profile}, arrays, details)
        details["seconds_including_serialization"] = time.perf_counter() - started
        profiles.append(details)
    # Cache/teacher-forcing parity on every saved token prefix, including sampled suffixes.
    max_error = 0.
    with torch.no_grad():
        for i, path in enumerate(tokens):
            for t in range(32):
                actual = engine.prefix_state(path[:t].tolist()).logits.cpu()
                reference = baseline[i:i + 1, t]
                actual_q, reference_q = policy_probabilities(actual, chronos_config), policy_probabilities(reference, chronos_config)
                if not torch.allclose(actual, reference, atol=1e-5, rtol=1e-4) or not torch.allclose(actual_q, reference_q, atol=1e-6, rtol=1e-4) or not torch.equal(actual_q > 0, reference_q > 0):
                    raise ValueError("Cached vs teacher-forced sampled-prefix parity failed")
                max_error = max(max_error, float((actual - reference).abs().max()))
    write_json(output / ("n20_resource_replay.json" if n20 else "resource_replay.json"), {
        "status": "complete", "new_stochastic_paths": 0, "saved_paths_replayed": len(tokens),
        "source_sampling_digest": previous["provenance"]["source_digest"],
        "source_snapshot_id": source_snapshot["snapshot_id"], "profiles": profiles,
        "sampled_prefix_checks": len(tokens) * 32, "max_sampled_prefix_logit_error": max_error,
        "supervision": "Native Windows Job Object; suspended creation; process-tree memory accounting/termination",
        "first_attempt_memory_peak_invalid": True})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--resource-replay", action="store_true", help="Validate process-tree resources/capture on saved token paths; no sampling")
    parser.add_argument("--n20-validation", action="store_true", help="Target N20 on the same single cached context, within the shared model budget")
    args = parser.parse_args()
    try:
        if args.worker:
            if args.resource_replay:
                resource_replay(args.config.resolve(), args.output.resolve(), args.n20_validation)
            elif args.n20_validation:
                n20_validation(args.config.resolve(), args.output.resolve())
            else:
                worker(args.config.resolve(), args.output.resolve())
            result = 0
        else:
            result = supervise(args.config.resolve(), args.output, args.resource_replay, args.n20_validation)
    except BaseException as error:
        if args.output.is_dir():
            write_json(args.output / "failure.json", {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()})
        raise
    sys.exit(result)
