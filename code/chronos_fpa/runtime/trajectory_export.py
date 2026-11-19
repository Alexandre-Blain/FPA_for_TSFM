"""Opt-in, per-fork numeric ensemble archives and reproducibility metadata."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

import numpy as np

from chronos_distances import DISTANCE_CONVENTIONS, DISTANCE_VERSION, IQR_EPS, context_iqr_scale
from research_schema import WINDOW_KEY_COLS, window_key
from results_io import publish_directory, save_json


def add_trajectory_arguments(parser):
    parser.add_argument("--trajectory-metrics", action="store_true", help="Add strict post-fork W1/ED and one independent same-token ensemble (single branches only).")
    parser.add_argument("--save-trajectories", action="store_true", help="Save individual numeric suffix ensembles and provenance; implies --trajectory-metrics.")
    parser.add_argument("--sampling-seed", type=int, default=0, help="Root seed for independent per-window/token streams when trajectory metrics are enabled.")


def validate_trajectory_arguments(args):
    if args.resume_from:
        path = Path(args.resume_from) / "run_state.json"
        if path.exists():
            saved = json.loads(path.read_text(encoding="utf-8"))["args"]
            for name, default in (("trajectory_metrics", False), ("save_trajectories", False), ("sampling_seed", 0)):
                if getattr(args, name) != saved.get(name, default):
                    raise ValueError(f"Incompatible resume option {name}; start a new run")
    if args.trajectory_metrics or args.save_trajectories:
        if {mode.strip() for mode in args.branch_modes.split(",")} != {"single"}:
            raise ValueError("Trajectory metrics currently require --branch-modes single; bundle outputs remain historical-only")
        if args.temperature <= 0:
            raise ValueError("Trajectory sampling temperature must be positive")


def trajectory_options_from_args(args, run_dir, model, config):
    if not (args.trajectory_metrics or args.save_trajectories):
        return None
    root = Path(__file__).resolve().parents[3]
    versions = {"python": platform.python_version()}
    for name in ("numpy", "torch", "transformers"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False)
    source_files = list((root / "code" / "chronos_fpa").rglob("*.py")) + list((root / "scripts" / "runs").glob("*.py"))
    provenance = {
        "model_id": args.model_id,
        "model_revision": getattr(model.config, "_commit_hash", None),
        "model_dtype": str(next(model.parameters()).dtype),
        "model_device": str(next(model.parameters()).device),
        "model_eval": not model.training,
        "tokenizer_config": asdict(config),
        "software_versions": versions,
        "code_version": {"git_head": git.stdout.strip() or None,
                         "source_sha256": {str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(source_files)}},
    }
    protocol = {"distance_version": DISTANCE_VERSION, "sampling_seed": args.sampling_seed,
                "distance_conventions": DISTANCE_CONVENTIONS,
                "temperature": args.temperature, "sample_top_k": args.sample_top_k,
                "independent_same_token_control": True, "provenance": provenance}
    protocol_path = Path(run_dir) / "trajectory_protocol.json"
    if protocol_path.exists():
        previous = json.loads(protocol_path.read_text(encoding="utf-8"))
        if previous.get("distance_conventions") != DISTANCE_CONVENTIONS:
            raise ValueError("Distance conventions changed; start a separate trajectory run")
        if previous["provenance"]["model_revision"] != provenance["model_revision"]:
            raise ValueError("Model revision changed since this trajectory run; refusing mixed-model resume")
    else:
        save_json(protocol_path, protocol)
    return {"sampling_seed": args.sampling_seed,
            "output_dir": Path(run_dir) / "trajectories" if args.save_trajectories else None,
            "provenance": provenance}


def fork_namespace(window):
    context = np.asarray(window.context, dtype=np.float32)
    return json.dumps([list(window_key(window)), hashlib.sha256(context.tobytes()).hexdigest()], separators=(",", ":"))


def _numpy(values):
    if hasattr(values, "detach"):
        values = values.detach().cpu().numpy()
    return np.asarray(values)


def _array_description(values):
    return {"shape": list(values.shape), "dtype": str(values.dtype),
            "sha256": hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()}


def load_fork_ensembles(manifest_path):
    """Read numeric arrays without pickle and validate the recorded array hashes."""
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "chronos_numeric_ensembles_v1":
        raise ValueError("Unsupported numeric ensemble schema")
    archive = path.parent / manifest["archive"]
    if archive.resolve().parent != path.parent.resolve():
        raise ValueError("Ensemble archive must stay beside its manifest")
    with np.load(archive, allow_pickle=False) as stored:
        arrays = {name: stored[name] for name in stored.files}
    if set(arrays) != set(manifest["arrays"]):
        raise ValueError("Ensemble array keys differ from the manifest")
    for name, values in arrays.items():
        if _array_description(values) != manifest["arrays"][name]:
            raise ValueError(f"Ensemble checksum/shape/dtype mismatch: {name}")
    return manifest, arrays


def validate_trajectory_links(summary, run_dir):
    if "trajectory_manifest" not in summary:
        return
    root = Path(run_dir).resolve()
    for link in summary["trajectory_manifest"].unique():
        path = (root / str(link)).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Trajectory links must remain inside their run")
        manifest, _ = load_fork_ensembles(path)
        expected_window = dict(zip(WINDOW_KEY_COLS, window_key(next(summary.itertuples(index=False)))))
        if manifest["window"] != expected_window:
            raise ValueError("Trajectory manifest window identity mismatch")
        if manifest["branch_step"] != int(summary.branch_step.iloc[0]):
            raise ValueError("Trajectory manifest branch position mismatch")
        if {entry["token_id"] for entry in manifest["ensembles"]} != set(summary.token_id.astype(int)):
            raise ValueError("Trajectory manifest branch identities mismatch")


def save_fork_ensembles(output_dir, decoded, window, provenance):
    """Publish one archive per fork. Base and independent null are each saved once.

    Publish before the existing branch-group callback. An interrupted publication
    is not a committed group; deterministic RNG streams make retries reproducible.
    A conflicting existing archive is rejected, never silently overwritten.
    """
    position = int(decoded["branch_step"])
    identity = [fork_namespace(window), position]
    digest = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / digest
    scale, valid, reason = context_iqr_scale(window.context)
    reference_token = int(decoded["base_token_at_branch"])
    arrays = {"context": np.asarray(window.context, dtype=np.float32),
              "greedy_prefix_tokens": _numpy(decoded["base_tokens"])[:position],
              "greedy_prefix_values": _numpy(decoded["base_values"])[:position]}
    ensembles = []
    for token, entry in decoded["branches"].items():
        name = f"token_{token}"
        samples = _numpy(entry["sample_values"])
        arrays[name] = samples[:, position + 1:]
        alt = entry["alternative"]
        ensembles.append({"array_key": name, "token_id": int(token),
                          "forced_value": float(samples[0, position]), "candidate_rank": int(alt.rank),
                          "p_sel": float(alt.probability), "p_sampling_at_fork": float(alt.sampling_probability),
                          "is_reference": int(token) == reference_token, "rng": entry["rng"]})
    arrays["same_token_null"] = _numpy(decoded["same_token_null"]["sample_values"])[:, position + 1:]
    reference = decoded["branches"][reference_token]["alternative"]
    manifest = {
        "schema_version": "chronos_numeric_ensembles_v1", "distance_version": DISTANCE_VERSION,
        "distance_conventions": DISTANCE_CONVENTIONS,
        "fork_id": digest, "archive": "ensembles.npz",
        "window": dict(zip(("source", "dataset_name", "series_id", "window_id", "window_start", "context_len", "horizon"), window_key(window))),
        "context_sha256": _array_description(arrays["context"])["sha256"],
        "branch_step": position, "post_fork_start": position + 1, "post_fork_length": window.horizon - position - 1,
        "reference_array_key": f"token_{reference_token}", "reference_token_id": reference_token,
        "context_iqr": scale if np.isfinite(scale) else None, "context_iqr_valid": valid,
        "invalid_scale_reason": reason, "context_iqr_tolerance": IQR_EPS,
        "tokenizer_mean_abs_scale": float(_numpy(decoded["tokenizer_scale"]).reshape(-1)[0]),
        "sample_count": int(decoded["metadata"]["num_samples"]),
        "selection_policy": {"distribution": "softmax of valid-token-masked logits; no temperature or top-k renormalization",
                             "candidate_top_k": decoded["metadata"]["top_k"], "minimum_probability": None,
                             "token_entropy": reference.token_entropy, "normalized_token_entropy": reference.normalized_token_entropy,
                             "candidate_probability_mass": sum(e["p_sel"] for e in ensembles)},
        "decoder_policy": {**decoded["metadata"], "do_sample": True, "top_p": 1.0,
                           "special_token_policy": "exclude all specials, EOS and PAD",
                           "top_k_ties": "retain every logit equal to the kth threshold", "use_cache": False},
        "ensembles": ensembles,
        "same_token_null": {"array_key": "same_token_null", "forced_token_id": reference_token,
                            "forced_value": next(entry["forced_value"] for entry in ensembles if entry["is_reference"]),
                            "p_sel": reference.probability,
                            "rng": decoded["same_token_null"]["rng"], "shared_reference": f"token_{reference_token}"},
        "arrays": {name: _array_description(values) for name, values in arrays.items()},
        "provenance": provenance,
    }
    if destination.exists():
        previous, _ = load_fork_ensembles(destination / "manifest.json")
        if previous != manifest:
            raise ValueError("Existing fork archive conflicts with these samples/provenance; start a separate run")
        return destination / "manifest.json"
    pending = Path(tempfile.mkdtemp(prefix=".pending-", dir=root))
    with (pending / "ensembles.npz").open("wb") as stream:
        np.savez_compressed(stream, **arrays)
        stream.flush()
        os.fsync(stream.fileno())
    save_json(pending / "manifest.json", manifest)
    publish_directory(pending, destination)
    return destination / "manifest.json"
