"""Paper 1 distances on empirical, strictly post-fork numeric ensembles."""
from __future__ import annotations

import numpy as np
import pandas as pd

DISTANCE_VERSION = "chronos_strict_suffix_w1_ed_v1"
IQR_EPS = 1e-12
DISTANCE_CONVENTIONS = {
    "version": DISTANCE_VERSION, "suffix_start": "b+1", "suffix_end_exclusive": "H",
    "w1": "exact equally weighted empirical marginal W1, then horizon mean",
    "energy_estimator": "V-statistic including diagonal pairs",
    "energy_ground_distance": "euclidean_norm/sqrt(post_fork_length)",
    "energy_square_root": False, "normalization": "finite_context_iqr",
    "invalid_scale_leq": IQR_EPS, "empty_suffix": "undefined",
}


def _ensemble(values):
    if hasattr(values, "detach"):
        values = values.detach().cpu().numpy()
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or array.shape[0] == 0 or not np.isfinite(array).all():
        raise ValueError("Expected a finite, nonempty sample axis with shape [samples, horizons]")
    return array


def _paired(a, b):
    a, b = _ensemble(a), _ensemble(b)
    if a.shape[1] != b.shape[1]:
        raise ValueError("Ensembles must have the same horizon length")
    return a, b


def empirical_w1_by_horizon(a, b):
    """Exact equally weighted empirical W1, also for unequal sample counts."""
    a, b = _paired(a, b)
    a, b = np.sort(a, axis=0), np.sort(b, axis=0)
    n, m = len(a), len(b)
    if n == m:
        return np.mean(np.abs(a - b), axis=0)
    # Integrate the two stepwise empirical inverse CDFs on their common grid.
    grid = np.unique(np.concatenate((np.arange(n + 1) / n, np.arange(m + 1) / m)))
    mid = (grid[:-1] + grid[1:]) / 2
    ia = np.minimum((mid * n).astype(int), n - 1)
    ib = np.minimum((mid * m).astype(int), m - 1)
    return np.sum(np.abs(a[ia] - b[ib]) * np.diff(grid)[:, None], axis=0)


def energy_distance_v(a, b):
    """Energy functional V-statistic with RMS Euclidean ground distance, no root.

    Diagonal within-sample pairs are included. Independent equal-law ensembles
    need not yield zero; an empty downstream horizon is undefined (NaN).
    """
    a, b = _paired(a, b)
    length = a.shape[1]
    if length == 0:
        return np.nan

    def pair_mean(x, y):
        # Rowwise computation avoids an [n, m, L] temporary.
        return float(np.mean([np.mean(np.linalg.norm(y - row, axis=1) / np.sqrt(length)) for row in x]))

    cross, within_a, within_b = pair_mean(a, b), pair_mean(a, a), pair_mean(b, b)
    value = 2 * cross - within_a - within_b
    tolerance = 64 * np.finfo(float).eps * max(cross, within_a, within_b, 1.)
    if value < -tolerance:
        raise ArithmeticError("Negative Energy V-statistic beyond numerical roundoff")
    return float(max(0., value))


def context_iqr_scale(context):
    values = np.asarray(context, dtype=np.float64).reshape(-1)
    finite = values[np.isfinite(values)]
    scale = float(np.quantile(finite, .75) - np.quantile(finite, .25)) if len(finite) else np.nan
    valid = bool(np.isfinite(scale) and scale > IQR_EPS)
    reason = "" if valid else "nonfinite_context_iqr" if not np.isfinite(scale) else "near_zero_context_iqr"
    return scale, valid, reason


def compare_fork_samples(reference, alternative, branch_step, context):
    """Separate the direct coordinate b from the strict suffix b+1:H."""
    reference, alternative = _paired(reference, alternative)
    horizon = reference.shape[1]
    if not 0 <= branch_step < horizon:
        raise ValueError("branch_step is outside the forecasting horizon")
    for paths in (reference, alternative):
        if not np.equal(paths[:, branch_step], paths[0, branch_step]).all():
            raise ValueError("The forced coordinate must be constant within each ensemble")
    if not np.equal(reference[:, :branch_step], reference[0, :branch_step]).all() or not np.equal(
        alternative[:, :branch_step], reference[0, :branch_step]
    ).all():
        raise ValueError("All samples must share the same prefix before the fork")
    a, b = reference[:, branch_step + 1:], alternative[:, branch_step + 1:]
    w1 = empirical_w1_by_horizon(a, b)
    scale, valid, reason = context_iqr_scale(context)
    direct = float(abs(reference[0, branch_step] - alternative[0, branch_step]))
    values = {
        "distance_version": DISTANCE_VERSION,
        "post_fork_length": horizon - branch_step - 1,
        "post_fork_defined": a.shape[1] > 0,
        "distance_context_iqr": scale,
        "distance_context_iqr_valid": valid,
        "distance_scale_invalid_reason": reason,
        "direct_token_jump": direct,
        "w1_post": float(w1.mean()) if w1.size else np.nan,
        "ed_post": energy_distance_v(a, b),
    }
    for name in ("direct_token_jump", "w1_post", "ed_post"):
        values[f"{name}_over_context_iqr"] = values[name] / scale if valid else np.nan
    return values, w1


def attach_sampled_fork_metrics(decoded, steps, summary, context):
    """Add distinct distance columns; never replace the historical quantile score."""
    reference = decoded["branches"][decoded["base_token_at_branch"]]["sample_values"]
    position = decoded["branch_step"]
    null, null_w1 = compare_fork_samples(reference, decoded["same_token_null"]["sample_values"], position, context)
    rows, profiles = [], {}
    for token, branch in decoded["branches"].items():
        row, w1 = compare_fork_samples(reference, branch["sample_values"], position, context)
        row.update(token_id=token, token_sampling_probability=branch["alternative"].sampling_probability)
        for name in ("w1_post", "ed_post", "w1_post_over_context_iqr", "ed_post_over_context_iqr"):
            row[f"same_token_null_{name}"] = null[name]
        rows.append(row)
        profiles[token] = w1
    result_steps, result_summary = steps.copy(), summary.copy()
    metrics = pd.DataFrame(rows).set_index("token_id")
    for column in metrics:
        result_summary[column] = result_summary.token_id.map(metrics[column])
    for column in ("w1_post_h", "w1_post_h_over_context_iqr", "same_token_null_w1_post_h", "same_token_null_w1_post_h_over_context_iqr"):
        result_steps[column] = np.nan
    for token, w1 in profiles.items():
        mask = result_steps.token_id.eq(token) & result_steps.forecast_step.gt(position)
        # Existing step rows are in forecast-step order within each branch.
        result_steps.loc[mask, "w1_post_h"] = w1
        result_steps.loc[mask, "same_token_null_w1_post_h"] = null_w1
        if null["distance_context_iqr_valid"]:
            scale = null["distance_context_iqr"]
            result_steps.loc[mask, "w1_post_h_over_context_iqr"] = w1 / scale
            result_steps.loc[mask, "same_token_null_w1_post_h_over_context_iqr"] = null_w1 / scale
    return result_steps, result_summary
