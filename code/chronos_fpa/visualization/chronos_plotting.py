from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import numpy as np
import pandas as pd


def _token_suffix_columns(predictions_df: pd.DataFrame) -> List[str]:
    suffixes = []
    for col in predictions_df.columns:
        if col.startswith("token_") and col.endswith("_q50"):
            suffixes.append(col[: -len("_q50")])
    return suffixes


def _x_values(predictions_df: pd.DataFrame):
    if "date" not in predictions_df.columns:
        return np.arange(len(predictions_df))
    dates = pd.to_datetime(predictions_df["date"], errors="coerce")
    if dates.notna().all():
        return dates
    return np.arange(len(predictions_df))


def plot_chronos_forecast_branches(predictions_df: pd.DataFrame, output_path: str | Path) -> Path:
    """Plot GT, greedy path, and q10/q50/q90 fan charts for each token branch."""
    import matplotlib.pyplot as plt

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    x = _x_values(predictions_df)
    fig, ax = plt.subplots(figsize=(12, 6))

    if "gt" in predictions_df.columns:
        ax.plot(x, predictions_df["gt"], marker="o", linewidth=1.5, label="ground truth")
    if "base_greedy" in predictions_df.columns:
        ax.plot(x, predictions_df["base_greedy"], linestyle="--", linewidth=1.5, label="base greedy")

    for suffix in _token_suffix_columns(predictions_df):
        q10_col = f"{suffix}_q10"
        q50_col = f"{suffix}_q50"
        q90_col = f"{suffix}_q90"
        if not {q10_col, q50_col, q90_col}.issubset(predictions_df.columns):
            continue
        ax.plot(x, predictions_df[q50_col], linewidth=1.2, label=f"{suffix} q50")
        ax.fill_between(
            x,
            predictions_df[q10_col].astype(float),
            predictions_df[q90_col].astype(float),
            alpha=0.15,
        )

    ax.set_title("Chronos token-bin FPA: forecast branches")
    ax.set_xlabel("forecast step / date")
    ax.set_ylabel("forecast value")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_chronos_forecast_branches_model_only(predictions_df: pd.DataFrame, output_path: str | Path) -> Path:
    """Same as forecast plot, but without ground truth so tiny branch differences remain visible."""
    import matplotlib.pyplot as plt

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    x = _x_values(predictions_df)
    fig, ax = plt.subplots(figsize=(12, 6))

    if "base_greedy" in predictions_df.columns:
        ax.plot(x, predictions_df["base_greedy"], linestyle="--", linewidth=1.5, label="base greedy")

    for suffix in _token_suffix_columns(predictions_df):
        q10_col = f"{suffix}_q10"
        q50_col = f"{suffix}_q50"
        q90_col = f"{suffix}_q90"
        if not {q10_col, q50_col, q90_col}.issubset(predictions_df.columns):
            continue
        ax.plot(x, predictions_df[q50_col], linewidth=1.2, label=f"{suffix} q50")
        ax.fill_between(
            x,
            predictions_df[q10_col].astype(float),
            predictions_df[q90_col].astype(float),
            alpha=0.15,
        )

    ax.set_title("Chronos token-bin FPA: forecast branches, model-only zoom")
    ax.set_xlabel("forecast step / date")
    ax.set_ylabel("forecast value")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_chronos_law_shift(step_df: pd.DataFrame, output_path: str | Path) -> Path:
    """Plot law_shift_h across the forecast horizon for every forced token branch."""
    import matplotlib.pyplot as plt

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 5))
    for token_id, grp in step_df.groupby("token_id", sort=False):
        grp = grp.sort_values("forecast_step")
        is_base = bool(grp["is_base_token"].iloc[0]) if "is_base_token" in grp else False
        label = f"token {token_id}" + (" (base)" if is_base else "")
        ax.plot(grp["forecast_step"], grp["law_shift_h"], marker="o", linewidth=1.4, label=label)

    if "branch_step" in step_df.columns and not step_df.empty:
        branch_step = int(step_df["branch_step"].iloc[0])
        ax.axvline(branch_step, linestyle="--", linewidth=1.0, label="branch step")

    ax.set_title("Chronos token-bin FPA: law shift by forecast step")
    ax.set_xlabel("forecast step")
    ax.set_ylabel("mean |branch quantiles - base quantiles|")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_chronos_branch_scores(summary_df: pd.DataFrame, output_path: str | Path) -> Path:
    """Plot progressive token-bin forking score for each branch."""
    import matplotlib.pyplot as plt

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if summary_df.empty:
        raise ValueError("summary_df is empty; cannot plot branch scores.")

    score_col = "progressive_token_bin_forking_score"
    ordered = summary_df.sort_values(score_col, ascending=True).copy()
    labels = [
        f"token {int(row.token_id)}" + (" (base)" if bool(row.is_base_token) else "")
        for row in ordered.itertuples(index=False)
    ]

    fig, ax = plt.subplots(figsize=(9, max(3, 0.45 * len(ordered) + 1.5)))
    ax.barh(labels, ordered[score_col].astype(float))
    ax.set_title("Chronos token-bin FPA: branch ranking")
    ax.set_xlabel(score_col)
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_chronos_token_probabilities(alternatives_df: pd.DataFrame, output_path: str | Path) -> Path:
    """Plot top-k token-bin probabilities at the forced branch step."""
    import matplotlib.pyplot as plt

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if alternatives_df.empty:
        raise ValueError("alternatives_df is empty; cannot plot token probabilities.")

    df = alternatives_df.sort_values("rank", ascending=True).copy()
    labels = [
        f"rank {int(row.rank)}\ntoken {int(row.token_id)}" + ("\nbase" if bool(row.is_base_token) else "")
        for row in df.itertuples(index=False)
    ]

    fig, ax = plt.subplots(figsize=(max(6, 1.2 * len(df)), 4))
    ax.bar(labels, df["probability"].astype(float))
    ax.set_title("Chronos token-bin FPA: top-k token probabilities")
    ax.set_ylabel("probability")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def plot_chronos_all_outputs(
    run_dir: str | Path,
    predictions_df: pd.DataFrame,
    step_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    alternatives_df: pd.DataFrame,
) -> List[Path]:
    """Generate all standard Chronos token-bin FPA figures into run_dir/figures."""
    run_dir = Path(run_dir)
    figures_dir = run_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    outputs: List[Path] = []
    outputs.append(plot_chronos_forecast_branches(predictions_df, figures_dir / "chronos_forecast_branches.png"))
    outputs.append(plot_chronos_forecast_branches_model_only(predictions_df, figures_dir / "chronos_forecast_branches_model_only.png"))
    outputs.append(plot_chronos_law_shift(step_df, figures_dir / "chronos_law_shift_by_step.png"))
    outputs.append(plot_chronos_branch_scores(summary_df, figures_dir / "chronos_branch_scores.png"))
    outputs.append(plot_chronos_token_probabilities(alternatives_df, figures_dir / "chronos_token_probabilities.png"))
    return outputs

