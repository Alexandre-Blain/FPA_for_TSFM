"""Descriptive analysis of finalized local-pilot cells; no model loading/draws."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

os.environ.setdefault("MPLBACKEND", "Agg")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code/chronos_fpa"))
sys.path.insert(0, str(ROOT / "scripts/runs"))
import bootstrap  # noqa: E402,F401

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd

from chronos_distances import empirical_w1_by_horizon, energy_distance_v
from chronos_outcomes import THRESHOLDS, window_outcomes
from chronos_pilot_uncertainty import event_uncertainty, independent_difference, reused_component_covariance
from chronos_pilot_validation import read_complete_cell
from run_chronos_microbenchmark import jsonable, write_json


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rank_correlation(a, b):
    a, b = pd.Series(a).rank(), pd.Series(b).rank()
    return float(a.corr(b)) if a.nunique() > 1 and b.nunique() > 1 else np.nan


def summarize(frame, columns):
    return {c: {"min": float(frame[c].min()), "median": float(frame[c].median()),
                "max": float(frame[c].max())} for c in columns}


def analyze(output):
    complete = load(output / "pilot_complete.json")
    plan = load(output / "cell_plan.json")
    panel = load(output / "selection_manifest.json")
    analysis = output / "analysis"
    figures = analysis / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__), analysis / "analyze_chronos_local_pilot.py")
    windows = {w["window_id"]: w for w in panel["windows"]}
    all_cells, branch_rows, fork_rows, event_rows, overlap_rows, covariance_rows = [], [], [], [], [], []
    morphology_rows, profiles, accounting = [], [], []
    rng_stream_ids = set()
    for cell in plan:
        directory = output / "cells" / cell["cell_id"]
        marker_path = directory / "complete.json"
        if hashlib.sha256(marker_path.read_bytes()).hexdigest() != complete["complete_sha256"][cell["cell_id"]]:
            raise ValueError("Pilot aggregate/complete-cell hash mismatch")
        marker, result, validation = read_complete_cell(directory, cell["scope"])
        window = windows[cell["window_id"]]
        common = {"cell_id": cell["cell_id"], "window_id": cell["window_id"], "primary": cell["primary"],
                  "dataset": cell["scope"]["dataset_id"], "series": cell["scope"]["series_id"],
                  "seed": cell["scope"]["sampling_seed"], "stratum": cell["stratum"]}
        timing = load(directory / "timing.json")
        accounting.append({**common, "ensembles": validation["ensembles"], "paths": validation["paths"],
                           "positions": 10, "alternatives": len(result["distances"]), **timing,
                           "captured_paths": load(directory / "capture_summary.json")["selected_paths"],
                           "parity_checks": len(load(directory / "parity.json")),
                           "max_logit_error": max(r["logit_abs_max"] for r in load(directory / "parity.json")),
                           "max_q50_error": max(r["q50_abs_max"] for r in load(directory / "parity.json"))})
        lookup = validation["lookup"]
        for manifest, _ in validation["records"]:
            stream = manifest["metadata"]["rng"]["stream_id"]
            if stream in rng_stream_ids:
                raise ValueError("An RNG stream was reused across finalized ensembles/cells")
            rng_stream_ids.add(stream)
        greedy, iqr = np.asarray(result["greedy_values"]), result["context_iqr"]
        for row in result["distances"]:
            fork = result["forks"][row["b"]]
            token_offset = row["token"] - fork["greedy_token"]
            record = {**common, **{k: v for k, v in row.items() if k not in {"w1_profile", "same_token_null"}},
                      "entropy_q50": fork["entropy_q50_nats"], "entropy_p_sel": fork["entropy_p_sel_nats"],
                      "selected_mass": fork["selected_mass"], "residual_mass": fork["residual_mass"],
                      "token_offset": token_offset, "bin_width_iqr": abs(row["signed_direct_token_jump_over_context_iqr"] / token_offset),
                      "context_iqr": iqr, "context_lag1": window["lag1"], "context_diff_std_iqr": window["diff_std_iqr"]}
            record.update({"null_" + k: v for k, v in row["same_token_null"].items()})
            # Two transparent numerical propagation comparators; primary estimands unchanged.
            record["persistent_shift_w1_iqr"] = row["direct_token_jump_over_context_iqr"]
            record["context_ar1_shift_w1_fixed22_iqr"] = row["direct_token_jump_over_context_iqr"] * np.mean(abs(window["lag1"]) ** np.arange(1, 23))
            reference = lookup[(row["b"], "reference", fork["greedy_token"])][1]["values"]
            alternative = lookup[(row["b"], "alternative", row["token"])][1]["values"]
            null = lookup[(row["b"], "null", fork["greedy_token"])][1]["values"]
            suffix_reference, suffix_null = reference[:, row["b"] + 1:].astype(float), null[:, row["b"] + 1:].astype(float)
            signed_jump = float(alternative[0, row["b"]]) - float(reference[0, row["b"]])
            for label, response in (("persistent", np.ones(suffix_null.shape[1])),
                                    ("context_ar1", window["lag1"] ** np.arange(1, suffix_null.shape[1] + 1))):
                translated_null = suffix_null + signed_jump * response
                w1 = empirical_w1_by_horizon(suffix_reference, translated_null)
                record[f"independent_null_{label}_w1_fixed22_iqr"] = w1[:22].mean() / iqr
                record[f"independent_null_{label}_ed_fixed22_iqr"] = energy_distance_v(suffix_reference[:, :22], translated_null[:, :22]) / iqr
            branch_rows.append(record)
            null_profile = empirical_w1_by_horizon(reference[:, row["b"] + 1:], null[:, row["b"] + 1:]) / iqr
            for h, value in enumerate(row["w1_profile"], 1):
                profiles.append({**common, "b": row["b"], "token": row["token"], "strict_horizon": h,
                                 "forecast_coordinate": row["b"] + h, "w1_raw": value,
                                 "w1_iqr": value / iqr, "null_w1_iqr": null_profile[h - 1]})
            for role, paths in (("reference", reference), ("alternative", alternative)):
                suffix = (paths[:, row["b"] + 1:].astype(float) - greedy[row["b"] + 1:]) / iqr
                time = np.arange(suffix.shape[1], dtype=float)
                centered = time - time.mean()
                descriptors = {"mean_level_delta_iqr": suffix.mean(axis=1),
                               "residual_slope_total_iqr": (suffix @ centered) / (centered @ centered) * (len(time) - 1),
                               "residual_roughness_iqr": np.abs(np.diff(suffix, axis=1)).mean(axis=1),
                               "trajectory_roughness_iqr": np.abs(np.diff(paths[:, row["b"] + 1:].astype(float), axis=1)).mean(axis=1) / iqr,
                               "terminal_delta_iqr": suffix[:, -1]}
                for descriptor, values in descriptors.items():
                    morphology_rows.append({**common, "b": row["b"], "token": row["token"], "role": role,
                                            "descriptor": descriptor, "mean": values.mean(),
                                            "q10": np.quantile(values, .1), "median": np.median(values), "q90": np.quantile(values, .9)})
        for fork in result["forks"]:
            fork_rows.append({**common, **fork})
        estimates = {}
        for position in range(16):
            if position < 10:
                groups, weights = validation["groups_by_position"][position]
            elif position == 10:
                groups = [lookup[(9, "reference", int(result["greedy_tokens"][9]))][1]]
                weights = [1.]
            else:
                groups, weights = [lookup[(position, "direct_cpd", None)][1]], [1.]
            events = [window_outcomes(a["values"], greedy, iqr)["events"] for a in groups]
            estimate = event_uncertainty(events, weights)
            estimates[position] = estimate
            for outcome, name in enumerate(("terminal", "last8")):
                for j, threshold in enumerate(THRESHOLDS):
                    event_rows.append({**common, "position": position, "outcome": name, "threshold": threshold,
                        "probability": estimate["event_probability"][outcome, j],
                        "mc_se": estimate["conditional_mc_se"][outcome, j],
                        "hoeffding_radius": estimate["hoeffding_radius"],
                        "lower": estimate["pointwise_lower"][outcome, j], "upper": estimate["pointwise_upper"][outcome, j],
                        "variance_proxy": estimate["hoeffding_variance_proxy"],
                        "method": result["outcome_distributions"][str(position)]["method"]})
        for position in (0, 9, 10):
            events = window_outcomes(lookup[(position, "overlap_direct", None)][1]["values"], greedy, iqr)["events"]
            direct = event_uncertainty([events], [1.])
            difference = independent_difference(estimates[position], direct)
            family_radius = np.sqrt(np.log(2 * 180 / .05) / 2 *
                                    (estimates[position]["hoeffding_variance_proxy"] + direct["hoeffding_variance_proxy"]))
            for outcome, name in enumerate(("terminal", "last8")):
                for j, threshold in enumerate(THRESHOLDS):
                    gap = difference["difference"][outcome, j]
                    overlap_rows.append({**common, "position": position, "outcome": name, "threshold": threshold,
                        "primary_probability": estimates[position]["event_probability"][outcome, j],
                        "direct_probability": direct["event_probability"][outcome, j], "gap_primary_minus_direct": gap,
                        "primary_variance": estimates[position]["conditional_mc_se"][outcome, j] ** 2,
                        "direct_variance": direct["conditional_mc_se"][outcome, j] ** 2,
                        "gap_mc_se": difference["conditional_mc_se"][outcome, j], "hoeffding_radius": difference["hoeffding_radius"],
                        "pointwise_bound_excludes_zero": abs(gap) > difference["hoeffding_radius"],
                        "calibration_family_radius_180": family_radius,
                        "calibration_family_bound_excludes_zero": abs(gap) > family_radius})
        reference_events = window_outcomes(lookup[(9, "reference", int(result["greedy_tokens"][9]))][1]["values"], greedy, iqr)["events"]
        greedy_weight = result["forks"][9]["selected_weights"][0]
        covariance = reused_component_covariance(reference_events, greedy_weight)
        var9, var10 = estimates[9]["conditional_mc_se"] ** 2, estimates[10]["conditional_mc_se"] ** 2
        for outcome, name in enumerate(("terminal", "last8")):
            for j, threshold in enumerate(THRESHOLDS):
                covariance_rows.append({**common, "outcome": name, "threshold": threshold, "greedy_weight_b9": greedy_weight,
                    "covariance_p9_p10": covariance[outcome, j], "naive_adjacent_se": np.sqrt(var9[outcome, j] + var10[outcome, j]),
                    "corrected_adjacent_se": np.sqrt(max(0., var9[outcome, j] + var10[outcome, j] - 2 * covariance[outcome, j]))})
        all_cells.append((cell, marker, result, validation))
    branches, forks, events, overlap, cov = map(pd.DataFrame, (branch_rows, fork_rows, event_rows, overlap_rows, covariance_rows))
    account, morphology, profile = map(pd.DataFrame, (accounting, morphology_rows, profiles))
    calibration_windows = {c["window_id"] for c in plan if not c["primary"]}
    for wid in calibration_windows:
        repeated = [r[2] for r in all_cells if r[0]["window_id"] == wid]
        if len(repeated) != 3 or any(r["forks"] != repeated[0]["forks"] or r["greedy_tokens"] != repeated[0]["greedy_tokens"] for r in repeated[1:]):
            raise ValueError("Independent-seed calibration changed deterministic weights/greedy path")
    calibration = overlap[overlap.window_id.isin(calibration_windows)]
    seed_variation = []
    for keys, frame in calibration.groupby(["window_id", "dataset", "series", "position", "outcome", "threshold"]):
        first, second = frame.primary_probability, frame.direct_probability
        seed_variation.append({**dict(zip(("window_id", "dataset", "series", "position", "outcome", "threshold"), keys)),
             "independent_seeds": len(frame), "primary_empirical_variance": first.var(ddof=1),
             "direct_empirical_variance": second.var(ddof=1), "mean_primary_plugin_variance": frame.primary_variance.mean(),
             "mean_direct_plugin_variance": frame.direct_variance.mean(), "mean_gap": (first - second).mean(),
             "seed_gap_min": (first - second).min(), "seed_gap_max": (first - second).max(),
             "empirical_gap_variance": (first - second).var(ddof=1), "empirical_cov_primary_direct": first.cov(second),
             "gap_of_three_seed_means_hoeffding_radius": np.sqrt(np.log(2 / .05) / 2 *
                 (frame.hoeffding_radius.iloc[0] ** 2 * 2 / np.log(2 / .05)) / len(frame))})
    variation = pd.DataFrame(seed_variation)
    distance_stability = []
    for wid, frame in branches[branches.window_id.isin(calibration_windows)].groupby("window_id"):
        for metric in ("w1_fixed22_over_context_iqr", "ed_fixed22_over_context_iqr"):
            pivot = frame.pivot(index=["b", "token"], columns="seed", values=metric)
            for i, first in enumerate(pivot.columns):
                for second in pivot.columns[i + 1:]:
                    distance_stability.append({"window_id": wid, "dataset": frame.dataset.iloc[0], "series": frame.series.iloc[0],
                        "metric": metric, "first_seed": first, "second_seed": second,
                        "branches": len(pivot), "spearman": rank_correlation(pivot[first], pivot[second]),
                        "median_absolute_difference": np.median(abs(pivot[first] - pivot[second]))})
    empirical_reuse, boundary = [], []
    for keys, frame in events[events.window_id.isin(calibration_windows)].groupby(["window_id", "dataset", "series", "outcome", "threshold"]):
        common = dict(zip(("window_id", "dataset", "series", "outcome", "threshold"), keys))
        pivot = frame.pivot(index="seed", columns="position", values="probability")
        empirical_reuse.append({**common, "independent_seeds": len(pivot), "empirical_cov_p9_p10": pivot[9].cov(pivot[10]),
                                "empirical_var_p9_minus_p10": (pivot[9] - pivot[10]).var(ddof=1)})
        for seed, group in frame.groupby("seed"):
            p10, p11 = group[group.position == 10].iloc[0], group[group.position == 11].iloc[0]
            boundary.append({**common, "seed": seed, "p10_probability": p10.probability, "p11_probability": p11.probability,
                             "p10_plugin_variance": p10.mc_se ** 2, "p11_plugin_variance": p11.mc_se ** 2,
                             "p10_hoeffding_proxy": p10.variance_proxy, "p11_hoeffding_proxy": p11.variance_proxy})
    primary = branches[branches.primary].copy()
    per_window = []
    correlations = []
    for wid, frame in primary.groupby("window_id", sort=False):
        w = windows[wid]
        row = {"window_id": wid, "dataset": w["dataset_id"], "series": w["series_id"], "stratum": w["stratum"],
               "context_iqr": w["context_iqr"], "alternatives": len(frame)}
        for metric in ("w1_post", "ed_post", "w1_fixed22", "ed_fixed22", "w1_post_over_context_iqr", "ed_post_over_context_iqr",
                       "w1_fixed22_over_context_iqr", "ed_fixed22_over_context_iqr", "null_w1_post_over_context_iqr", "null_ed_post_over_context_iqr"):
            row.update({metric + "_median": frame[metric].median(), metric + "_min": frame[metric].min(), metric + "_max": frame[metric].max()})
        row.update(w1_above_null_count=int((frame.w1_post > frame.null_w1_post).sum()),
                   ed_above_null_count=int((frame.ed_post > frame.null_ed_post).sum()),
                   w1_above_persistent_shift_count=int((frame.w1_post_over_context_iqr > frame.persistent_shift_w1_iqr).sum()),
                   w1_above_context_ar1_count=int((frame.w1_fixed22_over_context_iqr > frame.context_ar1_shift_w1_fixed22_iqr).sum()),
                   w1_above_independent_null_shift_count=int((frame.w1_fixed22_over_context_iqr > frame.independent_null_persistent_w1_fixed22_iqr).sum()),
                   w1_above_independent_null_ar1_count=int((frame.w1_fixed22_over_context_iqr > frame.independent_null_context_ar1_w1_fixed22_iqr).sum()))
        per_window.append(row)
        for effect in ("w1_fixed22_over_context_iqr", "ed_fixed22_over_context_iqr"):
            for predictor in ("direct_token_jump_over_context_iqr", "signed_direct_token_jump_over_context_iqr", "q50", "p_sel", "entropy_q50", "entropy_p_sel"):
                correlations.append({"window_id": wid, "dataset": w["dataset_id"], "series": w["series_id"],
                                     "effect": effect, "predictor": predictor, "spearman": rank_correlation(frame[effect], frame[predictor]),
                                     "branches": len(frame), "independent_series": 1, "interpretation": "descriptive; repeated fork predictors and shared references"})
    window_summary = pd.DataFrame(per_window)
    matched = []
    for (wid, b), frame in primary.groupby(["window_id", "b"]):
        for _, down in frame[frame.token_offset < 0].iterrows():
            up = frame[frame.token_offset == -down.token_offset]
            if len(up):
                up = up.iloc[0]
                matched.append({"window_id": wid, "dataset": down.dataset, "series": down.series, "b": b,
                    "down_token": int(down.token), "up_token": int(up.token), "token_steps": int(up.token_offset),
                    "down_w1_fixed22_iqr": down.w1_fixed22_over_context_iqr, "up_w1_fixed22_iqr": up.w1_fixed22_over_context_iqr,
                    "down_ed_fixed22_iqr": down.ed_fixed22_over_context_iqr, "up_ed_fixed22_iqr": up.ed_fixed22_over_context_iqr,
                    "down_abs_J_iqr": down.direct_token_jump_over_context_iqr, "up_abs_J_iqr": up.direct_token_jump_over_context_iqr,
                    "down_q50": down.q50, "up_q50": up.q50})
    matches = pd.DataFrame(matched)
    for name, frame in (("branches", branches), ("forks", forks), ("outcome_probabilities", events), ("overlap_calibration", overlap),
                        ("reuse_covariance", cov), ("seed_variation", variation), ("accounting", account), ("morphology", morphology),
                        ("w1_profiles", profile), ("per_window_summary", window_summary), ("descriptive_correlations", pd.DataFrame(correlations)),
                        ("matched_jump_pairs", matches), ("empirical_reuse_covariance", pd.DataFrame(empirical_reuse)),
                        ("p10_p11_variance_boundary", pd.DataFrame(boundary)), ("distance_seed_stability", pd.DataFrame(distance_stability))):
        frame.to_csv(analysis / (name + ".csv"), index=False)
    # Per-dataset summaries keep the two series visible; pooling is descriptive only.
    by_dataset = {dataset: {"independent_series": 2, "branches": len(frame),
         "pooled_branch_summary": summarize(frame, ["w1_post", "ed_post", "w1_post_over_context_iqr", "ed_post_over_context_iqr"]),
         "series_equal_weight_mean_of_medians": window_summary[window_summary.dataset == dataset][["w1_post_over_context_iqr_median", "ed_post_over_context_iqr_median"]].mean().to_dict()}
        for dataset, frame in primary.groupby("dataset")}
    attempts = [load(p) for p in (output / "attempts").glob("*.json")]
    selected_cases = []
    for _, frame in primary.groupby("window_id", sort=False):
        selected_cases.append(("largest_ED_within_window_posthoc", frame.loc[frame.ed_fixed22_over_context_iqr.idxmax()]))
    below = primary[primary.w1_post <= primary.null_w1_post]
    if len(below):
        selected_cases.append(("near_or_below_independent_null_posthoc", below.loc[below.w1_post_over_context_iqr.idxmin()]))
    if len(matches):
        contrast = (matches.up_w1_fixed22_iqr - matches.down_w1_fixed22_iqr).abs()
        pair = matches.loc[contrast.idxmax()]
        for token in (pair.down_token, pair.up_token):
            selected_cases.append(("largest_matched_jump_asymmetry_posthoc", primary[(primary.window_id == pair.window_id) & (primary.b == pair.b) & (primary.token == token)].iloc[0]))
    plot_all(output, figures, windows, all_cells, primary, profile, events, overlap, selected_cases)
    summary = {"status": "complete", "independent_original_series": 6, "primary_cells": 6, "calibration_extra_cells": 4,
        "accounting": {"ensembles": int(account.ensembles.sum()), "paths": int(account.paths.sum()), "fork_positions": int(account.positions.sum()),
                       "primary_paths": int(account[account.primary].paths.sum()), "calibration_extra_paths": int(account[~account.primary].paths.sum()),
                       "capture_replay_paths": int(account.captured_paths.sum()), "new_stochastic_profile_paths": 0,
                       "distinct_rng_streams": len(rng_stream_ids),
                       "parity_checks": int(account.parity_checks.sum()), "max_logit_error": account.max_logit_error.max(), "max_q50_error": account.max_q50_error.max()},
        "resources": {"attempts": len(attempts), "failed_attempts": sum(a["exit_code"] != 0 for a in attempts),
                      "model_process_tree_seconds": sum(a["elapsed_seconds"] for a in attempts),
                      "peak_job_committed_bytes": max(a["peak_job_committed_bytes"] for a in attempts),
                      "minimum_system_free_bytes": min(s["system_free_bytes"] for a in attempts for s in a["samples"]),
                      "collection_seconds": float(account.collection_seconds.sum()),
                      "output_file_bytes_at_analysis": sum(p.stat().st_size for p in output.rglob("*") if p.is_file())},
        "per_window": per_window, "per_dataset": by_dataset,
        "coverage": {"primary_forks": len(forks[forks.primary]), "cap8_count": int(sum(len(f["selected_tokens"]) == 8 for f in fork_rows if f["primary"])),
                     "target_not_attained_count": int(sum(not f["target_attained"] for f in fork_rows if f["primary"])),
                     "selected_mass_min": float(forks[forks.primary].selected_mass.min()), "selected_mass_max": float(forks[forks.primary].selected_mass.max()),
                     "residual_mass_max": float(forks[forks.primary].residual_mass.max())},
        "calibration": {"original_series": 2, "seeds_per_window": 3, "comparisons": len(calibration),
                        "max_abs_gap": float(calibration.gap_primary_minus_direct.abs().max()),
                        "pointwise_bound_exclusions": int(calibration.pointwise_bound_excludes_zero.sum()),
                        "family_180_bound_exclusions": int(calibration.calibration_family_bound_excludes_zero.sum()),
                        "zero_plugin_SE_primary_events": int((events[events.primary].mc_se == 0).sum()),
                        "total_primary_event_estimates": len(events[events.primary]),
                        "largest_gaps": calibration.assign(abs_gap=calibration.gap_primary_minus_direct.abs()).nlargest(8, "abs_gap").to_dict("records"),
                        "assumptions": "independent paths/role streams and seeds; deterministic context/weights/model fixed; pointwise Hoeffding bounds, Bonferroni180 calibration comparisons; three seeds insufficient for stable empirical variance"},
        "matched_jump_pairs": len(matches), "near_or_below_null_branches": int((primary.w1_post <= primary.null_w1_post).sum()),
        "case_selection": [{"reason": reason, **row[["dataset", "series", "window_id", "b", "token", "w1_fixed22_over_context_iqr", "ed_fixed22_over_context_iqr", "direct_token_jump_over_context_iqr", "q50"]].to_dict()} for reason, row in selected_cases],
        "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "limitations": ["two series per dataset, purposive diversity and local truncated eligible exports; no population prevalence or confirmatory inference", "no accuracy/causal-attention/BEAST/PELT claim", "event bounds condition on fixed weights and do not model between-series variation", "posthoc strongest/near-null cases are labeled and both ensembles shown"]}
    write_json(analysis / "summary.json", summary)
    print(json.dumps(jsonable({k: summary[k] for k in ("accounting", "resources", "coverage", "calibration")}), indent=2))


def plot_all(output, folder, windows, cells, primary, profiles, events, overlap, cases):
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    colors = dict(zip(windows, plt.get_cmap("tab10").colors))
    pdf = PdfPages(folder.parent / "PILOT_FIGURES.pdf")
    def save(fig, name):
        fig.tight_layout()
        fig.savefig(folder / (name + ".png"), dpi=145)
        pdf.savefig(fig)
        plt.close(fig)
    fig, axes = plt.subplots(3, 2, figsize=(12, 9))
    with np.load(output / "selected_contexts.npz", allow_pickle=False) as contexts:
        for axis, (wid, w) in zip(axes.flat, windows.items()):
            x = contexts[wid]
            axis.plot(np.arange(-512, 0), x, lw=1)
            axis.set_title(f"{w['dataset_id']}/{w['series_id']} ({w['stratum']}); IQR={w['context_iqr']:.5g}")
            axis.set_xlabel("coordinate relative to frozen forecast origin (future excluded)")
    save(fig, "01_contexts")
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    labels = [w["dataset_id"] + "/" + w["series_id"] for w in windows.values()]
    for axis, column in zip(axes.flat, ("w1_post", "ed_post", "w1_post_over_context_iqr", "ed_post_over_context_iqr")):
        axis.boxplot([primary[primary.window_id == wid][column] for wid in windows], tick_labels=labels, showfliers=True)
        axis.set_yscale("log")
        axis.tick_params(axis="x", rotation=35)
        axis.set_title(column + " (branches dependent within each series)")
    save(fig, "02_distances_raw_and_normalized")
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for axis, predictor in zip(axes.flat, ("signed_direct_token_jump_over_context_iqr", "direct_token_jump_over_context_iqr", "q50", "p_sel", "entropy_q50", "entropy_p_sel")):
        for wid, w in windows.items():
            frame = primary[primary.window_id == wid]
            axis.scatter(frame[predictor], frame.w1_fixed22_over_context_iqr, s=18, alpha=.75,
                         color=colors[wid], label=w["dataset_id"] + "/" + w["series_id"])
        axis.set_yscale("log")
        if "jump" in predictor:
            axis.set_xscale("symlog", linthresh=.01)
        axis.set_xlabel(predictor)
        axis.set_ylabel("strict fixed22 W1 / context IQR")
    axes[0, 0].legend(fontsize=7)
    save(fig, "03_effect_vs_jump_probability_entropy")
    fig, axes = plt.subplots(3, 2, figsize=(12, 9))
    for axis, (wid, w) in zip(axes.flat, windows.items()):
        frame = profiles[(profiles.window_id == wid) & profiles.primary]
        for _, group in frame.groupby(["b", "token"]):
            axis.plot(group.strict_horizon, group.w1_iqr, color=colors[wid], alpha=.15)
        medians = frame.groupby("strict_horizon")[["w1_iqr", "null_w1_iqr"]].median()
        axis.plot(medians.index, medians.w1_iqr, label="alternative median")
        axis.plot(medians.index, medians.null_w1_iqr, ls="--", color="black", label="same-token null median")
        axis.set_title(w["dataset_id"] + "/" + w["series_id"])
        axis.set_xlabel("strict horizon after fork; h<=22 common, later composition changes")
        axis.set_ylabel("W1 / context IQR")
    axes[0, 0].legend()
    save(fig, "04_horizon_profiles")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for axis, metric in zip(axes, ("w1", "ed")):
        for wid, w in windows.items():
            frame = primary[primary.window_id == wid]
            axis.scatter(frame[metric + "_fixed22_over_context_iqr"], frame[metric + "_post_over_context_iqr"],
                         color=colors[wid], s=18, label=w["series_id"])
        limits = axis.get_xlim()
        axis.plot(limits, limits, ls="--", color="black")
        axis.set_xscale("log")
        axis.set_yscale("log")
        axis.set_xlabel(metric + " fixed22 / IQR")
        axis.set_ylabel(metric + " full suffix / IQR")
    save(fig, "05_fixed22_vs_full")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for axis, baseline in zip(axes, ("persistent", "context_ar1")):
        for wid, w in windows.items():
            frame = primary[primary.window_id == wid]
            axis.scatter(frame[f"independent_null_{baseline}_w1_fixed22_iqr"], frame.w1_fixed22_over_context_iqr,
                         color=colors[wid], s=18, label=w["series_id"])
        limits = axis.get_xlim()
        axis.plot(limits, limits, ls="--", color="black")
        axis.set_xscale("log")
        axis.set_yscale("log")
        axis.set_xlabel(baseline + " translation of independent null: fixed22 W1/IQR")
        axis.set_ylabel("observed alternative: fixed22 W1/IQR")
    axes[0].legend(fontsize=7)
    save(fig, "05_numeric_propagation_comparators")
    for wid, w in windows.items():
        fig, axes = plt.subplots(5, 2, figsize=(12, 13), sharex=True, sharey=True)
        frame = events[(events.window_id == wid) & events.primary]
        direct = overlap[(overlap.window_id == wid) & overlap.primary]
        for i, threshold in enumerate(THRESHOLDS):
            for j, name in enumerate(("terminal", "last8")):
                axis = axes[i, j]
                points = frame[(frame.threshold == threshold) & (frame.outcome == name)].sort_values("position")
                axis.fill_between(points.position, points.lower, points.upper, alpha=.22, label="95% pointwise Hoeffding")
                axis.plot(points.position, points.probability, "o-", ms=3, label="primary estimator")
                extra = direct[(direct.threshold == threshold) & (direct.outcome == name)]
                axis.scatter(extra.position, extra.direct_probability, marker="x", color="red", label="independent overlap N60")
                axis.axvline(10.5, color="gray", ls="--")
                axis.set_title(f"{name} absolute deviation/IQR > {threshold:g}")
                axis.set_ylim(-.03, 1.03)
                axis.set_xticks(range(0, 16, 3))
        axes[0, 0].legend(fontsize=7)
        fig.suptitle(w["dataset_id"] + "/" + w["series_id"] + ": same fixed outcome at every P; boundary P10/P11", y=.995)
        save(fig, "06_outcomes_" + w["dataset_id"] + "_" + w["series_id"])
    for wid in sorted({c[0]["window_id"] for c in cells if not c[0]["primary"]}):
        frame = overlap[overlap.window_id == wid]
        fig, axes = plt.subplots(1, 3, figsize=(14, 5), sharey=True)
        for axis, position in zip(axes, (0, 9, 10)):
            for offset, (seed, group) in zip((-.18, 0., .18), frame[frame.position == position].groupby("seed")):
                group = group.sort_values(["outcome", "threshold"])
                axis.errorbar(np.arange(10) + offset, group.gap_primary_minus_direct, yerr=group.hoeffding_radius,
                              fmt="o", ms=3, alpha=.7, label=str(seed))
            axis.axhline(0, color="black", lw=.8)
            axis.set_title(f"P{position}: primary - independent direct")
            axis.set_xticks(range(10), ["L" + str(t) for t in THRESHOLDS] + ["T" + str(t) for t in THRESHOLDS], rotation=70)
        axes[0].legend(title="independent root seeds")
        axes[0].set_ylabel("event probability difference; 95% pointwise Hoeffding bounds")
        w = windows[wid]
        save(fig, "07_calibration_" + w["dataset_id"])
    for index, (reason, row) in enumerate(cases):
        cell, marker, result, validation = next(c for c in cells if c[0]["primary"] and c[0]["window_id"] == row.window_id)
        b = int(row.b)
        fork = result["forks"][b]
        reference = validation["lookup"][(b, "reference", fork["greedy_token"])][1]["values"]
        alternative = validation["lookup"][(b, "alternative", int(row.token))][1]["values"]
        fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
        for axis, name, values, color in zip(axes, ("independent greedy reference", "forced alternative"), (reference, alternative), ("tab:blue", "tab:orange")):
            scaled = (values - np.asarray(result["greedy_values"])[None]) / result["context_iqr"]
            axis.plot(np.arange(32), scaled.T, color=color, alpha=.18, lw=.7)
            axis.fill_between(np.arange(32), np.quantile(scaled, .1, axis=0), np.quantile(scaled, .9, axis=0), color=color, alpha=.15)
            axis.plot(np.median(scaled, axis=0), color=color, lw=2, label="median; band10..90%; all20 paths")
            axis.axvline(b, color="black", ls="--")
            axis.set_title(name)
            axis.set_xlabel("forecast coordinate; forced b excluded from reported distances")
            axis.set_ylabel("numeric value - greedy / context IQR")
            axis.legend(fontsize=7)
        fig.suptitle(f"{row.dataset}/{row.series} b={b} token={row.token}; {reason}", y=.995)
        save(fig, f"08_morphology_{index:02d}")
    pdf.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    analyze(args.output.resolve())
