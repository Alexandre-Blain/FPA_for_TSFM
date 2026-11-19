"""Shared Chronos FPA score definition, without model/runtime dependencies."""
from __future__ import annotations

import pandas as pd


SCORE_VERSION = "chronos_fpa_context_iqr_v1"
METRIC_VERSION = "chronos_fpa_metrics_v2_explicit_scale"
SCORE_WEIGHTS = {
    "mean_law_shift": 0.40,
    "max_law_shift": 0.25,
    "positive_law_amplification": 0.15,
    "shape_break": 0.10,
    "max_widening_10_90": 0.10,
}


def compute_forking_scores(frame: pd.DataFrame, unit_scale=1.0):
    """Return the mixed-component token score and its persistence-weighted score.

    Only dimensional shifts are divided by unit_scale; amplification and shape
    remain dimensionless. Operation order matches the historical formula.
    """
    values = {key: pd.to_numeric(frame[key], errors="coerce") for key in SCORE_WEIGHTS}
    token = (
        SCORE_WEIGHTS["mean_law_shift"] * (values["mean_law_shift"] / unit_scale)
        + SCORE_WEIGHTS["max_law_shift"] * (values["max_law_shift"] / unit_scale)
        + SCORE_WEIGHTS["positive_law_amplification"] * values["positive_law_amplification"]
        + SCORE_WEIGHTS["shape_break"] * values["shape_break"]
        + SCORE_WEIGHTS["max_widening_10_90"] * (values["max_widening_10_90"] / unit_scale)
    )
    last_over_max = pd.to_numeric(frame["last_over_max_law"], errors="coerce").clip(0.0, 1.0)
    monotonic = pd.to_numeric(frame["monotonic_growth_fraction"], errors="coerce").clip(0.0, 1.0)
    progressive = token * (0.5 + 0.5 * last_over_max) * (0.5 + 0.5 * monotonic)
    return token, progressive
