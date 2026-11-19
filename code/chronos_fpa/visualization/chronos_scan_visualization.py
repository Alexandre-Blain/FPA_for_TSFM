from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from chronos_score import SCORE_WEIGHTS as COMPONENT_WEIGHTS
from chronos_scales import (
    NORMALIZATION_SCALE_COLS,
    NORMALIZED_SCORE_COL,
    NORMALIZED_TOKEN_SCORE_COL,
    RAW_SCORE_COL,
    RAW_SCORE_OVER_WINDOW_SCALE_COL,
    RAW_TOKEN_SCORE_COL,
    WINDOW_SCALE_SCORE_COL,
    WINDOW_SCALE_TOKEN_SCORE_COL,
    resolve_score_column,
)
from research_schema import TEXT_COLUMNS, is_base_branch, read_csv

def _preferred_score_col(df: pd.DataFrame) -> str:
    selected = df.attrs.get("analysis_score_column", NORMALIZED_SCORE_COL)
    if not df.empty and selected not in df.columns:
        raise ValueError(f"Selected FPA score column {selected!r} is missing.")
    return selected


def _scale_col_from_score_col(score_col: str) -> str | None:
    if score_col in (WINDOW_SCALE_SCORE_COL, WINDOW_SCALE_TOKEN_SCORE_COL, RAW_SCORE_OVER_WINDOW_SCALE_COL):
        return "window_scale"
    for scale_col in NORMALIZATION_SCALE_COLS:
        if score_col.startswith(f"{scale_col}_scaled_"):
            return scale_col
    return None


def _preferred_scale_col(df: pd.DataFrame, score_col: str | None = None) -> str | None:
    return _scale_col_from_score_col(score_col or _preferred_score_col(df))


def _preferred_error_col(df: pd.DataFrame) -> str | None:
    score_col = _preferred_score_col(df)
    scale_col = _preferred_scale_col(df, score_col)
    col = f"base_mae_over_{scale_col}" if scale_col else "base_mae"
    return col if col in df.columns else None


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _safe_name(value: str) -> str:
    keep = []
    for char in str(value):
        keep.append(char if char.isalnum() or char in "-_." else "_")
    return "".join(keep).strip("_") or "dataset"


def _prepare_summary_df(summary_df: pd.DataFrame) -> pd.DataFrame:
    """Coerce known numeric columns; metrics are computed by the scan pipeline."""
    if summary_df.empty:
        return summary_df

    out = summary_df.copy()
    numeric_prefixes = (
        "base_",
        "context_",
        "gt_",
        "early_",
        "mid_",
        "late_",
        "peak_",
        "mean_",
        "max_",
        "min_",
        "token_",
        "top1_",
        "top2_",
        "normalized_",
        "progressive_",
        "persistent_",
        "instant_",
        "window_",
    )
    numeric_suffixes = (
        "_score",
        "_shift",
        "_scale",
        "_probability",
        "_surprisal",
        "_entropy",
        "_margin",
        "_ratio",
        "_fraction",
        "_rank",
        "_start",
        "_len",
    )
    explicit_numeric = {
        RAW_TOKEN_SCORE_COL,
        RAW_SCORE_COL,
        RAW_SCORE_OVER_WINDOW_SCALE_COL,
        NORMALIZED_TOKEN_SCORE_COL,
        NORMALIZED_SCORE_COL,
        WINDOW_SCALE_TOKEN_SCORE_COL,
        WINDOW_SCALE_SCORE_COL,
        "horizon",
        "branch_step",
        "num_samples",
        "shape_break",
        "positive_law_amplification",
        "monotonic_growth_fraction",
        "last_over_max_law",
        "area_under_law_shift",
        "top_k_probability_mass",
        "window_id",
        "token_id",
    }
    for col in out.columns:
        if col in TEXT_COLUMNS:
            continue
        if (
            col in explicit_numeric
            or col.startswith(numeric_prefixes)
            or col.endswith(numeric_suffixes)
            or "_over_" in col
            or "scaled_" in col
        ):
            out[col] = _numeric(out[col])
    return out.copy()


def _score_sorted(df: pd.DataFrame, score_col: str | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    score_col = score_col or _preferred_score_col(df)
    if score_col not in df.columns:
        raise ValueError(f"Selected FPA score column {score_col!r} is missing.")
    work = df.copy()
    work[score_col] = _numeric(work[score_col])
    return work.sort_values(score_col, ascending=False, na_position="last")


def _dataset_groups(df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    if df.empty or "dataset_name" not in df.columns:
        return []
    return [
        (str(dataset), grp.copy())
        for dataset, grp in df.groupby("dataset_name", dropna=False, sort=True)
    ]


def _alternative_branches(df: pd.DataFrame) -> pd.DataFrame:
    """Drop forced-base branches so plots focus on actual alternatives."""
    return df.loc[~is_base_branch(df)].copy()


def _rank_corr(df: pd.DataFrame, x_col: str, y_col: str) -> float:
    work = df[[x_col, y_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(work) < 3:
        return np.nan
    return float(work[x_col].rank().corr(work[y_col].rank()))


def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _branch_label(row) -> str:
    parts = [
        str(getattr(row, "dataset_name", "")),
        str(getattr(row, "series_id", "")),
        f"w{getattr(row, 'window_id', '')}",
        f"s{getattr(row, 'branch_step', '')}",
        str(getattr(row, "branch_mode", "")),
    ]
    if hasattr(row, "branch_id") and pd.notna(getattr(row, "branch_id")):
        parts.append(str(getattr(row, "branch_id")))
    elif hasattr(row, "token_id") and pd.notna(getattr(row, "token_id")):
        parts.append(f"tok{int(getattr(row, 'token_id'))}")
    return " / ".join(part for part in parts if part)


def _branch_key_columns(df: pd.DataFrame) -> list[str]:
    base = [
        "source",
        "dataset_name",
        "series_id",
        "window_id",
        "window_start",
        "branch_mode",
        "branch_step",
    ]
    if "branch_id" in df.columns:
        base.append("branch_id")
    elif "token_id" in df.columns:
        base.append("token_id")
    return [col for col in base if col in df.columns]


def _read_csv_if_exists(path: Path) -> pd.DataFrame:
    return read_csv(path, missing_ok=True)


def plot_top_branch_scores(
    ranking_df: pd.DataFrame,
    output_path: str | Path,
    top_n: int = 25,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(ranking_df)
    if ranking_df.empty or score_col not in ranking_df.columns:
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ordered = ranking_df.head(top_n).iloc[::-1].copy()
    labels = [_branch_label(row) for row in ordered.itertuples(index=False)]

    fig, ax = plt.subplots(figsize=(12, max(4, 0.42 * len(ordered) + 1.5)))
    ax.barh(labels, ordered[score_col].astype(float))
    ax.set_title("Top Chronos FPA Branch Shifts")
    ax.set_xlabel(score_col)
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_window_score_overview(
    summary_df: pd.DataFrame,
    output_path: str | Path,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    required = {"dataset_name", "series_id", "window_start", score_col}
    if summary_df.empty or not required.issubset(summary_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    grouped = (
        summary_df.groupby(["dataset_name", "series_id", "window_start"], dropna=False)
        [score_col]
        .max()
        .reset_index()
        .sort_values(score_col, ascending=False)
    )
    labels = [
        f"{row.dataset_name}/{row.series_id} @ {int(row.window_start)}"
        for row in grouped.head(40).itertuples(index=False)
    ][::-1]
    values = grouped.head(40)[score_col].astype(float).to_numpy()[::-1]

    fig, ax = plt.subplots(figsize=(12, max(4, 0.35 * len(labels) + 1.5)))
    ax.barh(labels, values)
    ax.set_title("Most Sensitive Dataset Windows")
    ax.set_xlabel(f"max {score_col}")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_top_law_shift_curves(
    steps_df: pd.DataFrame,
    ranking_df: pd.DataFrame,
    output_path: str | Path,
    top_n: int = 8,
) -> Path | None:
    plt = _pyplot()

    required = {"forecast_step", "law_shift_h"}
    if steps_df.empty or ranking_df.empty or not required.issubset(steps_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    key_cols = _branch_key_columns(steps_df)
    if not key_cols:
        return None

    top_keys = ranking_df.head(top_n)
    fig, ax = plt.subplots(figsize=(12, 6))
    plotted = 0

    for row in top_keys.itertuples(index=False):
        mask = pd.Series(True, index=steps_df.index)
        for col in key_cols:
            if not hasattr(row, col):
                continue
            value = getattr(row, col)
            mask &= steps_df[col] == value

        grp = steps_df[mask].sort_values("forecast_step")
        if grp.empty:
            continue
        ax.plot(
            grp["forecast_step"].astype(float),
            grp["law_shift_h"].astype(float),
            linewidth=1.5,
            label=_branch_label(row),
        )
        plotted += 1

    if plotted == 0:
        plt.close(fig)
        return None

    ax.set_title("Law Shift Curves For Top Branches")
    ax.set_xlabel("forecast step")
    ax.set_ylabel("law_shift_h")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=7)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_base_quality(
    summary_df: pd.DataFrame,
    output_path: str | Path,
) -> Path | None:
    plt = _pyplot()

    col = _preferred_error_col(summary_df)
    required = {"dataset_name", "series_id", "window_start", col}
    if col is None or summary_df.empty or not required.issubset(summary_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    grouped = (
        summary_df.groupby(["dataset_name", "series_id", "window_start"], dropna=False)
        [col]
        .max()
        .reset_index()
        .sort_values(col, ascending=False)
        .head(40)
    )
    labels = [
        f"{row.dataset_name}/{row.series_id} @ {int(row.window_start)}"
        for row in grouped.itertuples(index=False)
    ][::-1]
    values = grouped[col].astype(float).to_numpy()[::-1]

    fig, ax = plt.subplots(figsize=(12, max(4, 0.35 * len(labels) + 1.5)))
    ax.barh(labels, values)
    ax.axvline(1.0, color="crimson", linestyle="--", linewidth=1.2, label="warning threshold 1.0")
    ax.set_title("Chronos Base Forecast Error")
    ax.set_xlabel(col)
    ax.grid(True, axis="x", alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_score_distribution(
    summary_df: pd.DataFrame,
    output_path: str | Path,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    if summary_df.empty or score_col not in summary_df.columns:
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    work_df = summary_df.copy()
    work_df[score_col] = work_df[score_col].replace([np.inf, -np.inf], np.nan)
    work_df = work_df.dropna(subset=[score_col])
    if work_df.empty:
        return None

    fig, ax = plt.subplots(figsize=(10, 5.5))
    if "dataset_name" not in work_df.columns or work_df["dataset_name"].nunique() <= 1:
        ax.hist(
            work_df[score_col].astype(float),
            bins=min(40, max(8, int(np.sqrt(len(work_df))))),
            alpha=0.85,
        )
    else:
        datasets = sorted(work_df["dataset_name"].dropna().astype(str).unique())
        bins = min(40, max(8, int(np.sqrt(len(work_df)))))
        values_by_dataset = [
            work_df.loc[work_df["dataset_name"].astype(str) == dataset, score_col].astype(float)
            for dataset in datasets
        ]
        ax.hist(
            values_by_dataset,
            bins=bins,
            stacked=True,
            label=datasets,
            alpha=0.85,
        )
        ax.legend(
            title="dataset",
            loc="upper right",
            fontsize=8,
            title_fontsize=9,
        )

    ax.set_title("Distribution Of Chronos FPA Scores By Dataset")
    ax.set_xlabel(score_col)
    ax.set_ylabel("branch count")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_score_by_dataset_boxplot(
    summary_df: pd.DataFrame,
    output_path: str | Path,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    if (
        summary_df.empty
        or "dataset_name" not in summary_df.columns
        or score_col not in summary_df.columns
    ):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    work_df = summary_df.dropna(subset=[score_col, "dataset_name"]).copy()
    if work_df.empty:
        return None

    datasets = []
    values = []
    for dataset, grp in _dataset_groups(work_df):
        vals = _numeric(grp[score_col]).dropna().to_numpy()
        if len(vals) == 0:
            continue
        datasets.append(dataset)
        values.append(vals)

    if not values:
        return None

    medians = [float(np.median(vals)) for vals in values]
    order = np.argsort(medians)
    datasets = [datasets[i] for i in order]
    values = [values[i] for i in order]

    fig, ax = plt.subplots(figsize=(12, max(4, 0.45 * len(datasets) + 2)))
    ax.boxplot(values, vert=False, labels=datasets, showfliers=True, patch_artist=True)
    ax.set_title("Chronos FPA Score Distribution Per Dataset")
    ax.set_xlabel(score_col)
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_raw_vs_normalized_score(
    summary_df: pd.DataFrame,
    output_path: str | Path,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    if summary_df.empty or not {RAW_SCORE_COL, score_col}.issubset(summary_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    work_df = summary_df.dropna(subset=[RAW_SCORE_COL, score_col]).copy()
    if work_df.empty:
        return None

    fig, ax = plt.subplots(figsize=(8.5, 6.2))
    if "dataset_name" in work_df.columns:
        for dataset, grp in _dataset_groups(work_df):
            ax.scatter(
                _numeric(grp[RAW_SCORE_COL]),
                _numeric(grp[score_col]),
                s=28,
                alpha=0.72,
                label=dataset,
            )
        ax.legend(title="dataset", fontsize=8, title_fontsize=9)
    else:
        ax.scatter(
            _numeric(work_df[RAW_SCORE_COL]),
            _numeric(work_df[score_col]),
            s=28,
            alpha=0.72,
        )

    ax.set_title("Raw Score vs Normalized Score")
    ax.set_xlabel(RAW_SCORE_COL)
    ax.set_ylabel(score_col)
    ax.grid(True, alpha=0.25)
    if (_numeric(work_df[RAW_SCORE_COL]) > 0).all():
        ax.set_xscale("log")
    if (_numeric(work_df[score_col]) > 0).all():
        ax.set_yscale("log")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_score_vs_base_error(
    summary_df: pd.DataFrame,
    output_path: str | Path,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    error_col = _preferred_error_col(summary_df)
    if (
        summary_df.empty
        or error_col is None
        or score_col not in summary_df.columns
        or error_col not in summary_df.columns
    ):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    group_cols = [
        col
        for col in ("dataset_name", "series_id", "window_id", "window_start")
        if col in summary_df.columns
    ]
    if group_cols:
        work_df = (
            summary_df.groupby(group_cols, dropna=False)
            .agg({score_col: "max", error_col: "max"})
            .reset_index()
        )
    else:
        work_df = summary_df[[score_col, error_col]].copy()

    work_df[score_col] = _numeric(work_df[score_col])
    work_df[error_col] = _numeric(work_df[error_col])
    work_df = work_df.dropna(subset=[score_col, error_col])
    if work_df.empty:
        return None

    score_thr = float(work_df[score_col].median())
    err_thr = float(work_df[error_col].median())

    fig, ax = plt.subplots(figsize=(9.5, 6.6))
    if "dataset_name" in work_df.columns:
        for dataset, grp in _dataset_groups(work_df):
            ax.scatter(
                _numeric(grp[error_col]),
                _numeric(grp[score_col]),
                s=38,
                alpha=0.72,
                label=dataset,
            )
        ax.legend(title="dataset", fontsize=8, title_fontsize=9)
    else:
        ax.scatter(_numeric(work_df[error_col]), _numeric(work_df[score_col]), s=38, alpha=0.72)

    ax.axvline(err_thr, color="grey", linestyle="--", linewidth=1.0)
    ax.axhline(score_thr, color="grey", linestyle="--", linewidth=1.0)
    ax.text(
        0.99,
        0.98,
        "high shift / high error",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        color="crimson",
    )
    ax.text(
        0.01,
        0.98,
        "high shift / low error",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color="darkgreen",
    )
    ax.text(
        0.99,
        0.03,
        "low shift / high error",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        color="darkorange",
    )
    ax.set_title("FPA Shift vs Chronos Base Forecast Error")
    ax.set_xlabel(error_col)
    ax.set_ylabel(score_col)
    ax.grid(True, alpha=0.25)
    if (_numeric(work_df[error_col]) > 0).all():
        ax.set_xscale("log")
    if (_numeric(work_df[score_col]) > 0).all():
        ax.set_yscale("log")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_score_vs_logit_metric(
    summary_df: pd.DataFrame,
    output_path: str | Path,
    metric_col: str,
    title: str,
    xlabel: str,
    alternatives_only: bool = True,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    if summary_df.empty or not {score_col, metric_col}.issubset(summary_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    work_df = _alternative_branches(summary_df) if alternatives_only else summary_df.copy()
    work_df[score_col] = _numeric(work_df[score_col])
    work_df[metric_col] = _numeric(work_df[metric_col])
    work_df = work_df.dropna(subset=[score_col, metric_col])
    if work_df.empty:
        return None

    fig, ax = plt.subplots(figsize=(9.5, 6.3))
    if "dataset_name" in work_df.columns:
        for dataset, grp in _dataset_groups(work_df):
            ax.scatter(
                _numeric(grp[metric_col]),
                _numeric(grp[score_col]),
                s=30,
                alpha=0.72,
                label=dataset,
            )
        ax.legend(title="dataset", fontsize=8, title_fontsize=9)
    else:
        ax.scatter(_numeric(work_df[metric_col]), _numeric(work_df[score_col]), s=30, alpha=0.72)

    corr = _rank_corr(work_df, metric_col, score_col)
    suffix = "alternatives only" if alternatives_only else "all branches"
    ax.set_title(f"{title} ({suffix}, rank corr={corr:.3f})")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(f"normalized FPA shift score: {score_col}")
    ax.grid(True, alpha=0.25)
    if metric_col in {"token_probability", "initial_token_probability"}:
        ax.set_xscale("log")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_branch_step_token_rank_heatmap(
    summary_df: pd.DataFrame,
    output_path: str | Path,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    rank_col = "token_rank" if "token_rank" in summary_df.columns else "initial_token_rank"
    required = {"branch_step", rank_col, score_col}
    if summary_df.empty or not required.issubset(summary_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    work_df = summary_df.copy()
    work_df[score_col] = _numeric(work_df[score_col])
    work_df[rank_col] = _numeric(work_df[rank_col])
    work_df = work_df.dropna(subset=[score_col, "branch_step", rank_col])
    if work_df.empty:
        return None

    pivot = work_df.pivot_table(
        index="branch_step",
        columns=rank_col,
        values=score_col,
        aggfunc="max",
    ).sort_index()
    if pivot.empty:
        return None

    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", interpolation="nearest", cmap="viridis")
    ax.set_title("Max Normalized FPA Shift By Branch Step And Token Rank")
    ax.set_xlabel("forced token rank at branch step (1 = greedy/base token)")
    ax.set_ylabel("forecast step where token is forced")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns])
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels([str(int(idx)) for idx in pivot.index])
    fig.colorbar(image, ax=ax, label=score_col)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_branch_step_token_rank_zone_map(
    summary_df: pd.DataFrame,
    output_path: str | Path,
    alternatives_only: bool = True,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    rank_col = "token_rank" if "token_rank" in summary_df.columns else "initial_token_rank"
    required = {"branch_step", rank_col, score_col}
    if summary_df.empty or not required.issubset(summary_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    work_df = _alternative_branches(summary_df) if alternatives_only else summary_df.copy()
    work_df[score_col] = _numeric(work_df[score_col])
    work_df[rank_col] = _numeric(work_df[rank_col])
    work_df["branch_step"] = _numeric(work_df["branch_step"])
    work_df = work_df.dropna(subset=[score_col, "branch_step", rank_col])
    if work_df.empty:
        return None

    pivot = work_df.pivot_table(
        index="branch_step",
        columns=rank_col,
        values=score_col,
        aggfunc="max",
    ).sort_index()
    if pivot.empty:
        return None

    fig, ax = plt.subplots(figsize=(10, 5.8))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", interpolation="nearest", cmap="magma")
    suffix = "alternatives only" if alternatives_only else "all branches"
    ax.set_title(f"Sensitive Zone Map: Branch Step x Token Rank ({suffix})")
    ax.set_xlabel("forced token rank at branch step (rank 1 = most probable token)")
    ax.set_ylabel("branch_step: forecast token position where forcing starts")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns])
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels([str(int(idx)) for idx in pivot.index])
    fig.colorbar(image, ax=ax, label=f"max {score_col}")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_window_token_rank_zone_map(
    summary_df: pd.DataFrame,
    output_path: str | Path,
    top_n: int = 40,
    alternatives_only: bool = True,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    rank_col = "token_rank" if "token_rank" in summary_df.columns else "initial_token_rank"
    key_cols = ["dataset_name", "series_id", "window_id", "window_start", "branch_step"]
    required = set(key_cols).union({rank_col, score_col})
    if summary_df.empty or not required.issubset(summary_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    work_df = _alternative_branches(summary_df) if alternatives_only else summary_df.copy()
    work_df[score_col] = _numeric(work_df[score_col])
    work_df[rank_col] = _numeric(work_df[rank_col])
    work_df["branch_step"] = _numeric(work_df["branch_step"])
    work_df = work_df.dropna(subset=[score_col, rank_col, "branch_step"])
    if work_df.empty:
        return None

    group_scores = (
        work_df.groupby(key_cols, dropna=False)[score_col]
        .max()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    selected = work_df.merge(group_scores[key_cols], on=key_cols, how="inner")
    if selected.empty:
        return None

    selected["zone_label"] = selected.apply(
        lambda row: (
            f"{row['dataset_name']}/{row['series_id']} "
            f"w{int(row['window_id'])} start={int(row['window_start'])} "
            f"s{int(row['branch_step'])}"
        ),
        axis=1,
    )
    label_order = (
        selected.groupby("zone_label", dropna=False)[score_col]
        .max()
        .sort_values(ascending=True)
        .index
        .tolist()
    )
    selected["zone_label"] = pd.Categorical(selected["zone_label"], categories=label_order, ordered=True)
    pivot = selected.pivot_table(
        index="zone_label",
        columns=rank_col,
        values=score_col,
        aggfunc="max",
        observed=False,
    )
    if pivot.empty:
        return None

    fig, ax = plt.subplots(figsize=(12, max(6, 0.30 * len(pivot.index) + 1.8)))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", interpolation="nearest", cmap="magma")
    suffix = "alternatives only" if alternatives_only else "all branches"
    ax.set_title(f"Top Sensitive Windows: Token Rank Micro-Map ({suffix})")
    ax.set_xlabel("forced token rank at branch step (rank 1 = most probable token)")
    ax.set_ylabel("window and branch_step")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns])
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels([str(label) for label in pivot.index], fontsize=7)
    fig.colorbar(image, ax=ax, label=score_col)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_temporal_shift_profile(
    summary_df: pd.DataFrame,
    output_path: str | Path,
    top_n: int = 25,
    alternatives_only: bool = False,
    x_clip_quantile: float | None = None,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    scale_col = _preferred_scale_col(summary_df, score_col)
    required = {score_col, "early_law_shift", "mid_law_shift", "late_law_shift"}
    if scale_col is not None:
        required.add(scale_col)
    if summary_df.empty or not required.issubset(summary_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source_df = _alternative_branches(summary_df) if alternatives_only else summary_df
    ordered = _score_sorted(source_df, score_col).head(top_n).copy()
    if ordered.empty:
        return None

    phases = ["early_law_shift", "mid_law_shift", "late_law_shift"]
    values = ordered[phases].apply(_numeric)
    if scale_col is not None:
        scale = _numeric(ordered[scale_col]).where(_numeric(ordered[scale_col]) > 0)
        values = values.div(scale, axis=0)
    clipped_note = ""
    if x_clip_quantile is not None:
        finite = values.to_numpy(dtype=float)
        finite = finite[np.isfinite(finite)]
        if finite.size:
            x_max = float(np.quantile(finite, x_clip_quantile))
            if np.isfinite(x_max) and x_max > 0:
                values = values.clip(upper=x_max)
                clipped_note = f" (x clipped at p{int(x_clip_quantile * 100)})"
    labels = [_branch_label(row) for row in ordered.itertuples(index=False)]

    fig, ax = plt.subplots(figsize=(11, max(5, 0.36 * len(ordered) + 1.6)))
    y = np.arange(len(ordered))
    height = 0.22
    offsets = [-height, 0.0, height]
    colors = ["#2A9D8F", "#246BFE", "#E76F51"]
    names = ["early normalized shift", "mid normalized shift", "late normalized shift"]
    for phase, offset, color, name in zip(phases, offsets, colors, names):
        ax.barh(y + offset, values[phase], height=height, color=color, alpha=0.85, label=name)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    suffix = " Alternatives Only" if alternatives_only else ""
    ax.set_title(f"Temporal Shift Profile For Top Branches{suffix}{clipped_note}")
    ax.set_xlabel(
        f"mean law_shift_h divided by {scale_col}"
        if scale_col is not None
        else "raw mean law_shift_h"
    )
    ax.grid(True, axis="x", alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_topology_regime_map(
    summary_df: pd.DataFrame,
    output_path: str | Path,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    required = {
        score_col,
        "normalized_token_entropy",
        "top1_top2_margin",
        "token_probability",
    }
    if summary_df.empty or not required.issubset(summary_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    work_df = _alternative_branches(summary_df)
    for col in [score_col, "normalized_token_entropy", "top1_top2_margin", "token_probability"]:
        work_df[col] = _numeric(work_df[col])
    work_df = work_df.dropna(
        subset=[score_col, "normalized_token_entropy", "top1_top2_margin", "token_probability"]
    )
    if work_df.empty:
        return None

    fig, ax = plt.subplots(figsize=(9.5, 6.2))
    scatter = ax.scatter(
        work_df["top1_top2_margin"],
        work_df["normalized_token_entropy"],
        c=work_df[score_col],
        s=18 + 60 * np.clip(-np.log10(work_df["token_probability"].clip(lower=1e-12)) / 12, 0, 1),
        alpha=0.72,
        cmap="viridis",
    )

    entropy_thr = float(work_df["normalized_token_entropy"].quantile(0.75))
    margin_thr = float(work_df["top1_top2_margin"].quantile(0.75))
    low_margin_thr = float(work_df["top1_top2_margin"].quantile(0.25))
    ax.axhline(entropy_thr, color="grey", linestyle="--", linewidth=1.0, alpha=0.7)
    ax.axvline(margin_thr, color="grey", linestyle="--", linewidth=1.0, alpha=0.7)
    ax.axvline(low_margin_thr, color="grey", linestyle=":", linewidth=1.0, alpha=0.7)
    ax.text(
        0.02,
        0.98,
        "uncertain zone\nhigh entropy / low margin",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color="darkgreen",
    )
    ax.text(
        0.98,
        0.04,
        "confident zone\nlow entropy / high margin",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        color="darkred",
    )
    ax.set_title("Topology Regime Map For Alternative Branches")
    ax.set_xlabel("top1 probability - top2 probability at branch_step")
    ax.set_ylabel("normalized entropy of next-token distribution at branch_step")
    ax.grid(True, alpha=0.25)
    fig.colorbar(scatter, ax=ax, label=score_col)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_score_component_contributions(
    ranking_df: pd.DataFrame,
    output_path: str | Path,
    top_n: int = 20,
) -> Path | None:
    plt = _pyplot()

    required = set(COMPONENT_WEIGHTS)
    if ranking_df.empty or not required.issubset(ranking_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ordered = _score_sorted(ranking_df).head(top_n).iloc[::-1].copy()
    if ordered.empty:
        return None

    labels = [_branch_label(row) for row in ordered.itertuples(index=False)]
    fig, ax = plt.subplots(figsize=(13, max(4.5, 0.45 * len(ordered) + 1.5)))
    left = np.zeros(len(ordered), dtype=float)
    colors = {
        "mean_law_shift": "#2A9D8F",
        "max_law_shift": "#246BFE",
        "positive_law_amplification": "#F4A261",
        "shape_break": "#6D5DF6",
        "max_widening_10_90": "#E76F51",
    }
    for col, weight in COMPONENT_WEIGHTS.items():
        values = _numeric(ordered[col]).fillna(0.0).to_numpy() * weight
        ax.barh(labels, values, left=left, label=f"{weight:.2f} x {col}", color=colors[col], alpha=0.86)
        left += values

    ax.set_title("Raw Forking Score Component Contributions")
    ax.set_xlabel("weighted contribution to token_bin_forking_score")
    ax.grid(True, axis="x", alpha=0.25)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_dataset_window_heatmap(
    summary_df: pd.DataFrame,
    output_path: str | Path,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    required = {"dataset_name", "series_id", "window_id", score_col}
    if summary_df.empty or not required.issubset(summary_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    grouped = (
        summary_df.groupby(["dataset_name", "series_id", "window_id"], dropna=False)
        [score_col]
        .max()
        .reset_index()
    )
    if grouped.empty:
        return None
    grouped["window_label"] = grouped.apply(
        lambda row: f"{row['dataset_name']}/{row['series_id']}",
        axis=1,
    )
    pivot = grouped.pivot_table(
        index="window_label",
        columns="window_id",
        values=score_col,
        aggfunc="max",
    )
    pivot["__max"] = pivot.max(axis=1)
    pivot = pivot.sort_values("__max", ascending=False).drop(columns="__max").head(35)
    if pivot.empty:
        return None

    data = pivot.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(12, max(4.5, 0.28 * len(pivot) + 1.8)))
    image = ax.imshow(data, aspect="auto", interpolation="nearest", cmap="viridis")
    ax.set_title("Window Sensitivity Heatmap")
    ax.set_xlabel("window_id")
    ax.set_ylabel("dataset/series")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(col) for col in pivot.columns])
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    fig.colorbar(image, ax=ax, label=score_col)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_dataset_summary_matrix(
    summary_df: pd.DataFrame,
    output_path: str | Path,
) -> Path | None:
    plt = _pyplot()

    score_col = _preferred_score_col(summary_df)
    error_col = _preferred_error_col(summary_df)
    required = {"dataset_name", score_col}
    if summary_df.empty or not required.issubset(summary_df.columns):
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    agg_spec = {
        score_col: ["median", "max"],
    }
    if RAW_SCORE_COL in summary_df.columns:
        agg_spec[RAW_SCORE_COL] = ["median", "max"]
    if error_col:
        agg_spec[error_col] = ["median", "max"]

    grouped = summary_df.groupby("dataset_name", dropna=False).agg(agg_spec)
    grouped.columns = ["_".join(col).strip("_") for col in grouped.columns.to_flat_index()]
    grouped = grouped.replace([np.inf, -np.inf], np.nan)
    if grouped.empty:
        return None

    cols = [col for col in grouped.columns if not col.endswith("_count")]
    matrix = grouped[cols].copy()
    # Column-wise robust scaling for visual comparison across heterogeneous metrics.
    scaled = matrix.copy()
    for col in cols:
        values = _numeric(scaled[col])
        lo = values.quantile(0.05)
        hi = values.quantile(0.95)
        denom = hi - lo
        scaled[col] = 0.0 if not np.isfinite(denom) or denom <= 1e-12 else ((values - lo) / denom).clip(0, 1)

    fig, ax = plt.subplots(figsize=(max(8, 1.25 * len(cols) + 2), max(4, 0.42 * len(scaled) + 1.8)))
    image = ax.imshow(scaled.to_numpy(dtype=float), aspect="auto", interpolation="nearest", cmap="magma")
    ax.set_title("Dataset Diagnostic Matrix (Column-Scaled)")
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(scaled.index)))
    ax.set_yticklabels([str(idx) for idx in scaled.index], fontsize=9)
    fig.colorbar(image, ax=ax, label="relative within metric")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_chronos_scan_outputs(
    run_dir: str | Path,
    top_n: int = 25,
    score_col: str | None = None,
) -> List[Path]:
    """Generate PNG figures from raw Chronos benchmark scan CSV outputs."""
    run_dir = Path(run_dir)
    figures_dir = run_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    steps_df = _read_csv_if_exists(run_dir / "chronos_scan_steps.csv")
    summary_df = _prepare_summary_df(_read_csv_if_exists(run_dir / "chronos_scan_summary.csv"))
    ranking_df = _prepare_summary_df(_read_csv_if_exists(run_dir / "chronos_scan_ranking.csv"))
    score_col = resolve_score_column(summary_df, score_col)
    if ranking_df.empty:
        ranking_df = summary_df.copy()
    for frame in (summary_df, ranking_df):
        if score_col not in frame.columns:
            raise ValueError(f"Selected FPA score column {score_col!r} is missing from scan summary/ranking.")
        resolve_score_column(frame, score_col)
        frame.attrs["analysis_score_column"] = score_col
    ranking_df = _score_sorted(ranking_df, score_col)

    token_probability_label = (
        "P(token force au branch_step | contexte + prefixe greedy) (log scale)"
    )
    token_surprisal_label = (
        "-log P(token force au branch_step | contexte + prefixe greedy)"
    )
    token_entropy_label = (
        "normalized entropy of P(next token | contexte + prefixe greedy)"
    )
    top_margin_label = "top1 - top2 in P(next token | contexte + prefixe greedy)"

    outputs = [
        plot_top_branch_scores(
            ranking_df,
            figures_dir / "chronos_top_branch_scores.png",
            top_n=top_n,
        ),
        plot_window_score_overview(
            summary_df,
            figures_dir / "chronos_window_score_overview.png",
        ),
        plot_top_law_shift_curves(
            steps_df,
            ranking_df,
            figures_dir / "chronos_top_law_shift_curves.png",
            top_n=min(8, top_n),
        ),
        plot_base_quality(
            summary_df,
            figures_dir / "chronos_base_quality.png",
        ),
        plot_score_distribution(
            summary_df,
            figures_dir / "chronos_score_distribution.png",
        ),
        plot_score_by_dataset_boxplot(
            summary_df,
            figures_dir / "chronos_score_by_dataset_boxplot.png",
        ),
        plot_raw_vs_normalized_score(
            summary_df,
            figures_dir / "chronos_raw_vs_normalized_score.png",
        ),
        plot_score_vs_base_error(
            summary_df,
            figures_dir / "chronos_score_vs_base_error.png",
        ),
        plot_score_component_contributions(
            ranking_df,
            figures_dir / "chronos_score_component_contributions.png",
            top_n=min(20, top_n),
        ),
        plot_dataset_window_heatmap(
            summary_df,
            figures_dir / "chronos_window_sensitivity_heatmap.png",
        ),
        plot_dataset_summary_matrix(
            summary_df,
            figures_dir / "chronos_dataset_diagnostic_matrix.png",
        ),
        plot_score_vs_logit_metric(
            summary_df,
            figures_dir / "chronos_score_vs_token_probability.png",
            metric_col=(
                "token_probability"
                if "token_probability" in summary_df.columns
                else "initial_token_probability"
            ),
            title="Normalized FPA Shift vs Forced Token Probability",
            xlabel=token_probability_label,
        ),
        plot_score_vs_logit_metric(
            summary_df,
            figures_dir / "chronos_score_vs_token_surprisal.png",
            metric_col=(
                "token_surprisal"
                if "token_surprisal" in summary_df.columns
                else "initial_token_surprisal"
            ),
            title="Normalized FPA Shift vs Forced Token Surprisal",
            xlabel=token_surprisal_label,
        ),
        plot_score_vs_logit_metric(
            summary_df,
            figures_dir / "chronos_score_vs_token_entropy.png",
            metric_col="normalized_token_entropy",
            title="Normalized FPA Shift vs Local Token Entropy",
            xlabel=token_entropy_label,
        ),
        plot_score_vs_logit_metric(
            summary_df,
            figures_dir / "chronos_score_vs_top1_top2_margin.png",
            metric_col="top1_top2_margin",
            title="Normalized FPA Shift vs Top-1/Top-2 Probability Margin",
            xlabel=top_margin_label,
        ),
        plot_branch_step_token_rank_heatmap(
            summary_df,
            figures_dir / "chronos_branch_step_token_rank_heatmap.png",
        ),
        plot_temporal_shift_profile(
            summary_df,
            figures_dir / "chronos_temporal_shift_profile.png",
            top_n=min(25, top_n),
        ),
    ]

    research_dir = figures_dir / "recherche"
    outputs.extend(
        [
            plot_score_vs_logit_metric(
                summary_df,
                research_dir / "score_vs_token_probability_alternatives_only.png",
                metric_col=(
                    "token_probability"
                    if "token_probability" in summary_df.columns
                    else "initial_token_probability"
                ),
                title="Alternative Branch Shift vs Forced Token Probability",
                xlabel=token_probability_label,
                alternatives_only=True,
            ),
            plot_score_vs_logit_metric(
                summary_df,
                research_dir / "score_vs_token_surprisal_alternatives_only.png",
                metric_col=(
                    "token_surprisal"
                    if "token_surprisal" in summary_df.columns
                    else "initial_token_surprisal"
                ),
                title="Alternative Branch Shift vs Forced Token Surprisal",
                xlabel=token_surprisal_label,
                alternatives_only=True,
            ),
            plot_topology_regime_map(
                summary_df,
                research_dir / "topology_regime_map_alternatives_only.png",
            ),
            plot_branch_step_token_rank_zone_map(
                summary_df,
                research_dir / "branch_step_token_rank_zone_map_alternatives_only.png",
                alternatives_only=True,
            ),
            plot_window_token_rank_zone_map(
                summary_df,
                research_dir / "window_token_rank_micro_map_alternatives_only.png",
                top_n=min(40, max(top_n, 20)),
                alternatives_only=True,
            ),
            plot_temporal_shift_profile(
                summary_df,
                research_dir / "temporal_shift_profile_alternatives_only.png",
                top_n=min(25, top_n),
                alternatives_only=True,
            ),
            plot_temporal_shift_profile(
                summary_df,
                research_dir / "temporal_shift_profile_alternatives_only_clipped_p95.png",
                top_n=min(25, top_n),
                alternatives_only=True,
                x_clip_quantile=0.95,
            ),
        ]
    )

    by_dataset_dir = figures_dir / "by_dataset"
    for dataset, dataset_summary in _dataset_groups(summary_df):
        dataset_dir = by_dataset_dir / _safe_name(dataset)
        dataset_steps = (
            steps_df[steps_df["dataset_name"].astype(str) == dataset].copy()
            if not steps_df.empty and "dataset_name" in steps_df.columns
            else pd.DataFrame()
        )
        dataset_ranking = (
            ranking_df[ranking_df["dataset_name"].astype(str) == dataset].copy()
            if "dataset_name" in ranking_df.columns
            else _score_sorted(dataset_summary)
        )
        outputs.extend(
            [
                plot_top_branch_scores(
                    dataset_ranking,
                    dataset_dir / "top_branch_scores.png",
                    top_n=min(top_n, 25),
                ),
                plot_window_score_overview(
                    dataset_summary,
                    dataset_dir / "window_score_overview.png",
                ),
                plot_top_law_shift_curves(
                    dataset_steps,
                    dataset_ranking,
                    dataset_dir / "law_shift_curves.png",
                    top_n=min(8, top_n),
                ),
                plot_base_quality(
                    dataset_summary,
                    dataset_dir / "base_quality.png",
                ),
                plot_score_distribution(
                    dataset_summary,
                    dataset_dir / "score_distribution.png",
                ),
                plot_score_vs_base_error(
                    dataset_summary,
                    dataset_dir / "score_vs_base_error.png",
                ),
                plot_score_component_contributions(
                    dataset_ranking,
                    dataset_dir / "score_component_contributions.png",
                    top_n=min(15, top_n),
                ),
                plot_dataset_window_heatmap(
                    dataset_summary,
                    dataset_dir / "window_sensitivity_heatmap.png",
                ),
                plot_score_vs_logit_metric(
                    dataset_summary,
                    dataset_dir / "score_vs_token_probability.png",
                    metric_col=(
                        "token_probability"
                        if "token_probability" in dataset_summary.columns
                        else "initial_token_probability"
                    ),
                    title=f"{dataset}: Shift vs Forced Token Probability",
                    xlabel=token_probability_label,
                ),
                plot_score_vs_logit_metric(
                    dataset_summary,
                    dataset_dir / "score_vs_token_entropy.png",
                    metric_col="normalized_token_entropy",
                    title=f"{dataset}: Shift vs Local Token Entropy",
                    xlabel=token_entropy_label,
                ),
                plot_branch_step_token_rank_heatmap(
                    dataset_summary,
                    dataset_dir / "branch_step_token_rank_heatmap.png",
                ),
                plot_temporal_shift_profile(
                    dataset_summary,
                    dataset_dir / "temporal_shift_profile.png",
                    top_n=min(15, top_n),
                ),
            ]
        )

    return [path for path in outputs if path is not None]





