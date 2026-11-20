"""Fixed-window outcome events and q50 conditional-mixture estimators."""
from __future__ import annotations

import numpy as np

from chronos_distances import compare_fork_samples


THRESHOLDS = np.array([.05, .10, .25, .50, 1.00])


def window_outcomes(paths, greedy, context_iqr):
    paths, greedy = np.asarray(paths), np.asarray(greedy)
    if paths.ndim != 2 or paths.shape[1] != 32 or greedy.shape != (32,):
        raise ValueError("These fixed outcomes require complete H32 paths and greedy future")
    if not np.isfinite(paths).all() or not np.isfinite(greedy).all():
        raise ValueError("Nonfinite outcome inputs")
    if not np.isfinite(context_iqr) or context_iqr <= 1e-12:
        raise ValueError("Outcome normalization requires valid context IQR; no fallback")
    delta = np.abs(paths.astype(float) - greedy.astype(float)) / context_iqr
    terminal, last8 = delta[:, 31], delta[:, 24:32].mean(axis=1)
    events = np.stack((terminal[:, None] > THRESHOLDS, last8[:, None] > THRESHOLDS), axis=1)
    return {"events": events, "terminal_value": paths[:, 31],
            "terminal_abs_delta_iqr": terminal, "last8_mean_abs_delta_iqr": last8}


def weighted_events(event_ensembles, weights):
    weights = np.asarray(weights, dtype=float)
    if weights.ndim != 1 or len(weights) != len(event_ensembles) or not len(weights):
        raise ValueError("One weight is required per conditional ensemble")
    if not np.isfinite(weights).all() or (weights < 0).any() or not np.isclose(weights.sum(), 1., atol=1e-10, rtol=0):
        raise ValueError("Mixture weights must be nonnegative and sum to one")
    arrays = [np.asarray(a, dtype=float) for a in event_ensembles]
    if any(a.ndim != 3 or not len(a) or a.shape[1:] != arrays[0].shape[1:]
           or not np.isin(a, [0, 1]).all() for a in arrays):
        raise ValueError("Expected nonempty binary event ensembles of a common shape")
    means = np.stack([a.mean(axis=0) for a in arrays])
    probability = np.tensordot(weights, means, axes=1)
    # Conditional Monte Carlo SE, given fixed estimated fork weights, not series uncertainty.
    variances = [a.var(axis=0, ddof=1) / len(a) if len(a) > 1 else np.full(a.shape[1:], np.nan)
                 for a in arrays]
    mc_variance = np.tensordot(weights ** 2, np.stack(variances), axes=1)
    return {"event_probability": probability, "conditional_mc_se": np.sqrt(mc_variance)}


def compare_fixed22_and_full(reference, alternative, branch_step, context):
    reference, alternative = np.asarray(reference), np.asarray(alternative)
    if reference.shape[1] - branch_step - 1 < 22:
        raise ValueError("Fewer than 22 strict post-fork coordinates")
    full, profile = compare_fork_samples(reference, alternative, branch_step, context)
    fixed, _ = compare_fork_samples(reference[:, :branch_step + 23], alternative[:, :branch_step + 23], branch_step, context)
    values = dict(full)
    for name in ("w1_post", "ed_post", "w1_post_over_context_iqr", "ed_post_over_context_iqr"):
        values[name.replace("_post", "_fixed22")] = fixed[name]
    signed = float(alternative[0, branch_step] - reference[0, branch_step])
    values["signed_direct_token_jump"] = signed
    values["signed_direct_token_jump_over_context_iqr"] = signed / full["distance_context_iqr"] if full["distance_context_iqr_valid"] else np.nan
    return values, profile
