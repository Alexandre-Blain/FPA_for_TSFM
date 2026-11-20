"""Prospective context-only panel selection; no model loading or future features."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from chronos_distances import context_iqr_scale
from ensemble_store import task_id


FEATURES = ("trend_iqr", "diff_std_iqr", "lag1", "lag24", "half_shift_iqr", "zero_fraction")


def context_features(context):
    x = np.asarray(context, dtype=np.float32)
    iqr, valid, reason = context_iqr_scale(x)
    if x.shape != (512,) or not np.isfinite(x).all():
        raise ValueError("nonfinite_or_incomplete_context")
    if not valid:
        raise ValueError(reason)
    y = x.astype(float)
    centered = y - y.mean()
    time = np.arange(512, dtype=float) - 255.5
    def corr(lag):
        a, b = y[:-lag], y[lag:]
        return float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.
    return {"context_iqr": iqr, "trend_iqr": float(centered @ time / (time @ time) * 511 / iqr),
            "diff_std_iqr": float(np.diff(y).std() / iqr), "lag1": corr(1), "lag24": corr(24),
            "half_shift_iqr": float((y[256:].mean() - y[:256].mean()) / iqr),
            "zero_fraction": float(np.mean(y == 0)), "context_mean": float(y.mean()),
            "context_std": float(y.std()), "context_min": float(y.min()), "context_max": float(y.max())}


def eligible_row(row, dataset, excluded):
    series_id = str(row["series_id"])
    if series_id in excluded:
        raise ValueError("previously_studied_original_series_excluded")
    target = row["target"]
    origin = len(target) - 32
    if origin < 512:
        raise ValueError("fewer_than_512_context_plus32_available")
    # Future values are never passed to any feature/QC predicate.
    context = np.asarray(target[origin - 512:origin], dtype=np.float32)
    features = context_features(context)
    record = {"dataset_id": dataset, "series_id": series_id, "forecast_origin": origin,
              "context_start": origin - 512, "context_end_exclusive": origin,
              "context_sha256": hashlib.sha256(context.tobytes()).hexdigest(), **features,
              "source_repo": row.get("source_repo"), "source_split": row.get("split"),
              "training_overlap": "unverified possible overlap; local export is training split, not certified held-out",
              "prior_FPA_exposure": "not among documented studied series; broader exposure unverified"}
    return record, context


def rank_features(records):
    values = np.array([[r[k] for k in FEATURES] for r in records])
    ranks = np.empty_like(values)
    for j in range(values.shape[1]):
        _, inverse, counts = np.unique(values[:, j], return_inverse=True, return_counts=True)
        average = np.cumsum(counts) - (counts + 1) / 2
        ranks[:, j] = average[inverse] / max(len(records) - 1, 1)
    return ranks


def choose_pair(records, dataset, seed):
    records = sorted(records, key=lambda r: r["series_id"])
    if len(records) < 2:
        raise ValueError("At least two distinct eligible original series required")
    derived_seed = int.from_bytes(hashlib.sha256(f"{seed}:{dataset}".encode()).digest()[:8], "big")
    rng = np.random.default_rng(derived_seed)
    representative = int(rng.integers(len(records)))
    ranks = rank_features(records)
    radius = np.square(ranks - np.median(ranks, axis=0)).mean(axis=1)
    allowed = [i for i in range(len(records)) if i != representative and radius[i] <= np.quantile(radius, .9)]
    if not allowed:
        raise ValueError("No non-extreme distinct diversity candidate")
    distance = np.square(ranks - ranks[representative]).mean(axis=1)
    diverse = min(allowed, key=lambda i: (-distance[i], records[i]["series_id"]))
    return [{**records[i], "stratum": role, "selection_rng_seed": derived_seed,
             "diversity_distance": float(distance[i]), "rank_radius": float(radius[i]),
             "representative_inclusion_probability": 1 / len(records)}
            for i, role in ((representative, "representative"), (diverse, "diversity"))]


def select_panel(root, config):
    root = Path(root)
    selected, population, rejections, contexts, source_hashes = [], [], [], {}, {}
    for dataset in config["datasets"]:
        source = Path("data/raw/chronos_benchmark") / f"autogluon_chronos_datasets__{dataset}__train.jsonl"
        path = root / source
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        source_hashes[source.as_posix()] = digest
        rows, seen = [], set()
        with path.open(encoding="utf-8") as stream:
            for row_number, line in enumerate(stream):
                row = json.loads(line)
                series = str(row["series_id"])
                try:
                    if series in seen:
                        raise ValueError("duplicate_original_series_id")
                    seen.add(series)
                    record, context = eligible_row(row, dataset, config["known_studied_series"].get(dataset, []))
                    record.update(source_file=source.as_posix(), source_sha256=digest, source_row=row_number)
                    rows.append(record)
                    contexts[(dataset, series)] = context
                except ValueError as error:
                    rejections.append({"dataset_id": dataset, "series_id": series,
                                       "source_row": row_number, "reason": str(error)})
        pair = choose_pair(rows, dataset, config["selection_seed"])
        for record in pair:
            record["window_id"] = task_id({k: record[k] for k in
                ("dataset_id", "series_id", "forecast_origin", "context_sha256", "source_sha256")})
        selected += pair
        chosen = {r["series_id"] for r in pair}
        population += [{**r, "selection_status": "selected" if r["series_id"] in chosen else "eligible_not_selected"}
                       for r in rows]
    if len(selected) != 6 or len({(r["dataset_id"], r["series_id"]) for r in selected}) != 6:
        raise ValueError("Exactly six distinct original series are required")
    core = {"schema": "chronos_six_window_pilot_v1", "config": config, "windows": selected,
            "source_hashes": source_hashes, "eligible_population": population, "rejections": rejections}
    core["grid_revision"] = task_id(core)
    arrays = {r["window_id"]: contexts[(r["dataset_id"], r["series_id"])] for r in selected}
    return core, arrays
