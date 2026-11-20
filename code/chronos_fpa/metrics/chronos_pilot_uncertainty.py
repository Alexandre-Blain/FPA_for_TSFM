"""Conditional Monte Carlo diagnostics; no cross-series or change-point inference."""
from __future__ import annotations

import numpy as np

from chronos_outcomes import weighted_events


def event_uncertainty(groups, weights, alpha=.05):
    """Pointwise weighted Hoeffding bounds for independent Bernoulli paths.

    Weights/contexts/model are fixed. The bounds are deliberately conservative,
    remain nonzero for all-zero events, and are not simultaneous over events.
    """
    result = weighted_events(groups, weights)
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one")
    proxy = float(sum(float(w) ** 2 / len(a) for w, a in zip(weights, groups)))
    radius = float(np.sqrt(np.log(2 / alpha) * proxy / 2))
    probability = result["event_probability"]
    return {**result, "hoeffding_variance_proxy": proxy, "hoeffding_radius": radius,
            "pointwise_lower": np.maximum(0., probability - radius),
            "pointwise_upper": np.minimum(1., probability + radius), "alpha": alpha}


def independent_difference(first, second, alpha=.05):
    gap = first["event_probability"] - second["event_probability"]
    se = np.sqrt(first["conditional_mc_se"] ** 2 + second["conditional_mc_se"] ** 2)
    radius = float(np.sqrt(np.log(2 / alpha) / 2 *
                           (first["hoeffding_variance_proxy"] + second["hoeffding_variance_proxy"])))
    return {"difference": gap, "conditional_mc_se": se, "hoeffding_radius": radius,
            "pointwise_lower": gap - radius, "pointwise_upper": gap + radius}


def reused_component_covariance(events, weight):
    events = np.asarray(events, dtype=float)
    if len(events) < 2:
        raise ValueError("At least two paths required")
    return float(weight) * events.var(axis=0, ddof=1) / len(events)
