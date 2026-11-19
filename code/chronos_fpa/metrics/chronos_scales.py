"""Pure NumPy/pandas score normalization and window diagnostics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from chronos_score import METRIC_VERSION, SCORE_VERSION, SCORE_WEIGHTS, compute_forking_scores
from research_schema import is_base_branch


DEFAULT_BRANCH_STEPS = [0, 4, 8, 16]
DEFAULT_BUNDLE_CONTINUATION_RANKS = [1, 5, 10]


RAW_TOKEN_SCORE_COL = "token_bin_forking_score"
RAW_SCORE_COL = "progressive_token_bin_forking_score"
CONTEXT_IQR_TOKEN_SCORE_COL = "context_iqr_scaled_token_bin_forking_score"
CONTEXT_IQR_SCORE_COL = "context_iqr_scaled_progressive_token_bin_forking_score"
WINDOW_SCALE_TOKEN_SCORE_COL = "window_scaled_token_bin_forking_score"
WINDOW_SCALE_SCORE_COL = "window_scaled_progressive_token_bin_forking_score"
NORMALIZED_TOKEN_SCORE_COL = CONTEXT_IQR_TOKEN_SCORE_COL
NORMALIZED_SCORE_COL = CONTEXT_IQR_SCORE_COL
RAW_SCORE_OVER_WINDOW_SCALE_COL = f"{RAW_SCORE_COL}_over_window_scale"
NORMALIZED_SCORE_SPECS = [
    ("context_iqr", CONTEXT_IQR_TOKEN_SCORE_COL, CONTEXT_IQR_SCORE_COL),
    ("context_std", "context_std_scaled_token_bin_forking_score", "context_std_scaled_progressive_token_bin_forking_score"),
    ("context_range", "context_range_scaled_token_bin_forking_score", "context_range_scaled_progressive_token_bin_forking_score"),
    ("gt_iqr", "gt_iqr_scaled_token_bin_forking_score", "gt_iqr_scaled_progressive_token_bin_forking_score"),
    ("gt_std", "gt_std_scaled_token_bin_forking_score", "gt_std_scaled_progressive_token_bin_forking_score"),
    ("gt_range", "gt_range_scaled_token_bin_forking_score", "gt_range_scaled_progressive_token_bin_forking_score"),
    ("gt_rms", "gt_rms_scaled_token_bin_forking_score", "gt_rms_scaled_progressive_token_bin_forking_score"),
    ("window_scale", WINDOW_SCALE_TOKEN_SCORE_COL, WINDOW_SCALE_SCORE_COL),
]
DEFAULT_SCORE_COL = NORMALIZED_SCORE_COL
PRIMARY_SCALE_COL = "context_iqr"
BASE_ERROR_COL = "base_mae_over_context_iqr"
NORMALIZATION_SCALE_COLS = [
    scale_col for scale_col, _, _ in NORMALIZED_SCORE_SPECS
]
SCORE_CONVENTIONS = {
    "metric_version": METRIC_VERSION,
    "score_version": SCORE_VERSION,
    "default_score_column": DEFAULT_SCORE_COL,
    "normalization_scale": PRIMARY_SCALE_COL,
    "automatic_scale_fallback": False,
    "base_quality_error_column": BASE_ERROR_COL,
    "undefined_base_quality": "nan",
    "temporal_alias_scale": PRIMARY_SCALE_COL,
    "peak_timing_ties": "undefined_exact_ties",
}
SCALE_DIAGNOSTIC_COLS = [
    "gt_mean_abs",
    "gt_std",
    "gt_rms",
    "gt_range",
    "gt_iqr",
    "context_mean_abs",
    "context_std",
    "context_rms",
    "context_range",
    "context_iqr",
    "window_scale",
    "base_mae",
]
BASE_QUALITY_SCALE_COLS = [
    "gt_mean_abs",
    "window_scale",
    "context_iqr",
    "context_std",
    "context_range",
    "gt_iqr",
    "gt_std",
    "gt_range",
]


def _mean_or_nan(values) -> float:
    arr = np.asarray(values, dtype=np.float64)
    return float(np.mean(arr)) if arr.size else np.nan


def _temporal_shift_metrics(law, width_shift, branch_step: int, eps=1e-12) -> dict:
    """Summarize how branch shift evolves after the forced token."""
    abs_law = np.abs(np.asarray(law, dtype=np.float64))
    width_shift = np.asarray(width_shift, dtype=np.float64)
    if abs_law.size == 0:
        return {
            "early_law_shift": np.nan,
            "mid_law_shift": np.nan,
            "late_law_shift": np.nan,
            "area_under_law_shift": np.nan,
            "peak_law_shift": np.nan,
            "peak_forecast_step": np.nan,
            "peak_relative_step_after_branch": np.nan,
            "peak_delay_fraction": np.nan,
            "peak_timing_ambiguous": True,
            "late_over_early_law": np.nan,
            "persistence_ratio": np.nan,
            "convergence_ratio": np.nan,
            "early_widening_10_90": np.nan,
            "mid_widening_10_90": np.nan,
            "late_widening_10_90": np.nan,
        }

    law_chunks = np.array_split(abs_law, 3)
    widening_chunks = np.array_split(np.clip(width_shift, 0.0, None), 3)
    peak_idx = int(np.argmax(abs_law))
    peak = float(abs_law[peak_idx])
    ambiguous_peak = int(np.count_nonzero(abs_law == peak)) != 1
    first = float(abs_law[0])
    last = float(abs_law[-1])
    early = _mean_or_nan(law_chunks[0])
    late = _mean_or_nan(law_chunks[-1])
    denom_steps = max(1, abs_law.size - 1)

    return {
        "early_law_shift": early,
        "mid_law_shift": _mean_or_nan(law_chunks[1]),
        "late_law_shift": late,
        "area_under_law_shift": float(np.sum(abs_law)),
        "peak_law_shift": peak,
        "peak_forecast_step": np.nan if ambiguous_peak else int(branch_step + peak_idx),
        "peak_relative_step_after_branch": np.nan if ambiguous_peak else peak_idx,
        "peak_delay_fraction": np.nan if ambiguous_peak else float(peak_idx / denom_steps),
        "peak_timing_ambiguous": ambiguous_peak,
        "late_over_early_law": np.nan if early <= eps else float(late / early),
        "persistence_ratio": np.nan if peak <= eps else float(last / peak),
        "convergence_ratio": np.nan if first <= eps else float(last / first),
        "early_widening_10_90": _mean_or_nan(widening_chunks[0]),
        "mid_widening_10_90": _mean_or_nan(widening_chunks[1]),
        "late_widening_10_90": _mean_or_nan(widening_chunks[-1]),
    }


def _ratio(numerator, denominator, eps: float = 1e-12) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or denominator <= eps:
        return np.nan
    return float(numerator / denominator)


def _iqr(values: np.ndarray) -> float:
    if len(values) == 0:
        return np.nan
    return float(np.quantile(values, 0.75) - np.quantile(values, 0.25))


def compute_base_forecast_quality(
    base_values,
    y_true,
    context_values=None,
    eps: float = 1e-12,
) -> dict:
    """Compare Chronos greedy/base path against the window future."""
    pred = np.asarray(base_values, dtype=np.float64).reshape(-1)
    true = np.asarray(y_true, dtype=np.float64).reshape(-1)
    context = (
        np.asarray(context_values, dtype=np.float64).reshape(-1)
        if context_values is not None
        else np.asarray([], dtype=np.float64)
    )
    context = context[np.isfinite(context)]
    true_finite = true[np.isfinite(true)]

    context_mean_abs = float(np.mean(np.abs(context))) if len(context) else np.nan
    context_std = float(np.std(context)) if len(context) else np.nan
    context_rms = float(np.sqrt(np.mean(context ** 2))) if len(context) else np.nan
    context_range = float(np.max(context) - np.min(context)) if len(context) else np.nan
    context_iqr = _iqr(context)
    gt_mean_abs_all = float(np.mean(np.abs(true_finite))) if len(true_finite) else np.nan
    gt_std = float(np.std(true_finite)) if len(true_finite) else np.nan
    gt_rms_all = float(np.sqrt(np.mean(true_finite ** 2))) if len(true_finite) else np.nan
    gt_range_all = (
        float(np.max(true_finite) - np.min(true_finite)) if len(true_finite) else np.nan
    )
    gt_iqr_all = _iqr(true_finite)
    scale_candidates = [
        gt_mean_abs_all,
        gt_std,
        gt_rms_all,
        gt_range_all,
        gt_iqr_all,
        context_mean_abs,
        context_std,
        context_rms,
        context_range,
        context_iqr,
    ]
    finite_scales = [
        value for value in scale_candidates if np.isfinite(value) and value > eps
    ]
    window_scale = float(max(finite_scales)) if finite_scales else np.nan

    n = min(len(pred), len(true))
    base_payload = {
        "gt_mean_abs": gt_mean_abs_all,
        "gt_std": gt_std,
        "gt_rms": gt_rms_all,
        "gt_range": gt_range_all,
        "gt_iqr": gt_iqr_all,
        "context_mean_abs": context_mean_abs,
        "context_std": context_std,
        "context_rms": context_rms,
        "context_range": context_range,
        "context_iqr": context_iqr,
        "window_scale": window_scale,
    }
    if n == 0:
        payload = dict(base_payload)
        payload.update(
            {
                "base_mae": np.nan,
                "base_rmse": np.nan,
                **{f"base_mae_over_{col}": np.nan for col in BASE_QUALITY_SCALE_COLS},
            }
        )
        return payload

    err = pred[:n] - true[:n]
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    gt_mean_abs = float(np.mean(np.abs(true[:n])))
    gt_std = float(np.std(true[:n]))
    gt_rms = float(np.sqrt(np.mean(true[:n] ** 2)))
    gt_range = float(np.max(true[:n]) - np.min(true[:n]))
    gt_iqr = _iqr(true[:n])
    payload = dict(base_payload)
    payload.update(
        {
            "base_mae": mae,
            "base_rmse": rmse,
            "gt_mean_abs": gt_mean_abs,
            "gt_std": gt_std,
            "gt_rms": gt_rms,
            "gt_range": gt_range,
            "gt_iqr": gt_iqr,
        }
    )
    for col in BASE_QUALITY_SCALE_COLS:
        payload[f"base_mae_over_{col}"] = _ratio(mae, payload[col], eps=eps)
    return payload


def _attach_base_quality(frame: pd.DataFrame, quality: dict) -> pd.DataFrame:
    out = frame.copy()
    for key, value in quality.items():
        out[key] = value
    return out


def _positive_scale(values: pd.Series, eps: float = 1e-12) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.where(np.isfinite(numeric) & (numeric > eps))


def _attach_base_forecast_bad(frame: pd.DataFrame, threshold: float = 1.0) -> pd.DataFrame:
    """Undefined context-IQR quality must not be counted as a good forecast."""
    out = frame.copy()
    error = pd.to_numeric(out[BASE_ERROR_COL], errors="coerce")
    out["base_forecast_bad"] = error.ge(threshold).astype(object).where(np.isfinite(error), np.nan)
    return out


def _attach_normalized_branch_scores(
    frame: pd.DataFrame,
    eps: float = 1e-12,
) -> pd.DataFrame:
    out = frame.copy()
    metrics = [
        "mean_law_shift",
        "max_law_shift",
        "max_widening_10_90",
        RAW_TOKEN_SCORE_COL,
        RAW_SCORE_COL,
    ]
    for metric in metrics:
        if metric not in out.columns:
            continue
        metric_values = pd.to_numeric(out[metric], errors="coerce")
        for denom in SCALE_DIAGNOSTIC_COLS:
            if denom not in out.columns:
                continue
            denom_values = _positive_scale(out[denom], eps=eps)
            out[f"{metric}_over_{denom}"] = (
                metric_values / denom_values
            )

    required = set(SCORE_WEIGHTS).union({"last_over_max_law", "monotonic_growth_fraction"})
    if required.issubset(out.columns):
        for denom_col, token_col, progressive_col in NORMALIZED_SCORE_SPECS:
            if denom_col not in out.columns:
                continue
            unit_scale = _positive_scale(out[denom_col], eps=eps)
            out[token_col], out[progressive_col] = compute_forking_scores(out, unit_scale)
    return out


def resolve_score_column(summary_df: pd.DataFrame, requested: str | None = None) -> str:
    """Choose context IQR unless an explicit, usable score column is requested.

    Undefined rows may coexist with finite scores, but a populated frame with
    no finite score in the selected column is an error, never a scale fallback.
    """
    requested = requested.strip() if requested else None
    selected = requested or DEFAULT_SCORE_COL
    if summary_df.empty:
        return selected
    if selected not in summary_df.columns:
        raise ValueError(f"Score column {selected!r} is missing; select an available score explicitly.")
    values = pd.to_numeric(summary_df[selected], errors="coerce")
    if not np.isfinite(values).any():
        raise ValueError(f"Score column {selected!r} has no finite values.")
    return selected


def normalization_scale_for_score(score_col: str) -> str | None:
    for scale, token, progressive in NORMALIZED_SCORE_SPECS:
        if score_col in (token, progressive) or score_col.startswith(f"{scale}_scaled_"):
            return scale
    if score_col == RAW_SCORE_OVER_WINDOW_SCALE_COL:
        return "window_scale"
    return None


def _attach_temporal_forking_scores(
    frame: pd.DataFrame,
    eps: float = 1e-12,
) -> pd.DataFrame:
    """Add separated temporal scores for instant/persistent/progressive shifts."""
    out = frame.copy()
    required = {
        "early_law_shift",
        "mid_law_shift",
        "late_law_shift",
        "peak_law_shift",
        "persistence_ratio",
        "late_over_early_law",
        "monotonic_growth_fraction",
    }
    if not required.issubset(out.columns):
        return out

    early = pd.to_numeric(out["early_law_shift"], errors="coerce")
    mid = pd.to_numeric(out["mid_law_shift"], errors="coerce")
    late = pd.to_numeric(out["late_law_shift"], errors="coerce")
    peak = pd.to_numeric(out["peak_law_shift"], errors="coerce")
    persistence = pd.to_numeric(out["persistence_ratio"], errors="coerce").clip(0.0, 1.0)
    late_over_early = pd.to_numeric(out["late_over_early_law"], errors="coerce")
    monotonic = pd.to_numeric(out["monotonic_growth_fraction"], errors="coerce").clip(0.0, 1.0)

    for scale_col in NORMALIZATION_SCALE_COLS:
        if scale_col not in out.columns:
            continue
        scale = _positive_scale(out[scale_col], eps=eps)
        prefix = scale_col
        out[f"early_law_shift_over_{prefix}"] = early / scale
        out[f"mid_law_shift_over_{prefix}"] = mid / scale
        out[f"late_law_shift_over_{prefix}"] = late / scale
        out[f"peak_law_shift_over_{prefix}"] = peak / scale
        out[f"{prefix}_scaled_instant_forking_score"] = out[f"early_law_shift_over_{prefix}"]
        out[f"{prefix}_scaled_persistent_forking_score"] = (
            out[f"late_law_shift_over_{prefix}"] * (0.5 + 0.5 * persistence)
        )
        out[f"{prefix}_scaled_progressive_forking_score"] = (
            ((late - early).clip(lower=0.0) / scale)
            * (0.5 + 0.5 * monotonic)
            * late_over_early.where(late_over_early > 1.0, 1.0).clip(upper=10.0)
        )

    for kind in ("instant", "persistent", "progressive"):
        source = f"context_iqr_scaled_{kind}_forking_score"
        out[f"{kind}_forking_score"] = out[source] if source in out.columns else np.nan
    return out


def _attach_topology_regime(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """Classify local token-distribution topology with simple interpretable rules."""
    out = frame.copy()
    prob_col = "token_probability" if "token_probability" in out.columns else "initial_token_probability"
    if not {"normalized_token_entropy", "top1_top2_margin", prob_col}.issubset(out.columns):
        return out

    entropy = pd.to_numeric(out["normalized_token_entropy"], errors="coerce")
    margin = pd.to_numeric(out["top1_top2_margin"], errors="coerce")
    prob = pd.to_numeric(out[prob_col], errors="coerce")

    base_mask = is_base_branch(out)

    high_entropy = entropy >= 0.20
    low_entropy = entropy <= 0.05
    low_margin = margin <= 0.05
    high_margin = margin >= 0.75
    improbable = prob <= 1e-3
    plausible = prob >= 0.05

    out["topology_entropy_zone"] = np.select(
        [high_entropy, low_entropy],
        ["high_entropy", "low_entropy"],
        default="mid_entropy",
    )
    out["topology_margin_zone"] = np.select(
        [low_margin, high_margin],
        ["low_margin", "high_margin"],
        default="mid_margin",
    )
    out["forced_token_likelihood_zone"] = np.select(
        [improbable, plausible],
        ["improbable", "plausible"],
        default="low_to_mid_probability",
    )
    out["topology_regime"] = np.select(
        [
            base_mask,
            high_entropy & low_margin & plausible,
            low_entropy & high_margin & improbable,
            high_entropy & low_margin,
            low_entropy & high_margin,
        ],
        [
            "base_branch",
            "uncertain_plausible",
            "confident_improbable",
            "uncertain_competitive",
            "confident_stress",
        ],
        default="mixed_topology",
    )
    return out
