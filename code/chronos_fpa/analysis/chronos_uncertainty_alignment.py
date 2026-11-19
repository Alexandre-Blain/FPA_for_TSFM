from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from research_schema import validate_branch_keys
from chronos_scales import normalization_scale_for_score

from chronos_analysis_helpers import (
    is_base_branch as _is_base_branch,
    numeric as _numeric,
    read_csv_robust,
    resolve_score_column as _resolve_score_column,
)
from research_schema import ANALYSIS_VERSION, GROUP_KEY_COLS, WINDOW_KEY_COLS


MODEL_UNCERTAINTY_COLS = [
    "model_distribution_uncertainty_index",
    "normalized_token_entropy",
    "inverse_top1_top2_margin",
    "inverse_top1_probability",
    "token_surprisal",
    "token_rank",
    "inverse_token_probability",
]

FPA_COL_CANDIDATES = [
    "instant_forking_score",
    "persistent_forking_score",
    "progressive_forking_score",
    "early_law_shift",
    "mid_law_shift",
    "late_law_shift",
    "peak_law_shift",
    "persistence_ratio",
]


@dataclass(frozen=True)
class AlignmentOutputs:
    output_dir: Path
    csv_paths: list[Path]
    figure_paths: list[Path]
    warnings: list[str]


def _rank01(series: pd.Series, higher_is_more: bool = True) -> pd.Series:
    values = _numeric(series)
    if not higher_is_more:
        values = -values
    valid = values.notna()
    out = pd.Series(np.nan, index=series.index, dtype=float)
    if valid.sum() <= 1:
        return out
    out.loc[valid] = values.loc[valid].rank(method="average", pct=True)
    return out


def prepare_uncertainty_metrics(summary: pd.DataFrame) -> pd.DataFrame:
    """Freeze descriptive percentile indices on the full, unfiltered summary.

    Average-tie percentile ranks use all finite input rows (including base
    branches). Missing components are omitted from row means; components with
    fewer than two finite rows stay undefined. This function never drops rows.
    """
    out = summary.copy()
    numeric_cols = set(MODEL_UNCERTAINTY_COLS + FPA_COL_CANDIDATES)
    numeric_cols.update(
        col
        for col in out.columns
        if "forking_score" in col
        or "law_shift" in col
        or col
        in {
            "token_probability",
            "token_surprisal",
            "token_rank",
            "normalized_token_entropy",
            "top1_top2_margin",
            "top1_probability",
            "top_k_probability_mass",
            "base_mae_over_window_scale",
        }
    )
    for col in numeric_cols.intersection(out.columns):
        out[col] = _numeric(out[col])
    out = out.copy()

    if "top1_top2_margin" in out.columns:
        out["inverse_top1_top2_margin"] = 1.0 - out["top1_top2_margin"].clip(0.0, 1.0)
    if "top1_probability" in out.columns:
        out["inverse_top1_probability"] = 1.0 - out["top1_probability"].clip(0.0, 1.0)
    if "token_probability" in out.columns:
        clipped = out["token_probability"].clip(lower=1e-12)
        out["inverse_token_probability"] = 1.0 - clipped
        if "token_surprisal" not in out.columns:
            out["token_surprisal"] = -np.log(clipped)

    distribution_parts = []
    for col, higher_is_more in [
        ("normalized_token_entropy", True),
        ("top1_top2_margin", False),
        ("top1_probability", False),
    ]:
        if col in out.columns:
            distribution_parts.append(_rank01(out[col], higher_is_more=higher_is_more))
    if distribution_parts:
        out["model_distribution_uncertainty_index"] = pd.concat(distribution_parts, axis=1).mean(axis=1)

    token_implausibility_parts = []
    for col, higher_is_more in [
        ("token_surprisal", True),
        ("token_rank", True),
        ("token_probability", False),
    ]:
        if col in out.columns:
            token_implausibility_parts.append(_rank01(out[col], higher_is_more=higher_is_more))
    if token_implausibility_parts:
        out["forced_token_implausibility_index"] = pd.concat(token_implausibility_parts, axis=1).mean(axis=1)

    return out


def _prepare_analysis_frame(summary: pd.DataFrame, score_col: str) -> pd.DataFrame:
    out = prepare_uncertainty_metrics(summary)
    out[score_col] = _numeric(out[score_col])
    out["selected_fpa_score"] = out[score_col]
    return out


def _corr_records(frame: pd.DataFrame, group_name: str, group_value: str, fpa_cols: list[str]) -> list[dict]:
    records = []
    metric_cols = [col for col in MODEL_UNCERTAINTY_COLS + ["forced_token_implausibility_index"] if col in frame.columns]
    for fpa_col in fpa_cols:
        if fpa_col not in frame.columns:
            continue
        for metric_col in metric_cols:
            work = frame[[fpa_col, metric_col]].apply(_numeric).dropna()
            enough = len(work) >= 3
            nonconstant = work[fpa_col].nunique() > 1 and work[metric_col].nunique() > 1
            defined = enough and nonconstant
            records.append(
                {
                    "group_name": group_name,
                    "group_value": group_value,
                    "fpa_metric": fpa_col,
                    "model_metric": metric_col,
                    "n": int(len(work)),
                    "rows_total": int(len(frame)),
                    "rows_excluded_pairwise": int(len(frame) - len(work)),
                    "correlation_defined": defined,
                    "undefined_reason": "" if defined else "fewer_than_three_pairs" if not enough else "constant_metric",
                    "pearson_corr": float(work[fpa_col].corr(work[metric_col], method="pearson")) if defined else np.nan,
                    "spearman_corr": float(work[fpa_col].rank().corr(work[metric_col].rank())) if defined else np.nan,
                }
            )
    return records


def _aggregate_branch_points(frame: pd.DataFrame, fpa_cols: list[str]) -> pd.DataFrame:
    missing = set(GROUP_KEY_COLS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing branch-point identifiers: {sorted(missing)}")
    metrics = list(dict.fromkeys(
        col for col in fpa_cols + MODEL_UNCERTAINTY_COLS + ["forced_token_implausibility_index"]
        if col in frame.columns and col not in GROUP_KEY_COLS
    ))
    grouped = frame.groupby(GROUP_KEY_COLS, dropna=False, sort=False)
    out = grouped[metrics].mean().reset_index()
    out["branches_aggregated"] = grouped.size().to_numpy()
    return out


def _grouped_correlations(frame: pd.DataFrame, fpa_cols: list[str]) -> pd.DataFrame:
    records = _corr_records(frame, "global", "all", fpa_cols)
    for column, group_name in [("dataset_name", "dataset"), ("branch_step", "branch_step")]:
        if column in frame.columns:
            for value, subset in frame.groupby(column, dropna=False):
                records.extend(_corr_records(subset, group_name, str(value), fpa_cols))
    return pd.DataFrame(records)


def _make_quadrants(frame: pd.DataFrame, score_col: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    metric = "model_distribution_uncertainty_index"
    if metric not in frame.columns:
        return pd.DataFrame(), pd.DataFrame()
    work = frame.dropna(subset=[metric, score_col]).copy()
    if work.empty:
        return pd.DataFrame(), pd.DataFrame()

    uncertainty_cut = work[metric].quantile(0.75)
    score_cut = work[score_col].quantile(0.75)
    work["model_uncertainty_zone"] = np.where(
        work[metric] >= uncertainty_cut,
        "high_model_uncertainty",
        "lower_model_uncertainty",
    )
    work["fpa_shift_zone"] = np.where(work[score_col] >= score_cut, "high_fpa_shift", "lower_fpa_shift")
    work["uncertainty_fpa_quadrant"] = work["model_uncertainty_zone"] + "__" + work["fpa_shift_zone"]

    summary = (
        work.groupby("uncertainty_fpa_quadrant", dropna=False)
        .agg(
            rows=(score_col, "size"),
            median_fpa_score=(score_col, "median"),
            max_fpa_score=(score_col, "max"),
            median_model_uncertainty=(metric, "median"),
            median_token_probability=("token_probability", "median") if "token_probability" in work.columns else (score_col, "size"),
            median_token_rank=("token_rank", "median") if "token_rank" in work.columns else (score_col, "size"),
        )
        .reset_index()
        .sort_values(["median_fpa_score", "rows"], ascending=[False, False])
    )
    return work, summary


def _interesting_branches(frame: pd.DataFrame, score_col: str, top_n: int) -> pd.DataFrame:
    metric = "model_distribution_uncertainty_index"
    if metric not in frame.columns:
        return pd.DataFrame()
    work = frame.dropna(subset=[metric, score_col]).copy()
    if work.empty:
        return pd.DataFrame()
    uncertainty_q25 = work[metric].quantile(0.25)
    uncertainty_q75 = work[metric].quantile(0.75)
    score_q75 = work[score_col].quantile(0.75)
    score_q25 = work[score_col].quantile(0.25)

    cases = []
    specs = [
        ("low_model_uncertainty_high_fpa", (work[metric] <= uncertainty_q25) & (work[score_col] >= score_q75), False),
        ("high_model_uncertainty_high_fpa", (work[metric] >= uncertainty_q75) & (work[score_col] >= score_q75), False),
        ("high_model_uncertainty_low_fpa", (work[metric] >= uncertainty_q75) & (work[score_col] <= score_q25), True),
        ("most_sensitive_overall", work[score_col].notna(), False),
    ]
    keep_cols = [
        col
        for col in [
            "dataset_name",
            "series_id",
            "window_id",
            "window_start",
            "branch_mode",
            "branch_step",
            "token_rank",
            "token_id",
            "token_probability",
            "token_surprisal",
            "normalized_token_entropy",
            "top1_top2_margin",
            "top1_probability",
            metric,
            "forced_token_implausibility_index",
            score_col,
            "instant_forking_score",
            "persistent_forking_score",
            "progressive_forking_score",
            "persistence_ratio",
            "topology_regime",
            "base_mae_over_window_scale",
        ]
        if col in work.columns
    ]
    for name, mask, ascending in specs:
        subset = work.loc[mask].sort_values(score_col, ascending=ascending).head(top_n).copy()
        if subset.empty:
            continue
        subset.insert(0, "case_type", name)
        cases.append(subset[["case_type"] + keep_cols])
    return pd.concat(cases, ignore_index=True) if cases else pd.DataFrame()


def _save_csv(path: Path, frame: pd.DataFrame, paths: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    paths.append(path)


def _scatter_plot(
    frame: pd.DataFrame,
    x_col: str,
    y_col: str,
    output_path: Path,
    title: str,
    xlabel: str,
    ylabel: str,
) -> Path | None:
    work = frame.dropna(subset=[x_col, y_col]).copy()
    if len(work) < 3:
        return None
    if len(work) > 5000:
        work = work.sample(5000, random_state=0)
    colors = None
    if "dataset_name" in work.columns:
        cats = pd.Categorical(work["dataset_name"].astype(str))
        colors = cats.codes
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.scatter(work[x_col], work[y_col], c=colors, s=18, alpha=0.65, cmap="tab10", edgecolors="none")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    if "dataset_name" in work.columns:
        datasets = pd.Categorical(work["dataset_name"].astype(str)).categories
        handles = [
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=plt.get_cmap("tab10")(i), markersize=7)
            for i, _ in enumerate(datasets)
        ]
        ax.legend(handles, datasets, title="dataset", loc="best", fontsize=8)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)
    return output_path


def _heatmap(corr_df: pd.DataFrame, output_path: Path, title: str) -> Path | None:
    if corr_df.empty:
        return None
    global_corr = corr_df[corr_df["group_name"] == "global"].copy()
    if global_corr.empty:
        return None
    pivot = global_corr.pivot_table(
        index="model_metric",
        columns="fpa_metric",
        values="spearman_corr",
        aggfunc="first",
    )
    if pivot.empty:
        return None
    fig_w = max(8.0, 0.8 * len(pivot.columns) + 3.0)
    fig_h = max(4.5, 0.45 * len(pivot.index) + 2.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    data = pivot.to_numpy(dtype=float)
    im = ax.imshow(data, vmin=-1, vmax=1, cmap="coolwarm", aspect="auto")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title(title)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if np.isfinite(data[i, j]):
                ax.text(j, i, f"{data[i, j]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label="Spearman correlation")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)
    return output_path


def _dataset_barplot(corr_df: pd.DataFrame, score_col: str, output_path: Path) -> Path | None:
    if corr_df.empty:
        return None
    metric = "model_distribution_uncertainty_index"
    work = corr_df[
        (corr_df["group_name"] == "dataset")
        & (corr_df["fpa_metric"] == score_col)
        & (corr_df["model_metric"].isin([metric, "token_surprisal", "token_rank", "token_probability"]))
    ].copy()
    if work.empty:
        return None
    pivot = work.pivot_table(index="group_value", columns="model_metric", values="spearman_corr", aggfunc="first")
    if pivot.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, max(4.5, 0.55 * len(pivot.index) + 1.5)))
    pivot.plot(kind="barh", ax=ax, width=0.8)
    ax.axvline(0.0, color="black", linewidth=0.8)
    ax.set_title("Model uncertainty vs FPA score by dataset")
    ax.set_xlabel("Spearman correlation")
    ax.set_ylabel("dataset")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)
    return output_path


def analyze_run_uncertainty_alignment(
    run_dir: str | Path,
    score_col: str | None = None,
    output_subdir: str = "recherche/model_uncertainty_alignment",
    top_n: int = 40,
) -> AlignmentOutputs:
    run_dir = Path(run_dir)
    summary_path = run_dir / "chronos_scan_summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing {summary_path}")

    summary, warnings = read_csv_robust(summary_path, context="analysis")
    validate_branch_keys(summary)
    resolved_score = _resolve_score_column(summary, score_col)
    frame = _prepare_analysis_frame(summary, resolved_score)
    base_rows = int(_is_base_branch(frame).sum())
    frame = frame[~_is_base_branch(frame)].copy()
    alternative_rows = len(frame)
    frame = frame.dropna(subset=["selected_fpa_score"])
    output_dir = run_dir / output_subdir
    figure_dir = output_dir / "figures"
    csv_paths: list[Path] = []
    figure_paths: list[Path] = []

    scale = normalization_scale_for_score(resolved_score)
    comparison_candidates = ["persistence_ratio"]
    if scale:
        comparison_candidates += [f"{scale}_scaled_{kind}_forking_score" for kind in ("instant", "persistent", "progressive")]
        comparison_candidates += [f"{period}_law_shift_over_{scale}" for period in ("early", "mid", "late", "peak")]
    fpa_cols = [resolved_score, "selected_fpa_score"] + [
        col for col in comparison_candidates if col in frame.columns
    ]
    fpa_cols = list(dict.fromkeys(fpa_cols))

    corr_df = _grouped_correlations(frame, fpa_cols)
    if not corr_df.empty:
        corr_df["observation_level"] = "branch"
    _save_csv(output_dir / "model_uncertainty_fpa_correlations.csv", corr_df, csv_paths)
    points = _aggregate_branch_points(frame, fpa_cols)
    point_corr = _grouped_correlations(points, fpa_cols)
    if not point_corr.empty:
        point_corr["observation_level"] = "branch_point"
    _save_csv(output_dir / "model_uncertainty_branch_points.csv", points, csv_paths)
    _save_csv(output_dir / "model_uncertainty_branch_point_correlations.csv", point_corr, csv_paths)

    quadrant_frame, quadrant_summary = _make_quadrants(frame, "selected_fpa_score")
    if not quadrant_frame.empty:
        keep = [
            col
            for col in [
                "uncertainty_fpa_quadrant",
                "dataset_name",
                "series_id",
                "window_id",
                "window_start",
                "branch_step",
                "token_rank",
                "token_probability",
                "token_surprisal",
                "normalized_token_entropy",
                "top1_top2_margin",
                "model_distribution_uncertainty_index",
                "selected_fpa_score",
                "persistence_ratio",
                "topology_regime",
            ]
            if col in quadrant_frame.columns
        ]
        _save_csv(output_dir / "model_uncertainty_fpa_quadrant_branches.csv", quadrant_frame[keep], csv_paths)
    _save_csv(output_dir / "model_uncertainty_fpa_quadrant_summary.csv", quadrant_summary, csv_paths)

    interesting = _interesting_branches(frame, "selected_fpa_score", top_n=top_n)
    _save_csv(output_dir / "model_uncertainty_interesting_branches.csv", interesting, csv_paths)

    dataset_summary_records = []
    if "dataset_name" in frame.columns:
        for dataset, subset in frame.groupby("dataset_name"):
            dataset_summary_records.append(
                {
                    "dataset_name": dataset,
                    "rows": int(len(subset)),
                    "windows": int(len(subset[WINDOW_KEY_COLS].drop_duplicates()))
                    if set(WINDOW_KEY_COLS).issubset(subset.columns)
                    else np.nan,
                    "median_fpa_score": float(subset["selected_fpa_score"].median()),
                    "p90_fpa_score": float(subset["selected_fpa_score"].quantile(0.90)),
                    "median_model_distribution_uncertainty_index": float(
                        subset["model_distribution_uncertainty_index"].median()
                    )
                    if "model_distribution_uncertainty_index" in subset.columns
                    else np.nan,
                    "median_token_probability": float(subset["token_probability"].median())
                    if "token_probability" in subset.columns
                    else np.nan,
                    "median_token_rank": float(subset["token_rank"].median())
                    if "token_rank" in subset.columns
                    else np.nan,
                }
            )
    dataset_summary = pd.DataFrame(dataset_summary_records)
    _save_csv(output_dir / "model_uncertainty_dataset_summary.csv", dataset_summary, csv_paths)

    figure_specs = [
        (
            "model_distribution_uncertainty_index",
            "selected_fpa_score",
            "score_vs_model_distribution_uncertainty.png",
            "FPA shift vs Chronos distribution uncertainty",
            "Chronos distribution uncertainty index (higher = more uncertain)",
            f"FPA score ({resolved_score})",
        ),
        (
            "token_probability",
            "selected_fpa_score",
            "score_vs_token_probability.png",
            "FPA shift vs forced-token probability",
            "P(token force | context + greedy prefix)",
            f"FPA score ({resolved_score})",
        ),
        (
            "token_surprisal",
            "selected_fpa_score",
            "score_vs_token_surprisal.png",
            "FPA shift vs forced-token surprisal",
            "-log P(token force | context + greedy prefix)",
            f"FPA score ({resolved_score})",
        ),
        (
            "token_rank",
            "selected_fpa_score",
            "score_vs_token_rank.png",
            "FPA shift vs forced-token rank",
            "forced token rank among tested alternatives",
            f"FPA score ({resolved_score})",
        ),
    ]
    for x_col, y_col, filename, title, xlabel, ylabel in figure_specs:
        if x_col in frame.columns and y_col in frame.columns:
            path = _scatter_plot(frame, x_col, y_col, figure_dir / filename, title, xlabel, ylabel)
            if path:
                figure_paths.append(path)

    path = _heatmap(corr_df, figure_dir / "model_uncertainty_fpa_correlation_heatmap.png", "Model uncertainty vs FPA metrics")
    if path:
        figure_paths.append(path)
    path = _dataset_barplot(corr_df, "selected_fpa_score", figure_dir / "model_uncertainty_correlations_by_dataset.png")
    if path:
        figure_paths.append(path)

    payload = {
        "analysis_version": ANALYSIS_VERSION,
        "run_dir": str(run_dir),
        "summary_path": str(summary_path),
        "score_column": resolved_score,
        "normalization_scale": scale,
        "comparison_fpa_columns": fpa_cols,
        "rows_total": int(len(summary)),
        "rows_alternative": int(len(frame)),
        "rows_base_excluded": base_rows,
        "rows_alternative_before_score_filter": alternative_rows,
        "rows_invalid_score_excluded": alternative_rows - len(frame),
        "branch_points": int(len(points)),
        "branch_point_key_columns": GROUP_KEY_COLS,
        "output_dir": str(output_dir),
        "csv_outputs": [str(path) for path in csv_paths],
        "figure_outputs": [str(path) for path in figure_paths],
        "notes": [
            "Base-token branches are excluded.",
            "model_distribution_uncertainty_index averages percentile ranks of entropy, inverse top1-top2 margin, and inverse top1 probability when available.",
            "forced_token_implausibility_index is stored separately because token improbability is not the same object as model distribution uncertainty.",
            "Percentile ranks use average ties over all input summary rows BEFORE base-branch and invalid-score filtering; original branch-level formulas are preserved.",
            "A constant rank component uses its average percentile rank; a component with fewer than two finite values is undefined. Available components are averaged rowwise.",
            "Branch-point tables use one row per complete group key, with unweighted arithmetic means over retained alternative branches for every metric, including precomputed indices. Branch points receive equal weight in their correlations.",
            "Correlations use pairwise-complete finite observations, require at least three pairs and nonconstant metrics, and report undefined results explicitly. Spearman uses average ranks for ties.",
            "Both observation levels are descriptive; repeated branches and branch points are not asserted to be statistically independent. No inferential significance is claimed.",
        ],
        "warnings": warnings,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "model_uncertainty_alignment_summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    csv_paths.append(output_dir / "model_uncertainty_alignment_summary.json")
    return AlignmentOutputs(output_dir=output_dir, csv_paths=csv_paths, figure_paths=figure_paths, warnings=warnings)
