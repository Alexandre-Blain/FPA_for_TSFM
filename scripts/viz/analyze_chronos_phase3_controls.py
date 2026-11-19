"""Bounded offline controls for the saved Phase 2 pilot; never loads a model."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

for variable in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ[variable] = "1"

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code" / "chronos_fpa"))
import bootstrap  # noqa: E402,F401

import numpy as np
import pandas as pd

from chronos_distances import DISTANCE_CONVENTIONS, empirical_w1_by_horizon, energy_distance_v
from research_schema import read_csv
from results_io import make_run_dir, save_dataframe, save_json
from trajectory_export import load_fork_ensembles, validate_trajectory_links

METRICS = ("w1", "ed")


def rng_for(seed, *identity):
    digest = hashlib.sha256(json.dumps([seed, *identity], sort_keys=True).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


def prepare_pool(paths):
    paths = np.asarray(paths, dtype=float)
    if paths.ndim != 2 or min(paths.shape) == 0 or not np.isfinite(paths).all():
        raise ValueError("A finite nonempty [paths, horizons] pool is required")
    order = np.argsort(paths, axis=0, kind="stable")
    gaps = np.diff(np.take_along_axis(paths, order, axis=0), axis=0)
    distances = np.stack([np.linalg.norm(paths - row, axis=1) / np.sqrt(paths.shape[1]) for row in paths])
    return order, gaps, distances


def pool_statistics(cache, left, right):
    """Exact empirical W1 and ED V-statistic, reusing a fixed path pool.

    CDF integration permits unused pool rows and unequal ensemble sizes.
    For signed empirical weights u, the Energy functional equals -u.T D u.
    """
    order, gaps, distances = cache
    left, right = np.asarray(left, dtype=int), np.asarray(right, dtype=int)
    if not len(left) or not len(right) or len(np.unique(np.r_[left, right])) != len(left) + len(right):
        raise ValueError("Nonempty disjoint unique whole-path indices are required")
    weights = np.zeros(len(order))
    weights[left], weights[right] = 1 / len(left), -1 / len(right)
    cdf = np.cumsum(weights[order], axis=0)[:-1]
    w1 = float(np.sum(np.abs(cdf) * gaps) / gaps.shape[1])
    energy = float(-weights @ distances @ weights)
    tolerance = 128 * np.finfo(float).eps * max(1., float(distances.max()))
    if energy < -tolerance:
        raise ArithmeticError("Negative cached Energy statistic beyond roundoff")
    return np.array([w1, max(0., energy)])


def permutation_pair(a, b, count, rng):
    """Relabel complete paths under the independent equal-law null."""
    pool = np.concatenate([a, b])
    cache = prepare_pool(pool)
    n = len(a)
    observed = pool_statistics(cache, np.arange(n), np.arange(n, len(pool)))
    expected = [empirical_w1_by_horizon(a, b).mean(), energy_distance_v(a, b)]
    np.testing.assert_allclose(observed, expected, rtol=1e-10, atol=1e-10)
    values = np.empty((count, 2))
    for iteration in range(count):
        indices = rng.permutation(len(pool))
        values[iteration] = pool_statistics(cache, indices[:n], indices[n:])
    return observed, values


def permutation_p(observed, null, two_sided=False):
    observed, null = np.asarray(observed), np.asarray(null)
    if two_sided:
        observed, null = np.abs(observed), np.abs(null)
    tolerance = 128 * np.finfo(float).eps * np.maximum(1., np.abs(observed))
    return (1 + np.sum(null >= observed - tolerance, axis=0)) / (len(null) + 1)


def holm_adjust(pvalues):
    pvalues = np.asarray(pvalues, dtype=float)
    order = np.argsort(pvalues)
    adjusted = np.minimum(1., np.maximum.accumulate(pvalues[order] * np.arange(len(order), 0, -1)))
    result = np.empty_like(adjusted)
    result[order] = adjusted
    return result


def subsample_group(reference, alternatives, null, sizes, repeats, rng):
    """Paired reference/null subsets across alternatives, not population CIs."""
    n = len(reference)
    paths = {"same_token": null, **alternatives}
    caches = {name: prepare_pool(np.concatenate([reference, sample])) for name, sample in paths.items()}
    rows = []
    for size in sizes:
        if not 1 <= size <= n or any(len(p) != n for p in paths.values()):
            raise ValueError("Subsamples must fit the equally sized saved ensembles")
        for repeat in range(1 if size == n else repeats):
            left = np.arange(n) if size == n else rng.choice(n, size, replace=False)
            for name in paths:
                right = np.arange(n) if size == n else rng.choice(n, size, replace=False)
                stats = pool_statistics(caches[name], left, right + n)
                rows.append({"sample_size": size, "repeat": repeat, "role": str(name), "w1": stats[0], "ed": stats[1]})
    return rows


def asymmetry_permutations(reference, down, up, count, rng):
    """Hold reference fixed, exchange the two alternative labels as whole paths.

    Null is equal alternative laws, NOT equal absolute distances alone.
    Statistic is signed D(reference,up) - D(reference,down).
    """
    n = len(reference)
    if len(down) != n or len(up) != n:
        raise ValueError("This pilot asymmetry diagnostic needs equal sample counts")
    cache = prepare_pool(np.concatenate([reference, down, up]))
    ref, indices = np.arange(n), np.arange(n, 3 * n)
    observed = pool_statistics(cache, ref, indices[n:]) - pool_statistics(cache, ref, indices[:n])
    values = np.empty((count, 2))
    for repeat in range(count):
        shuffled = rng.permutation(indices)
        values[repeat] = pool_statistics(cache, ref, shuffled[n:]) - pool_statistics(cache, ref, shuffled[:n])
    return observed, values


def temporal_permutations(reference, other, count, rng):
    """Only the Phase 2 ERCOT example: first 10 versus remaining horizons."""
    if reference.shape[1] <= 10:
        raise ValueError("Temporal diagnostic requires more than ten horizons")
    def statistic(a, b):
        profile = empirical_w1_by_horizon(a, b)
        early, late = profile[:10].mean(), profile[10:].mean()
        return np.array([early, late, early - late])
    pool = np.concatenate([reference, other])
    n = len(reference)
    values = np.empty((count, 3))
    for repeat in range(count):
        indices = rng.permutation(len(pool))
        values[repeat] = statistic(pool[indices[:n]], pool[indices[n:]])
    return statistic(reference, other), values


def path_descriptors(paths, scale):
    paths = np.asarray(paths, dtype=float)
    t = np.arange(paths.shape[1], dtype=float)
    t -= t.mean()
    slope = (paths @ t) / np.sum(t * t)
    residual = paths - paths.mean(axis=1, keepdims=True) - slope[:, None] * t
    return {"endpoint_change_iqr": (paths[:, -1] - paths[:, 0]) / scale,
            "ols_slope_iqr_per_step": slope / scale,
            "detrended_rms_iqr": np.sqrt(np.mean(residual * residual, axis=1)) / scale}


def wilson_interval(successes, n):
    z = 1.959963984540054
    proportion, denominator = successes / n, 1 + z * z / n
    center = (proportion + z * z / (2 * n)) / denominator
    half = z * np.sqrt(proportion * (1 - proportion) / n + z * z / (4 * n * n)) / denominator
    return (0. if successes == 0 else max(0., center - half),
            1. if successes == n else min(1., center + half))


def summarize_subsampling(draws):
    keys = ["dataset_name", "series_id", "window_id", "branch_step", "seed"]
    summaries, rankings = [], []
    for identity, group in draws.groupby(keys):
        info = dict(zip(keys, identity))
        full = group[group.sample_size.eq(50)].set_index("role")
        alternatives = sorted(set(group.role) - {"same_token"})
        for size, subset in group.groupby("sample_size"):
            for metric in METRICS:
                column = metric + "_iqr"
                wide = subset.pivot(index="repeat", columns="role", values=column)
                for role in wide:
                    values = wide[role]
                    summaries.append({**info, "sample_size": size, "role": role, "metric": metric,
                        "n_subsets": len(values), "median_iqr": values.median(),
                        "q05_iqr": values.quantile(.05), "q95_iqr": values.quantile(.95),
                        "fraction_above_shared_null": float((values > wide.same_token).mean()) if role != "same_token" else np.nan})
                if len(alternatives) == 2:
                    first, second = alternatives
                    delta = wide[first] - wide[second]
                    full_delta = full.loc[first, column] - full.loc[second, column]
                    rankings.append({**info, "sample_size": size, "metric": metric,
                        "first_token": first, "second_token": second, "n_subsets": len(delta),
                        "full50_difference_iqr": full_delta,
                        "fraction_same_order_as_full50": float((np.sign(delta) == np.sign(full_delta)).mean()),
                        "difference_q05_iqr": delta.quantile(.05), "difference_median_iqr": delta.median(),
                        "difference_q95_iqr": delta.quantile(.95)})
    return pd.DataFrame(summaries), pd.DataFrame(rankings)


def run_controls(run_dir, output_dir=None, permutations=999, repeats=100, seed=20261117):
    if not 19 <= permutations <= 1999 or not 10 <= repeats <= 200:
        raise ValueError("Bounded offline analysis: 19..1999 permutations and 10..200 subsamples")
    started = time.monotonic()
    run_dir = Path(run_dir).resolve()
    output = Path(output_dir).resolve() if output_dir else make_run_dir(ROOT / "result", None, "phase3_offline_controls")
    if output_dir:
        if output.exists() or output.is_relative_to(run_dir):
            raise ValueError("Use a new output directory outside the Phase 2 run")
        output.mkdir(parents=True)
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    input_hashes = {"config.json": hashlib.sha256((run_dir / "config.json").read_bytes()).hexdigest()}
    if (run_dir / "execution_plan.json").exists():
        input_hashes["execution_plan.json"] = hashlib.sha256((run_dir / "execution_plan.json").read_bytes()).hexdigest()
    permutation_rows, subsamples, asymmetries, descriptors, descriptor_paths, temporal = [], [], [], [], [], []
    null_arrays = {}
    group_count = 0
    for model_seed in config["seeds"]:
        seed_dir = run_dir / f"seed_{model_seed}"
        summary = read_csv(seed_dir / "chronos_scan_summary.csv")
        input_hashes[str((seed_dir / "chronos_scan_summary.csv").relative_to(run_dir))] = hashlib.sha256((seed_dir / "chronos_scan_summary.csv").read_bytes()).hexdigest()
        for link in summary.trajectory_manifest.unique():
            validate_trajectory_links(summary[summary.trajectory_manifest.eq(link)], seed_dir)
            path = seed_dir / link
            manifest, arrays = load_fork_ensembles(path)
            if not manifest["context_iqr_valid"]:
                raise ValueError("This bounded pilot analysis requires valid saved context IQR")
            for source in (path, path.with_name(manifest["archive"])):
                input_hashes[str(source.relative_to(run_dir))] = hashlib.sha256(source.read_bytes()).hexdigest()
            scale = manifest["context_iqr"]
            ident = {k: manifest["window"][k] for k in ("dataset_name", "series_id", "window_id")}
            ident.update(branch_step=manifest["branch_step"], seed=model_seed)
            reference = arrays[manifest["reference_array_key"]]
            null = arrays["same_token_null"]
            ref_meta = next(e for e in manifest["ensembles"] if e["is_reference"])
            alternatives = {e["token_id"]: arrays[e["array_key"]] for e in manifest["ensembles"] if not e["is_reference"]}
            identity = [model_seed, manifest["fork_id"]]
            print(f"Offline group {group_count + 1}: {ident}", flush=True)
            for label, sample in {"same_token": null, **alternatives}.items():
                observed, values = permutation_pair(reference, sample, permutations, rng_for(seed, *identity, str(label), "permutation"))
                array_id = f"pair_{group_count}_{label}"
                null_arrays[array_id] = values
                probabilities = permutation_p(observed, values)
                for column, metric in enumerate(METRICS):
                    permutation_rows.append({**ident, "comparison": str(label), "metric": metric,
                        "observed_raw": observed[column], "observed_iqr": observed[column] / scale,
                        "permutation_median_iqr": np.median(values[:, column]) / scale,
                        "permutation_q95_iqr": np.quantile(values[:, column], .95) / scale,
                        "p_exploratory": probabilities[column], "permutations": permutations,
                        "null_array": array_id, "null_column": column, "n_per_ensemble": len(reference)})
                if ident["dataset_name"] == "ercot" and ident["series_id"] == "EAST" and ident["branch_step"] == 0 and str(label) in {"same_token", "2228"}:
                    observed_time, null_time = temporal_permutations(reference, sample, permutations, rng_for(seed, *identity, str(label), "temporal"))
                    temporal_id = f"temporal_{group_count}_{label}"
                    null_arrays[temporal_id] = null_time
                    temporal.append({**ident, "comparison": str(label),
                        "early_w1_iqr": observed_time[0] / scale, "late_w1_iqr": observed_time[1] / scale,
                        "early_minus_late_iqr": observed_time[2] / scale,
                        "permutation_contrast_q95_iqr": np.quantile(null_time[:, 2], .95) / scale,
                        "p_exploratory": float(permutation_p(observed_time[2:3], null_time[:, 2:3])[0]),
                        "null_array": temporal_id, "null_column": 2})
            for row in subsample_group(reference, alternatives, null, (20, 35, 50), repeats, rng_for(seed, *identity, "subsampling")):
                subsamples.append({**ident, **row, "w1_iqr": row["w1"] / scale, "ed_iqr": row["ed"] / scale})
            entries = [e for e in manifest["ensembles"] if not e["is_reference"]]
            signed = [e["forced_value"] - ref_meta["forced_value"] for e in entries]
            if len(entries) == 2 and signed[0] * signed[1] < 0 and np.isclose(abs(signed[0]), abs(signed[1]), rtol=.001, atol=0):
                down = entries[0] if signed[0] < 0 else entries[1]
                up = entries[1] if signed[0] < 0 else entries[0]
                observed, values = asymmetry_permutations(reference, alternatives[down["token_id"]], alternatives[up["token_id"]], permutations, rng_for(seed, *identity, "asymmetry"))
                array_id = f"asymmetry_{group_count}"
                null_arrays[array_id] = values
                probabilities = permutation_p(observed, values, two_sided=True)
                for column, metric in enumerate(METRICS):
                    asymmetries.append({**ident, "metric": metric, "up_token": up["token_id"], "down_token": down["token_id"],
                        "up_p_sel": up["p_sel"], "down_p_sel": down["p_sel"],
                        "delta_up_minus_down_iqr": observed[column] / scale,
                        "p_exploratory": probabilities[column], "null_array": array_id, "null_column": column})
            for entry in manifest["ensembles"]:
                for name, values in path_descriptors(arrays[entry["array_key"]], scale).items():
                    count = int(np.sum(values > 0)) if name == "endpoint_change_iqr" else np.nan
                    lower, upper = wilson_interval(count, len(values)) if np.isfinite(count) else (np.nan, np.nan)
                    descriptors.append({**ident, "token_id": entry["token_id"], "is_reference": entry["is_reference"],
                        "descriptor": name, "n": len(values), "q10": np.quantile(values, .1), "median": np.median(values),
                        "q90": np.quantile(values, .9), "positive_count": count,
                        "positive_fraction": count / len(values), "positive_wilson95_low": lower, "positive_wilson95_high": upper})
                    descriptor_paths.extend({**ident, "token_id": entry["token_id"], "path_index": index,
                                             "descriptor": name, "value": value} for index, value in enumerate(values))
            group_count += 1
    table = pd.DataFrame(permutation_rows)
    alternative = table.comparison.ne("same_token")
    table["holm_exploratory_family"] = np.nan
    table.loc[alternative, "holm_exploratory_family"] = holm_adjust(table.loc[alternative, "p_exploratory"])
    asymmetry = pd.DataFrame(asymmetries)
    if not asymmetry.empty:
        asymmetry["holm_exploratory_family"] = holm_adjust(asymmetry.p_exploratory)
    save_dataframe(output / "permutation_tests.csv", table)
    save_dataframe(output / "directional_asymmetry.csv", asymmetry)
    temporal_table = pd.DataFrame(temporal)
    if not temporal_table.empty:
        selected = temporal_table.comparison.ne("same_token")
        temporal_table["holm_exploratory_family"] = np.nan
        temporal_table.loc[selected, "holm_exploratory_family"] = holm_adjust(temporal_table.loc[selected, "p_exploratory"])
    save_dataframe(output / "temporal_localization.csv", temporal_table)
    draws = pd.DataFrame(subsamples)
    stability, ranking = summarize_subsampling(draws)
    save_dataframe(output / "subsampling_draws.csv", draws)
    save_dataframe(output / "subsampling_stability.csv", stability)
    save_dataframe(output / "subsampling_rank_stability.csv", ranking)
    save_dataframe(output / "path_descriptors.csv", pd.DataFrame(descriptors))
    save_dataframe(output / "path_descriptor_values.csv", pd.DataFrame(descriptor_paths))
    np.savez_compressed(output / "permutation_distributions.npz", **null_arrays)
    save_json(output / "protocol.json", {
        "scope": "Phase 3 Deliverable A only: bounded offline exploratory controls; no model inference",
        "source_run": str(run_dir), "source_hashes": input_hashes,
        "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "distance_source_sha256": hashlib.sha256((ROOT / "code/chronos_fpa/metrics/chronos_distances.py").read_bytes()).hexdigest(),
        "software": {"numpy": np.__version__, "pandas": pd.__version__},
        "distance_conventions": DISTANCE_CONVENTIONS, "normalization": "saved historical context_iqr; no fallback",
        "offline_rng_seed": seed, "rng": "SHA256 per group/role; NumPy default_rng",
        "n_point_seed_groups": group_count, "permutations_per_test": permutations,
        "monte_carlo_p": "(1 + count(T_perm >= T_observed))/(B+1); absolute statistic for signed asymmetry; roundoff ties retained",
        "exchangeability": "whole independent paths under equal conditional laws; never timestep shuffling",
        "multiple_tests": "Holm over all alternative/seed/metric tests; separate matched-direction asymmetry and targeted temporal-contrast families; controls diagnostic only; separate families do not control a combined study-wide error rate",
        "selection_bias": "all pilot tests remain exploratory; multiplicity correction cannot undo historical context/outcome selection",
        "subsampling": "without replacement inside each saved ensemble; shared reference and null draw across alternatives; conditional finite-pool stability, not population CIs",
        "sample_sizes": [20, 35, 50], "subsample_repeats": repeats, "n50_repeats": 1,
        "morphology": "OLS slope and detrended RMS over full strict suffix; no plateau/peak/trend classifier; Wilson intervals are pointwise binomial conditional on fixed context, not motif discovery",
        "matched_absolute_jump_relative_tolerance": .001,
        "temporal_scope": "Only ERCOT/EAST b=0 token 2228 and same-token controls; first 10 vs remaining horizons selected in Phase 2, explicitly post hoc",
        "elapsed_seconds": time.monotonic() - started,
    })
    print(f"Saved offline controls for {group_count} groups to {output}", flush=True)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--permutations", type=int, default=999)
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261117)
    args = parser.parse_args()
    run_controls(args.run_dir, args.output_dir, args.permutations, args.repeats, args.seed)
