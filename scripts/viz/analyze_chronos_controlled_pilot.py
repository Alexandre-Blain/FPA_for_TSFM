"""Offline Phase 2 analysis of saved empirical ensembles; no model imports."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code" / "chronos_fpa"))
import bootstrap  # noqa: E402,F401

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from chronos_distances import empirical_w1_by_horizon, energy_distance_v
from controlled_pilot_plan import group_identity, selected_groups
from research_schema import read_csv
from results_io import save_dataframe, save_json
from trajectory_export import load_fork_ensembles

IDENTITY = ["dataset_name", "series_id", "window_id", "branch_step", "token_id"]
BLUE, RED, GRAY = "#0072B2", "#D55E00", "#686868"


def descriptive_correlation(x, y, method):
    if method == "spearman":
        # Spearman is Pearson on average ranks, including tied observations.
        return x.rank(method="average").corr(y.rank(method="average"))
    if method == "pearson":
        return x.corr(y)
    raise ValueError(f"Unsupported pilot correlation: {method}")


def comparison_limits(x, y):
    values = np.concatenate([np.asarray(x, dtype=float), np.asarray(y, dtype=float)])
    positive = values[np.isfinite(values) & (values > 0)]
    return (float(positive.min() * .8), float(positive.max() * 1.25)) if positive.size else (1e-6, 1.)


def compare_saved(reference, alternative, null, n, scale):
    a, b, c = [np.asarray(paths[:n], dtype=float) for paths in (reference, alternative, null)]
    profile, null_profile = empirical_w1_by_horizon(a, b), empirical_w1_by_horizon(a, c)
    metrics = {"w1_post": float(profile.mean()), "ed_post": energy_distance_v(a, b),
               "null_w1_post": float(null_profile.mean()), "null_ed_post": energy_distance_v(a, c)}
    for name, value in list(metrics.items()):
        metrics[name + "_iqr"] = value / scale if scale is not None and scale > 1e-12 else np.nan
    for name in ("w1", "ed"):
        metrics[name + "_excess_iqr"] = metrics[name + "_post_iqr"] - metrics["null_" + name + "_post_iqr"]
        floor = metrics["null_" + name + "_post"]
        metrics[name + "_over_null"] = metrics[name + "_post"] / floor if floor > 1e-12 else np.nan
    # Same 47-step relative suffix support for the b=0/b=16 comparison.
    length = min(47, a.shape[1])
    metrics["common_length"] = length
    metrics["w1_first47_iqr"] = float(profile[:length].mean()) / scale if scale else np.nan
    metrics["ed_first47_iqr"] = energy_distance_v(a[:, :length], b[:, :length]) / scale if scale else np.nan
    metrics["null_w1_first47_iqr"] = float(null_profile[:length].mean()) / scale if scale else np.nan
    metrics["null_ed_first47_iqr"] = energy_distance_v(a[:, :length], c[:, :length]) / scale if scale else np.nan
    # A transparent per-path descriptor, not a peak/trend classifier.
    for label, paths in (("reference", a), ("alternative", b)):
        delta = paths[:, -1] - paths[:, 0]
        metrics[label + "_end_minus_start_positive_count"] = int(np.sum(delta > 0))
        metrics[label + "_end_minus_start_zero_count"] = int(np.sum(delta == 0))
        metrics[label + "_end_minus_start_median_iqr"] = float(np.median(delta)) / scale if scale else np.nan
    return metrics, profile, null_profile


def collect(run_dir, config):
    rows, profiles, points, archives = [], [], [], {}
    strata = {(c["dataset_name"], c["series_id"], c["window_id"]): c["stratum"] for c in config["cases"]}
    for seed in config["seeds"]:
        seed_dir = run_dir / f"seed_{seed}"
        summary = read_csv(seed_dir / "chronos_scan_summary.csv")
        if summary.empty:
            continue
        for link in summary.trajectory_manifest.unique():
            path = seed_dir / link
            manifest, arrays = load_fork_ensembles(path)
            if not manifest["context_iqr_valid"]:
                raise ValueError("Pilot contains an invalid IQR; raw-only analysis must be explicit")
            point = {**manifest["window"], "branch_step": manifest["branch_step"], "seed": seed}
            point["stratum"] = strata[(point["dataset_name"], point["series_id"], point["window_id"])]
            point["manifest"] = str(path.relative_to(ROOT)).replace("\\", "/")
            point["context_iqr"] = manifest["context_iqr"]
            point["token_entropy"] = manifest["selection_policy"]["token_entropy"]
            point["normalized_token_entropy"] = manifest["selection_policy"]["normalized_token_entropy"]
            point["candidate_probability_mass"] = manifest["selection_policy"]["candidate_probability_mass"]
            reference = arrays[manifest["reference_array_key"]]
            null = arrays["same_token_null"]
            ref_meta = next(e for e in manifest["ensembles"] if e["is_reference"])
            if ref_meta["rng"]["stream_id"] == manifest["same_token_null"]["rng"]["stream_id"]:
                raise ValueError("Null and reference RNG streams are not distinct")
            points.append({**point, "num_samples": len(reference), "post_fork_length": reference.shape[1],
                           "candidate_count_including_base": len(manifest["ensembles"]),
                           "reference_token_id": manifest["reference_token_id"]})
            group = summary[(summary.branch_step == point["branch_step"]) &
                            (summary.series_id == point["series_id"]) &
                            (summary.dataset_name == point["dataset_name"]) &
                            (summary.window_id == point["window_id"])]
            for entry in manifest["ensembles"]:
                if entry["is_reference"]:
                    continue
                alternative = arrays[entry["array_key"]]
                token = entry["token_id"]
                old = group[group.token_id == token]
                if len(old) != 1:
                    raise ValueError("Archive to summary join is not one-to-one")
                archives[(seed, *[point[k] for k in IDENTITY[:-1]], token)] = (manifest, arrays, entry)
                for n in config["nested_sample_counts"]:
                    if n > len(reference):
                        raise ValueError("Requested N exceeds stored sample count")
                    metrics, w1, null_w1 = compare_saved(reference, alternative, null, n, point["context_iqr"])
                    direct = entry["forced_value"] - ref_meta["forced_value"]
                    row = {**point, "num_samples": n, "token_id": token, "rank": entry["candidate_rank"],
                           "p_sel": entry["p_sel"], "p_sampling_at_fork": entry["p_sampling_at_fork"],
                           "signed_token_jump": direct, "direct_jump_iqr": abs(direct) / point["context_iqr"],
                           "post_fork_length": reference.shape[1], **metrics}
                    # Recomputed N=50 must match the already committed Phase 1 metrics.
                    if n == manifest["sample_count"]:
                        for name in ("w1_post", "ed_post"):
                            if not np.isclose(row[name], old.iloc[0][name], rtol=1e-10, atol=1e-10):
                                raise ValueError(f"Saved sample/committed metric disagreement: {name}")
                    legacy = [c for c in old.columns if "forking_score" in c and "context_iqr" in c]
                    for column in legacy:
                        row["legacy_" + column] = old.iloc[0][column] if n == manifest["sample_count"] else np.nan
                    rows.append(row)
                    for h, (value, floor) in enumerate(zip(w1, null_w1), start=point["branch_step"] + 1):
                        profiles.append({**{k: row[k] for k in ["seed", *IDENTITY, "num_samples", "stratum"]},
                                         "forecast_step": h, "relative_step": h - point["branch_step"],
                                         "w1": value, "null_w1": floor,
                                         "w1_iqr": value / point["context_iqr"],
                                         "null_w1_iqr": floor / point["context_iqr"]})
    return pd.DataFrame(rows), pd.DataFrame(profiles), pd.DataFrame(points), archives


def save_overview(frame, directory):
    data = frame[frame.num_samples == 50].copy()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    for dataset, group in data.groupby("dataset_name"):
        for axis, metric in zip(axes, ("w1", "ed")):
            axis.scatter(group["null_" + metric + "_post_iqr"], group[metric + "_post_iqr"], label=dataset, alpha=.8)
    for axis, metric in zip(axes, ("W1", "ED")):
        x, y = data["null_" + metric.lower() + "_post_iqr"], data[metric.lower() + "_post_iqr"]
        lo, hi = comparison_limits(x, y)
        axis.plot([lo, hi], [lo, hi], color=GRAY, linestyle="--", label="effect = same-token control")
        axis.set(xscale="log", yscale="log", xlim=(lo, hi), ylim=(lo, hi), xlabel=f"Same-token {metric} / context IQR",
                 ylabel=f"Alternative vs reference {metric} / context IQR", title=metric + " at N=50")
        excluded = int(((x <= 0) | (y <= 0)).sum())
        if excluded:
            axis.text(.02, .02, f"{excluded} nonpositive pairs not shown on log axes", transform=axis.transAxes, fontsize=8)
        axis.legend(fontsize=8)
    fig.suptitle("Descriptive noise comparison: shared references; points are NOT independent series")
    fig.savefig(directory / "effect_vs_same_token_control.png", dpi=150)
    plt.close(fig)
    paired = frame.pivot(index=["seed", *IDENTITY], columns="num_samples", values=["w1_post_iqr", "ed_post_iqr"])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for axis, name, title in zip(axes, ("w1_post_iqr", "ed_post_iqr"), ("W1", "ED")):
        x, y = paired[name][20], paired[name][50]
        axis.scatter(x, y, color=BLUE, alpha=.8)
        lo, hi = comparison_limits(x, y)
        axis.plot([lo, hi], [lo, hi], color=GRAY, linestyle="--")
        axis.set(xscale="log", yscale="log", xlim=(lo, hi), ylim=(lo, hi), xlabel=f"N=20 {title} / context IQR",
                 ylabel=f"N=50 {title} / context IQR", title=title + ": nested samples")
        excluded = int(((x <= 0) | (y <= 0)).sum())
        if excluded:
            axis.text(.02, .02, f"{excluded} nonpositive pairs not shown on log axes", transform=axis.transAxes, fontsize=8)
    fig.suptitle("First 20 of the saved 50 paths: NOT independent replications")
    fig.savefig(directory / "nested_sample_comparison.png", dpi=150)
    plt.close(fig)


def choose_gallery(frame):
    data = frame[frame.num_samples == 50]
    numeric = ["w1_post_iqr", "ed_post_iqr", "w1_over_null", "ed_over_null", "direct_jump_iqr"]
    pool = data.groupby(IDENTITY + ["stratum"], as_index=False)[numeric].mean()
    main = pool[pool.stratum == "main"]
    candidates = [
        ("strong_main_ED", main.ed_post_iqr.sort_values(ascending=False).index),
        ("near_control_main", (main.w1_over_null + main.ed_over_null).sort_values().index),
        ("middle_main_ED", (main.ed_post_iqr - main.ed_post_iqr.median()).abs().sort_values().index),
        ("rare_token_stress", pool[pool.stratum == "stress"].direct_jump_iqr.sort_values(ascending=False).index),
        ("W1_ED_rank_disagreement", (main.w1_post_iqr.rank() - main.ed_post_iqr.rank()).abs().sort_values(ascending=False).index),
        ("effect_per_direct_jump", (main.w1_post_iqr / main.direct_jump_iqr).sort_values(ascending=False).index),
    ]
    selected, used = [], set()
    for role, indices in candidates:
        index = next((i for i in indices if i not in used), None)
        if index is not None:
            used.add(index)
            selected.append({"selection_role": role, **pool.loc[index].to_dict()})
    return pd.DataFrame(selected)


def gallery_plot(row, seed, archives, directory):
    key = (seed, *[row[k] for k in IDENTITY])
    manifest, arrays, entry = archives[key]
    reference, alternative = arrays[manifest["reference_array_key"]], arrays[entry["array_key"]]
    scale = manifest["context_iqr"]
    metrics, profile, floor = compare_saved(reference, alternative, arrays["same_token_null"], 50, scale)
    b = manifest["branch_step"]
    x = np.arange(b + 1, manifest["window"]["horizon"])
    reference_entry = next(e for e in manifest["ensembles"] if e["is_reference"])
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout="constrained")
    for axis, paths, meta, color, title in (
        (axes[0, 0], reference, reference_entry, BLUE, "Forced greedy token + sampled suffix"),
        (axes[0, 1], alternative, entry, RED, "Forced alternative token + sampled suffix"),
    ):
        axis.plot(x, paths[:20].T, color=color, alpha=.10, linewidth=.6)
        q10, median, q90 = np.quantile(paths, [.1, .5, .9], axis=0)
        axis.fill_between(x, q10, q90, color=color, alpha=.18, label="pointwise q10-q90 (50 paths)")
        axis.plot(x, median, color=color, linewidth=2, label="pointwise median")
        prefix = arrays["greedy_prefix_values"]
        if len(prefix):
            axis.plot(np.arange(b), prefix, color=GRAY, linewidth=1, label="shared greedy prefix")
        axis.scatter([b], [meta["forced_value"]], color=color, marker="x", s=60, label="forced coordinate (excluded)")
        axis.set(title=title + f"; rank={meta['candidate_rank']}, p_sel={meta['p_sel']:.3g}",
                 xlabel="Forecast index (0-based)", ylabel="Decoded value (original series units)")
        axis.legend(fontsize=8)
    limits = [a.get_ylim() for a in axes[0]]
    for axis in axes[0]:
        axis.set_ylim(min(t[0] for t in limits), max(t[1] for t in limits))
    axes[1, 0].plot(x, profile / scale, color=RED, label="alternative vs reference")
    axes[1, 0].plot(x, floor / scale, color=GRAY, linestyle="--", label="independent same-token control")
    axes[1, 0].set(xlabel="Forecast index h > b (forced coordinate excluded)", ylabel="Empirical marginal W1(h) / context IQR",
                   title=f"W1={metrics['w1_post_iqr']:.3g}; ED={metrics['ed_post_iqr']:.3g}; null ED={metrics['null_ed_post_iqr']:.3g}")
    axes[1, 0].legend(fontsize=8)
    deltas = [(p[:, -1] - p[:, 0]) / scale for p in (reference, alternative)]
    bins = np.linspace(min(d.min() for d in deltas), max(d.max() for d in deltas) + 1e-12, 15)
    for delta, color, title in zip(deltas, (BLUE, RED), ("reference", "alternative")):
        axes[1, 1].hist(delta, bins=bins, color=color, alpha=.4, label=f"{title}: positive={int(np.sum(delta>0))}/50")
    axes[1, 1].axvline(0, color=GRAY, linestyle="--")
    axes[1, 1].set(xlabel="Per-path (Y[H-1] - Y[b+1]) / context IQR", ylabel="Number of sampled paths",
                   title="Endpoint-change descriptor, NOT a trend/peak classifier")
    axes[1, 1].legend(fontsize=8)
    fig.suptitle(f"{row['selection_role']}: {row['dataset_name']}/{row['series_id']} w{row['window_id']} "
                 f"b={b}, token={entry['token_id']}, seed={seed}\n"
                 f"Direct jump / IQR={row['direct_jump_iqr']:.3g}; N=50; bands are marginal, not simultaneous\n"
                 "p_sel = P(token at b | context + greedy prefix), before top-50 renormalization")
    filename = f"{row['selection_role']}_seed_{seed}.png"
    fig.savefig(directory / filename, dpi=150)
    plt.close(fig)
    return filename


def analyze(run_dir):
    run_dir = Path(run_dir).resolve()
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    plan_path = run_dir / "execution_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else None
    scheduled = selected_groups(config, plan)
    output = run_dir / ("analysis_half" if plan else "analysis")
    figures = output / "figures"
    gallery_dir = figures / "morphology_candidates"
    gallery_dir.mkdir(parents=True, exist_ok=True)
    rows, profiles, points, archives = collect(run_dir, config)
    if rows.empty:
        raise ValueError("No committed pilot group is available for analysis")
    save_dataframe(output / "branch_effects.csv", rows)
    save_dataframe(output / "w1_profiles.csv", profiles)
    save_dataframe(output / "fork_points.csv", points)
    fifty = rows[rows.num_samples == 50]
    coverage = []
    for threshold in config["probability_thresholds"]:
        for stratum, population in fifty.groupby("stratum"):
            for dataset, group in [("ALL", population), *list(population.groupby("dataset_name"))]:
                kept = group[group.p_sel >= threshold]
                unique = group.drop_duplicates(IDENTITY)
                retained = kept.drop_duplicates(IDENTITY)
                coverage.append({"threshold": threshold, "stratum": stratum, "dataset_name": dataset,
                                 "unique_forks_total": len(unique), "unique_forks_retained": len(retained),
                                 "observations_retained": len(kept),
                                 "alternative_mass_total": unique.p_sel.sum(),
                                 "alternative_mass_retained": retained.p_sel.sum(),
                                 **{name + "_median": kept[name].median() for name in
                                    ("w1_post_iqr", "ed_post_iqr", "direct_jump_iqr", "w1_over_null", "ed_over_null")}})
    save_dataframe(output / "probability_coverage.csv", pd.DataFrame(coverage))
    stability = fifty.pivot(index=IDENTITY + ["stratum"], columns="seed", values=["w1_post_iqr", "ed_post_iqr", "w1_over_null", "ed_over_null"])
    stability.columns = [f"{metric}_seed_{seed}" for metric, seed in stability.columns]
    save_dataframe(output / "seed_stability.csv", stability.reset_index())
    comparisons = rows.pivot(index=["seed", *IDENTITY], columns="num_samples", values=["w1_post_iqr", "ed_post_iqr", "null_w1_post_iqr", "null_ed_post_iqr"])
    comparisons.columns = [f"{metric}_n{n}" for metric, n in comparisons.columns]
    save_dataframe(output / "nested_n_comparison.csv", comparisons.reset_index())
    # Pooled correlation is descriptive only; do not attach IID p-values.
    correlations = []
    for stratum, population in fifty.groupby("stratum"):
        groups = [("POOLED", population), *[(f"series:{d}/{s}", g) for (d, s), g in population.groupby(["dataset_name", "series_id"])]]
        for label, group in groups:
            for x in ("token_entropy", "normalized_token_entropy", "p_sel", "direct_jump_iqr"):
                for y in ("w1_post_iqr", "ed_post_iqr"):
                    for method in ("pearson", "spearman"):
                        valid = group[[x, y]].dropna()
                        unique_count = len(group.drop_duplicates(IDENTITY))
                        reason = ("fewer_than_three_unique_alternatives" if unique_count < 3 else
                                  "constant_variable" if valid[x].nunique() <= 1 or valid[y].nunique() <= 1 else "")
                        value = descriptive_correlation(valid[x], valid[y], method) if not reason else np.nan
                        correlations.append({"stratum": stratum, "population": label, "x": x, "y": y,
                                             "method": method, "n_branch_seed_rows": len(valid),
                                             "n_unique_alternatives": unique_count, "undefined_reason": reason,
                                             "n_unique_fork_points": len(group.drop_duplicates(IDENTITY[:-1])),
                                             "coefficient": value, "iid_significance_computed": False})
    save_dataframe(output / "descriptive_correlations.csv", pd.DataFrame(correlations))
    save_overview(rows, figures)
    gallery = choose_gallery(rows)
    files = []
    for row in gallery.to_dict("records"):
        for seed in config["seeds"]:
            if (seed, *[row[k] for k in IDENTITY]) not in archives:
                continue
            files.append({**row, "seed": seed, "figure": gallery_plot(row, seed, archives, gallery_dir)})
    save_dataframe(output / "morphology_candidates.csv", pd.DataFrame(files))
    observed = {(p.seed, p.dataset_name, p.series_id, p.window_id, p.branch_step)
                for p in points.itertuples(index=False)}
    if not observed.issubset({group_identity(group) for group in scheduled}):
        raise ValueError("Observed groups lie outside the recorded execution plan")
    missing = [group for group in scheduled if group_identity(group) not in observed]
    deferred = [group for group in selected_groups(config)
                if group_identity(group) not in {group_identity(g) for g in scheduled}]
    save_json(output / "analysis_protocol.json", {
        "scope": "Phase 2 only; no new inference", "normalization": "context_iqr",
        "analysis_version": "chronos_controlled_pilot_analysis_v3_rank_correlations",
        "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_config_sha256": hashlib.sha256((run_dir / "config.json").read_bytes()).hexdigest(),
        "execution_plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest() if plan else None,
        "n_comparison": "first 20 nested within saved 50; not independent replications",
        "same_token_control": "one independent ensemble per fork point/seed; shared reference",
        "null_interpretation": "descriptive noise baseline, not a calibrated significance threshold",
        "candidate_pool_unique_alternative_forks": len(fifty.drop_duplicates(IDENTITY)),
        "observed_fork_point_seed_groups": len(points),
        "observed_original_series": len(points.drop_duplicates(["dataset_name", "series_id"])),
        "missing_approved_groups": missing,
        "deliberately_deferred_original_groups": deferred,
        "planned_fork_point_seed_groups": len(scheduled),
        "gallery_selection": "up to six deterministic role-based examples, seed-averaged; unavailable roles are skipped; see selection_role",
        "gallery_selected_unique_forks": len(gallery),
        "gallery_figure_count": len(files),
        "correlation_convention": "Pearson on values; Spearman is Pearson on average ranks, including ties; descriptive only, no IID p-values",
        "morphology": "descriptive ensemble inspection only; endpoint sign is not a motif classifier",
        "statistical_limits": "original design contains four series; executed subsets have fewer; repeated seeds may be uneven across points; shared reference and branch positions; no IID p-values",
        "entropy_convention": "decoder entropy uses valid-token p_sel; normalized entropy divides by log(number of strictly positive floating-point probabilities), not necessarily fixed vocabulary size",
        "figures": "q10-q90 are pointwise marginal bands; first 20 faint paths; medians use all 50",
        "common_support": "first 47 strictly downstream steps, relative to each branch position",
    })
    print(f"Analyzed {len(points)} fork-point/seed groups, {len(fifty)} alternative/seed observations, "
          f"{len(fifty.drop_duplicates(IDENTITY))} unique alternatives. Outputs: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    analyze(parser.parse_args().run_dir)
