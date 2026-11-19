from __future__ import annotations

import numpy as np
import pandas as pd

from chronos_scales import _temporal_shift_metrics
from chronos_score import SCORE_WEIGHTS, compute_forking_scores


def _to_numpy(x):
    if hasattr(x, "detach"):
        return x.detach().cpu().numpy()
    return np.asarray(x)


def _safe_corr(x, y, eps=1e-12):
    """Constant paths correlate as 1 if equal, 0 otherwise; retain roundoff."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xc = x - x.mean()
    yc = y - y.mean()
    sx = np.sqrt(np.sum(xc ** 2))
    sy = np.sqrt(np.sum(yc ** 2))
    if sx < eps or sy < eps:
        return 1.0 if np.allclose(x, y, atol=1e-10) else 0.0
    return float(np.sum(xc * yc) / (sx * sy))


def analyze_chronos_token_branches(decode_out, base_token_policy="forced_base"):
    """Build per-step metrics for Chronos token-bin FPA.

    The base distribution is the branch that forces the greedy/base token at
    `branch_step` when available. This matches the FPA comparison ot,w vs
    ot,w*, rather than comparing against a deterministic greedy trajectory only.
    """
    branch_step = int(decode_out["branch_step"])
    base_token = int(decode_out["base_token_at_branch"])
    branches = decode_out["branches"]

    if base_token_policy != "forced_base":
        raise ValueError("Only base_token_policy='forced_base' is currently supported.")
    if base_token not in branches:
        raise ValueError(
            "The base token branch is missing. Run decode_with_token_bin_intervention "
            "with include_base_token_branch=True."
        )

    q_base = _to_numpy(branches[base_token]["quantiles"])
    base_median = q_base[:, 4]
    base_width = q_base[:, 8] - q_base[:, 0]

    rows = []
    for token_id, branch in branches.items():
        alt = branch["alternative"]
        q = _to_numpy(branch["quantiles"])
        med = q[:, 4]
        width = q[:, 8] - q[:, 0]
        law_step = np.mean(np.abs(q - q_base), axis=1)
        median_shift = np.abs(med - base_median)
        width_shift = width - base_width

        for h in range(q.shape[0]):
            rows.append(
                {
                    "branch_step": branch_step,
                    "forecast_step": h,
                    "relative_step_after_branch": h - branch_step,
                    "token_id": int(token_id),
                    "token_rank": int(alt.rank),
                    "token_probability": float(alt.probability),
                    "token_surprisal": float(alt.token_surprisal),
                    "top1_probability": float(alt.top1_probability),
                    "top2_probability": float(alt.top2_probability),
                    "top1_top2_margin": float(alt.top1_top2_margin),
                    "token_entropy": float(alt.token_entropy),
                    "normalized_token_entropy": float(alt.normalized_token_entropy),
                    "top_k_probability_mass": float(alt.top_k_probability_mass),
                    "token_value_unit_scale": float(alt.value),
                    "is_base_token": bool(alt.is_base_token),
                    "base_token_id": base_token,
                    "law_shift_h": float(law_step[h]),
                    "median_shift_h": float(median_shift[h]),
                    "width_shift_10_90_h": float(width_shift[h]),
                    "base_q10": float(q_base[h, 0]),
                    "base_q50": float(q_base[h, 4]),
                    "base_q90": float(q_base[h, 8]),
                    "branch_q10": float(q[h, 0]),
                    "branch_q50": float(q[h, 4]),
                    "branch_q90": float(q[h, 8]),
                }
            )

    return pd.DataFrame(rows)


def _summarize_branch_components(grp, eps=1e-12):
    """Shared scientific summary for token-ID and named branches."""
    grp = grp.sort_values("forecast_step")
    post = grp[grp["relative_step_after_branch"] >= 0].copy()
    if post.empty:
        post = grp.copy()

    law = post["law_shift_h"].astype(float).to_numpy()
    width_shift = post["width_shift_10_90_h"].astype(float).to_numpy()
    base_med = post["base_q50"].astype(float).to_numpy()
    branch_med = post["branch_q50"].astype(float).to_numpy()

    max_law = float(np.max(np.abs(law)))
    mean_law = float(np.mean(np.abs(law)))
    first_law = float(abs(law[0]))
    last_law = float(abs(law[-1]))
    raw_amp = float((last_law - first_law) / (mean_law + eps))
    pos_amp = float(max(0.0, raw_amp))
    last_over_max = 0.0 if max_law <= eps else float(np.clip(last_law / max_law, 0.0, 1.0))
    monotonic = 1.0 if len(law) <= 1 else float(np.mean(np.diff(np.abs(law)) >= -eps))
    temporal = _temporal_shift_metrics(
        law,
        width_shift,
        branch_step=int(grp["branch_step"].iloc[0]),
        eps=eps,
    )

    row = {
        "n_steps": int(len(post)),
        "max_law_shift": max_law,
        "mean_law_shift": mean_law,
        "law_first": first_law,
        "law_last": last_law,
        "positive_law_amplification": pos_amp,
        "last_over_max_law": last_over_max,
        "monotonic_growth_fraction": monotonic,
        "max_widening_10_90": float(np.max(np.clip(width_shift, 0.0, None))),
        "shape_break": float(1.0 - _safe_corr(base_med, branch_med)),
    }
    row.update(temporal)
    return row


def summarize_chronos_branches(step_df, eps=1e-12):
    """One-row summary per forced token-bin branch."""
    rows = []
    for token_id, grp in step_df.groupby("token_id", sort=False):
        grp = grp.sort_values("forecast_step")
        components = _summarize_branch_components(grp, eps=eps)

        row = {
                "token_id": int(token_id),
                "token_rank": int(grp["token_rank"].iloc[0]),
                "token_probability": float(grp["token_probability"].iloc[0]),
                "token_surprisal": float(grp["token_surprisal"].iloc[0]),
                "top1_probability": float(grp["top1_probability"].iloc[0]),
                "top2_probability": float(grp["top2_probability"].iloc[0]),
                "top1_top2_margin": float(grp["top1_top2_margin"].iloc[0]),
                "token_entropy": float(grp["token_entropy"].iloc[0]),
                "normalized_token_entropy": float(grp["normalized_token_entropy"].iloc[0]),
                "top_k_probability_mass": float(grp["top_k_probability_mass"].iloc[0]),
                "token_value_unit_scale": float(grp["token_value_unit_scale"].iloc[0]),
                "is_base_token": bool(grp["is_base_token"].iloc[0]),
                "branch_step": int(grp["branch_step"].iloc[0]),
        }
        row.update(components)
        rows.append(row)

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    # Keep the score simple and transparent for token-bin FPA. Do not compare
    # across datasets without normalization.
    out["token_bin_forking_score"], out["progressive_token_bin_forking_score"] = compute_forking_scores(out)
    return out.sort_values(
        ["is_base_token", "progressive_token_bin_forking_score"],
        ascending=[True, False],
    ).reset_index(drop=True)


def analyze_chronos_named_branches(decode_out, base_branch_id=None):
    """Build per-step metrics for named Chronos branches.

    This is used by bundle branches whose identity is not just one token ID.
    """
    branch_step = int(decode_out["branch_step"])
    branches = decode_out["branches"]
    base_branch_id = base_branch_id or decode_out.get("base_branch_id")
    if base_branch_id not in branches:
        raise ValueError(f"Missing base branch {base_branch_id!r}.")

    q_base = _to_numpy(branches[base_branch_id]["quantiles"])
    base_median = q_base[:, 4]
    base_width = q_base[:, 8] - q_base[:, 0]

    rows = []
    for branch_id, branch in branches.items():
        spec = branch.get("branch")
        q = _to_numpy(branch["quantiles"])
        med = q[:, 4]
        width = q[:, 8] - q[:, 0]
        law_step = np.mean(np.abs(q - q_base), axis=1)
        median_shift = np.abs(med - base_median)
        width_shift = width - base_width

        if spec is None:
            forced_tokens = ""
            initial_token_id = np.nan
            initial_token_rank = np.nan
            continuation_rank = np.nan
            is_base_branch = branch_id == base_branch_id
            branch_kind = decode_out.get("metadata", {}).get("branch_kind", "named")
        else:
            forced_tokens = " ".join(str(token) for token in spec.forced_tokens)
            initial_token_id = int(spec.initial_token_id)
            initial_token_rank = int(spec.initial_token_rank)
            continuation_rank = (
                np.nan if spec.continuation_rank is None else int(spec.continuation_rank)
            )
            is_base_branch = bool(spec.is_base_branch)
            branch_kind = spec.branch_kind

        for h in range(q.shape[0]):
            rows.append(
                {
                    "branch_id": str(branch_id),
                    "branch_kind": branch_kind,
                    "branch_step": branch_step,
                    "forecast_step": h,
                    "relative_step_after_branch": h - branch_step,
                    "forced_tokens": forced_tokens,
                    "initial_token_id": initial_token_id,
                    "initial_token_rank": initial_token_rank,
                    "continuation_rank": continuation_rank,
                    "initial_token_probability": (
                        np.nan if spec is None else float(spec.initial_token_probability)
                    ),
                    "initial_token_surprisal": (
                        np.nan if spec is None else float(spec.initial_token_surprisal)
                    ),
                    "top1_probability": np.nan if spec is None else float(spec.top1_probability),
                    "top2_probability": np.nan if spec is None else float(spec.top2_probability),
                    "top1_top2_margin": np.nan if spec is None else float(spec.top1_top2_margin),
                    "token_entropy": np.nan if spec is None else float(spec.token_entropy),
                    "normalized_token_entropy": (
                        np.nan if spec is None else float(spec.normalized_token_entropy)
                    ),
                    "top_k_probability_mass": (
                        np.nan if spec is None else float(spec.top_k_probability_mass)
                    ),
                    "is_base_branch": is_base_branch,
                    "base_branch_id": str(base_branch_id),
                    "law_shift_h": float(law_step[h]),
                    "median_shift_h": float(median_shift[h]),
                    "width_shift_10_90_h": float(width_shift[h]),
                    "base_q10": float(q_base[h, 0]),
                    "base_q50": float(q_base[h, 4]),
                    "base_q90": float(q_base[h, 8]),
                    "branch_q10": float(q[h, 0]),
                    "branch_q50": float(q[h, 4]),
                    "branch_q90": float(q[h, 8]),
                }
            )

    return pd.DataFrame(rows)


def summarize_chronos_named_branches(step_df, eps=1e-12):
    """One-row summary per named Chronos branch."""
    rows = []
    for branch_id, grp in step_df.groupby("branch_id", sort=False):
        grp = grp.sort_values("forecast_step")
        components = _summarize_branch_components(grp, eps=eps)

        row = {
                "branch_id": str(branch_id),
                "branch_kind": str(grp["branch_kind"].iloc[0]),
                "branch_step": int(grp["branch_step"].iloc[0]),
                "forced_tokens": str(grp["forced_tokens"].iloc[0]),
                "initial_token_id": grp["initial_token_id"].iloc[0],
                "initial_token_rank": grp["initial_token_rank"].iloc[0],
                "initial_token_probability": grp["initial_token_probability"].iloc[0],
                "initial_token_surprisal": grp["initial_token_surprisal"].iloc[0],
                "top1_probability": grp["top1_probability"].iloc[0],
                "top2_probability": grp["top2_probability"].iloc[0],
                "top1_top2_margin": grp["top1_top2_margin"].iloc[0],
                "token_entropy": grp["token_entropy"].iloc[0],
                "normalized_token_entropy": grp["normalized_token_entropy"].iloc[0],
                "top_k_probability_mass": grp["top_k_probability_mass"].iloc[0],
                "continuation_rank": grp["continuation_rank"].iloc[0],
                "is_base_branch": bool(grp["is_base_branch"].iloc[0]),
        }
        row.update(components)
        rows.append(row)

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    out["token_bin_forking_score"], out["progressive_token_bin_forking_score"] = compute_forking_scores(out)
    return out.sort_values(
        ["is_base_branch", "progressive_token_bin_forking_score"],
        ascending=[True, False],
    ).reset_index(drop=True)

