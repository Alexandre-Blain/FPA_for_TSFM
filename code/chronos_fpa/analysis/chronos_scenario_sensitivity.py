from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from chronos_analysis_helpers import (
    is_base_branch as _is_base_branch,
    numeric as _numeric,
    read_csv_robust as _read_csv_robust,
    resolve_score_column,
)
from research_schema import validate_branch_keys
from chronos_scales import NORMALIZED_SCORE_SPECS, normalization_scale_for_score
from research_schema import ANALYSIS_VERSION, GROUP_KEY_COLS


BRANCH_KEY_COLS = GROUP_KEY_COLS + ["token_id"]

OPTIONAL_SUMMARY_COLS = [
    "token_rank",
    "token_probability",
    "token_surprisal",
    "normalized_token_entropy",
    "top1_top2_margin",
    "top1_probability",
    "model_distribution_uncertainty_index",
    "topology_regime",
    "base_mae_over_window_scale",
    "window_scale",
    "context_iqr",
    "context_std",
    "context_range",
    "gt_iqr",
]


@dataclass(frozen=True)
class ScenarioOutputs:
    output_dir: Path
    csv_paths: list[Path]
    figure_paths: list[Path]
    warnings: list[str]


def _decision_scale(summary_row: pd.Series, scale_col: str = "context_iqr") -> float:
    value = _numeric(pd.Series([summary_row.get(scale_col, np.nan)])).iloc[0]
    return float(value) if pd.notna(value) and value > 0 else np.nan


def _direction_label(delta: float, threshold: float) -> str:
    if delta > threshold:
        return "up"
    if delta < -threshold:
        return "down"
    return "flat"


def _time_bin(index: int, n: int) -> str:
    if n <= 0:
        return "unknown"
    frac = (index + 1) / n
    if frac <= 1 / 3:
        return "early"
    if frac <= 2 / 3:
        return "middle"
    return "late"


def _unique_extremum_index(values: np.ndarray, maximum: bool) -> float:
    extreme = np.max(values) if maximum else np.min(values)
    matches = np.flatnonzero(values == extreme)
    return float(matches[0]) if len(matches) == 1 else np.nan


def _scenario_records_for_branch(
    grp: pd.DataFrame,
    summary_row: pd.Series,
    score_col: str | None,
    scale_col: str = "context_iqr",
) -> list[dict]:
    grp = grp.sort_values("forecast_step").copy()
    post = grp[grp["relative_step_after_branch"] >= 0].copy()
    if post.empty:
        return []

    base_q10 = _numeric(post["base_q10"]).to_numpy(dtype=float)
    base_q50 = _numeric(post["base_q50"]).to_numpy(dtype=float)
    base_q90 = _numeric(post["base_q90"]).to_numpy(dtype=float)
    branch_q10 = _numeric(post["branch_q10"]).to_numpy(dtype=float)
    branch_q50 = _numeric(post["branch_q50"]).to_numpy(dtype=float)
    branch_q90 = _numeric(post["branch_q90"]).to_numpy(dtype=float)
    if not all(np.isfinite(values).all() for values in (
        base_q10, base_q50, base_q90, branch_q10, branch_q50, branch_q90,
    )):
        return []

    scale = _decision_scale(summary_row, scale_col)
    if not np.isfinite(scale):
        return []
    threshold = 0.25 * scale
    direction_threshold = 0.10 * scale
    start = float(base_q50[0])

    base_final_delta = float(base_q50[-1] - start)
    branch_final_delta = float(branch_q50[-1] - start)
    base_direction = _direction_label(base_final_delta, direction_threshold)
    branch_direction = _direction_label(branch_final_delta, direction_threshold)

    high_threshold = start + threshold
    low_threshold = start - threshold
    base_high = bool(np.nanmax(base_q50) >= high_threshold)
    branch_high = bool(np.nanmax(branch_q50) >= high_threshold)
    base_low = bool(np.nanmin(base_q50) <= low_threshold)
    branch_low = bool(np.nanmin(branch_q50) <= low_threshold)

    base_risk_low = bool(np.nanmin(base_q10) <= low_threshold)
    branch_risk_low = bool(np.nanmin(branch_q10) <= low_threshold)
    base_risk_high = bool(np.nanmax(base_q90) >= high_threshold)
    branch_risk_high = bool(np.nanmax(branch_q90) >= high_threshold)

    base_peak_idx = _unique_extremum_index(base_q50, maximum=True)
    branch_peak_idx = _unique_extremum_index(branch_q50, maximum=True)
    base_trough_idx = _unique_extremum_index(base_q50, maximum=False)
    branch_trough_idx = _unique_extremum_index(branch_q50, maximum=False)
    n = len(base_q50)
    base_peak_bin = _time_bin(base_peak_idx, n) if np.isfinite(base_peak_idx) else "undefined"
    branch_peak_bin = _time_bin(branch_peak_idx, n) if np.isfinite(branch_peak_idx) else "undefined"
    base_trough_bin = _time_bin(base_trough_idx, n) if np.isfinite(base_trough_idx) else "undefined"
    branch_trough_bin = _time_bin(branch_trough_idx, n) if np.isfinite(branch_trough_idx) else "undefined"

    branch_minus_base_final = branch_final_delta - base_final_delta
    branch_minus_base_peak = float(np.nanmax(branch_q50) - np.nanmax(base_q50))
    branch_minus_base_trough = float(np.nanmin(branch_q50) - np.nanmin(base_q50))

    base = {
        "analysis_version": ANALYSIS_VERSION,
        "decision_scale_column": scale_col,
        "decision_scale": scale,
        "decision_threshold": threshold,
        "direction_threshold": direction_threshold,
        "base_start_q50": start,
        "base_final_delta_over_scale": base_final_delta / scale,
        "branch_final_delta_over_scale": branch_final_delta / scale,
        "branch_minus_base_final_over_scale": branch_minus_base_final / scale,
        "branch_minus_base_peak_over_scale": branch_minus_base_peak / scale,
        "branch_minus_base_trough_over_scale": branch_minus_base_trough / scale,
        "selected_fpa_score": summary_row.get(score_col, np.nan) if score_col else np.nan,
    }
    for col in OPTIONAL_SUMMARY_COLS:
        if col in summary_row.index:
            base[col] = summary_row[col]

    scenarios = [
        {
            "scenario_name": "final_direction",
            "base_status": base_direction,
            "branch_status": branch_direction,
            "scenario_changed": base_direction != branch_direction,
            "scenario_change_type": f"{base_direction}_to_{branch_direction}",
            "scenario_margin_over_scale": abs(branch_minus_base_final) / scale,
        },
        {
            "scenario_name": "upside_threshold_crossing",
            "base_status": str(base_high),
            "branch_status": str(branch_high),
            "scenario_changed": base_high != branch_high,
            "scenario_change_type": "triggered" if branch_high and not base_high else "cancelled" if base_high and not branch_high else "unchanged",
            "scenario_margin_over_scale": abs(branch_minus_base_peak) / scale,
        },
        {
            "scenario_name": "downside_threshold_crossing",
            "base_status": str(base_low),
            "branch_status": str(branch_low),
            "scenario_changed": base_low != branch_low,
            "scenario_change_type": "triggered" if branch_low and not base_low else "cancelled" if base_low and not branch_low else "unchanged",
            "scenario_margin_over_scale": abs(branch_minus_base_trough) / scale,
        },
        {
            "scenario_name": "risk_band_breach",
            "base_status": str(base_risk_low or base_risk_high),
            "branch_status": str(branch_risk_low or branch_risk_high),
            "scenario_changed": (base_risk_low or base_risk_high) != (branch_risk_low or branch_risk_high),
            "scenario_change_type": "triggered"
            if (branch_risk_low or branch_risk_high) and not (base_risk_low or base_risk_high)
            else "cancelled"
            if (base_risk_low or base_risk_high) and not (branch_risk_low or branch_risk_high)
            else "unchanged",
            "scenario_margin_over_scale": max(
                abs(float(np.nanmin(branch_q10) - np.nanmin(base_q10))),
                abs(float(np.nanmax(branch_q90) - np.nanmax(base_q90))),
            )
            / scale,
        },
        {
            "scenario_name": "peak_timing_bin",
            "base_status": base_peak_bin,
            "branch_status": branch_peak_bin,
            "scenario_changed": base_peak_bin != branch_peak_bin,
            "scenario_change_type": f"{base_peak_bin}_to_{branch_peak_bin}",
            "scenario_margin_over_scale": abs(branch_peak_idx - base_peak_idx) / max(n - 1, 1),
        },
        {
            "scenario_name": "trough_timing_bin",
            "base_status": base_trough_bin,
            "branch_status": branch_trough_bin,
            "scenario_changed": base_trough_bin != branch_trough_bin,
            "scenario_change_type": f"{base_trough_bin}_to_{branch_trough_bin}",
            "scenario_margin_over_scale": abs(branch_trough_idx - base_trough_idx) / max(n - 1, 1),
        },
    ]

    key_values = {col: grp[col].iloc[0] for col in BRANCH_KEY_COLS if col in grp.columns}
    records = []
    for scenario in scenarios:
        defined = "undefined" not in (scenario["base_status"], scenario["branch_status"])
        scenario["scenario_defined"] = defined
        scenario["undefined_reason"] = "" if defined else "nonunique_extremum"
        if not defined:
            scenario["scenario_changed"] = np.nan
            scenario["scenario_change_type"] = "undefined"
            scenario["scenario_margin_over_scale"] = np.nan
        row = {**key_values, **base, **scenario}
        row["scenario_decision_shift_score"] = (
            float(row["scenario_changed"]) * (1.0 + float(row["scenario_margin_over_scale"]))
        )
        records.append(row)
    return records


def _prepare_summary(summary: pd.DataFrame, score_col: str | None, scale_col: str = "context_iqr") -> pd.DataFrame:
    summary = summary.copy()
    for col in summary.columns:
        if (
            col in [c for c in OPTIONAL_SUMMARY_COLS if c != "topology_regime"]
            or col in (score_col, scale_col)
            or "forking_score" in col
            or col.startswith("token_")
            or col.startswith("top1_")
            or col.startswith("normalized_")
            or col.endswith("_scale")
        ):
            summary[col] = _numeric(summary[col])
    summary = summary[~_is_base_branch(summary)].copy()
    keep = list(dict.fromkeys(col for col in BRANCH_KEY_COLS + OPTIONAL_SUMMARY_COLS + [scale_col] + ([score_col] if score_col else []) if col in summary.columns))
    return summary[keep]


def _save_csv(path: Path, frame: pd.DataFrame, paths: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    paths.append(path)


def _summarize_scenarios(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    return (
        frame.groupby(group_cols, dropna=False)
        .agg(
            rows=("scenario_changed", "size"),
            defined=("scenario_changed", "count"),
            undefined=("scenario_changed", lambda s: int(s.isna().sum())),
            changed=("scenario_changed", "sum"),
            changed_rate=("scenario_changed", "mean"),
            median_decision_shift_score=("scenario_decision_shift_score", "median"),
            p90_decision_shift_score=("scenario_decision_shift_score", lambda s: s.quantile(0.90)),
            median_fpa_score=("selected_fpa_score", "median"),
        )
        .reset_index()
    )


def _plot_change_rates(summary: pd.DataFrame, output_path: Path) -> Path | None:
    if summary.empty:
        return None
    work = summary.dropna(subset=["changed_rate"]).sort_values("changed_rate", ascending=True)
    if work.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.barh(work["scenario_name"], work["changed_rate"], color="#246BFE", alpha=0.82)
    ax.set_xlabel("Decision-change rate")
    ax.set_ylabel("scenario")
    ax.set_title("How often does branching change a generic scenario?")
    ax.grid(True, axis="x", alpha=0.25)
    for i, (_, row) in enumerate(work.iterrows()):
        ax.text(row["changed_rate"] + 0.005, i, f"{row['changed_rate']:.1%}", va="center", fontsize=9)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)
    return output_path


def _plot_dataset_heatmap(dataset_summary: pd.DataFrame, output_path: Path) -> Path | None:
    if dataset_summary.empty:
        return None
    pivot = dataset_summary.pivot_table(
        index="dataset_name",
        columns="scenario_name",
        values="changed_rate",
        aggfunc="first",
    )
    if pivot.empty:
        return None
    fig, ax = plt.subplots(figsize=(max(8, len(pivot.columns) * 1.2), max(3.8, len(pivot.index) * 0.55 + 1.5)))
    data = pivot.to_numpy(dtype=float)
    im = ax.imshow(data, vmin=0, vmax=max(0.01, np.nanmax(data)), cmap="YlOrRd", aspect="auto")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("Decision-change rate by dataset")
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if np.isfinite(data[i, j]):
                ax.text(j, i, f"{data[i, j]:.0%}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label="change rate")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)
    return output_path


def _plot_fpa_vs_decision(frame: pd.DataFrame, output_path: Path) -> Path | None:
    required = {"selected_fpa_score", "scenario_decision_shift_score", "scenario_name"}
    if frame.empty or not required.issubset(frame.columns):
        return None
    work = frame.dropna(subset=["selected_fpa_score", "scenario_decision_shift_score"]).copy()
    if work.empty:
        return None
    if len(work) > 8000:
        work = work.sample(8000, random_state=0)
    cats = pd.Categorical(work["scenario_name"].astype(str))
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.scatter(
        work["selected_fpa_score"],
        work["scenario_decision_shift_score"],
        c=cats.codes,
        cmap="tab10",
        alpha=0.6,
        s=16,
        edgecolors="none",
    )
    ax.set_xlabel("FPA score")
    ax.set_ylabel("scenario decision-shift score")
    ax.set_title("FPA magnitude vs scenario-level decision change")
    ax.grid(True, alpha=0.25)
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=plt.get_cmap("tab10")(i), markersize=7)
        for i, _ in enumerate(cats.categories)
    ]
    ax.legend(handles, cats.categories, title="scenario", loc="best", fontsize=7)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)
    return output_path


def _plot_example_branch(steps: pd.DataFrame, branch_row: pd.Series, output_path: Path) -> Path | None:
    mask = pd.Series(True, index=steps.index)
    for col in BRANCH_KEY_COLS:
        if col in steps.columns and col in branch_row.index:
            mask &= steps[col].astype(str) == str(branch_row[col])
    grp = steps.loc[mask].sort_values("forecast_step")
    if grp.empty:
        return None
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    x = _numeric(grp["forecast_step"]).to_numpy()
    for prefix, color, label in [("base", "#246BFE", "base"), ("branch", "#E76F51", "branch")]:
        q10 = _numeric(grp[f"{prefix}_q10"]).to_numpy()
        q50 = _numeric(grp[f"{prefix}_q50"]).to_numpy()
        q90 = _numeric(grp[f"{prefix}_q90"]).to_numpy()
        ax.fill_between(x, q10, q90, color=color, alpha=0.14)
        ax.plot(x, q50, color=color, linewidth=2.0, label=f"{label} q50")
    ax.axvline(float(branch_row.get("branch_step", 0)), color="#0D1B2A", linestyle="--", linewidth=1.0, label="branch_step")
    title = (
        f"{branch_row.get('scenario_name', '')}: {branch_row.get('dataset_name', '')}/"
        f"{branch_row.get('series_id', '')} w{branch_row.get('window_id', '')}"
    )
    ax.set_title(title)
    ax.set_xlabel("forecast step")
    ax.set_ylabel("forecast value")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=9)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)
    return output_path


def analyze_run_scenario_sensitivity(
    run_dir: str | Path,
    score_col: str | None = None,
    output_subdir: str = "recherche/scenario_sensitivity",
    top_n: int = 40,
    scale_col: str = "context_iqr",
) -> ScenarioOutputs:
    run_dir = Path(run_dir)
    steps_path = run_dir / "chronos_scan_steps.csv"
    summary_path = run_dir / "chronos_scan_summary.csv"
    if not steps_path.exists():
        raise FileNotFoundError(f"Missing {steps_path}")

    warnings: list[str] = []
    steps, step_warnings = _read_csv_robust(steps_path)
    warnings.extend(step_warnings)
    summary = pd.DataFrame()
    if summary_path.exists():
        summary, summary_warnings = _read_csv_robust(summary_path)
        warnings.extend(summary_warnings)
    validate_branch_keys(summary)
    validate_branch_keys(steps, steps=True)
    if not steps["branch_mode"].eq("single").all():
        raise ValueError("Scenario analysis currently supports single-token branches only")

    if score_col is None:
        score_col = next((progressive for scale, _, progressive in NORMALIZED_SCORE_SPECS if scale == scale_col), None)
        if score_col is None:
            raise ValueError(f"Decision scale {scale_col!r} has no saved normalized score convention")
    resolved_score = resolve_score_column(summary, score_col)
    if normalization_scale_for_score(resolved_score) != scale_col:
        raise ValueError("Scenario decisions and FPA score must use the same normalization column")
    if scale_col not in summary.columns:
        raise ValueError(f"Decision scale column {scale_col!r} is missing from {summary_path}.")
    summary_work = _prepare_summary(summary, resolved_score, scale_col)

    for col in [
        "forecast_step",
        "relative_step_after_branch",
        "branch_step",
        "token_id",
        "token_rank",
        "base_q10",
        "base_q50",
        "base_q90",
        "branch_q10",
        "branch_q50",
        "branch_q90",
    ]:
        if col in steps.columns:
            steps[col] = _numeric(steps[col])
    steps = steps[~_is_base_branch(steps)].copy()

    records: list[dict] = []
    excluded: list[dict] = []
    summary_index = {}
    if not summary_work.empty:
        summary_index = {
            tuple(row[col] for col in BRANCH_KEY_COLS): row
            for _, row in summary_work.iterrows()
            if set(BRANCH_KEY_COLS).issubset(summary_work.columns)
        }

    for key, grp in steps.groupby(BRANCH_KEY_COLS, dropna=False, sort=False):
        summary_row = summary_index.get(tuple(key), pd.Series(dtype=object))
        branch_records = _scenario_records_for_branch(grp, summary_row, resolved_score, scale_col)
        if not branch_records:
            reason = "invalid_decision_scale" if not np.isfinite(_decision_scale(summary_row, scale_col)) else "invalid_or_missing_post_branch_forecast"
            excluded.append({**dict(zip(BRANCH_KEY_COLS, key)), "reason": reason, "decision_scale_column": scale_col})
        records.extend(branch_records)

    scenario_df = pd.DataFrame(records)
    output_dir = run_dir / output_subdir
    figure_dir = output_dir / "figures"
    csv_paths: list[Path] = []
    figure_paths: list[Path] = []
    excluded_df = pd.DataFrame(excluded, columns=BRANCH_KEY_COLS + ["reason", "decision_scale_column"])
    _save_csv(output_dir / "scenario_excluded_branches.csv", excluded_df, csv_paths)
    if excluded:
        warnings.append(f"Excluded {len(excluded)} branches: {excluded_df['reason'].value_counts().to_dict()}.")

    if scenario_df.empty:
        warnings.append("No scenario records generated.")
    else:
        scenario_df["scenario_changed"] = _numeric(scenario_df["scenario_changed"])
        scenario_summary = (
            _summarize_scenarios(scenario_df, ["scenario_name"])
            .sort_values("changed_rate", ascending=False)
        )
        dataset_summary = (
            _summarize_scenarios(scenario_df, ["dataset_name", "scenario_name"])
            .sort_values(["dataset_name", "changed_rate"], ascending=[True, False])
        )
        interesting_pool = scenario_df[scenario_df["scenario_changed"] == 1].copy()
        if "selected_fpa_score" in interesting_pool.columns and interesting_pool["selected_fpa_score"].notna().any():
            scored_pool = interesting_pool[interesting_pool["selected_fpa_score"].notna()].copy()
        else:
            scored_pool = interesting_pool
        interesting = (
            scored_pool.sort_values(
                ["scenario_decision_shift_score", "selected_fpa_score"],
                ascending=False,
                na_position="last",
            )
            .head(top_n)
            .copy()
        )

        _save_csv(output_dir / "scenario_branch_decisions.csv", scenario_df, csv_paths)
        _save_csv(output_dir / "scenario_summary.csv", scenario_summary, csv_paths)
        _save_csv(output_dir / "scenario_dataset_summary.csv", dataset_summary, csv_paths)
        _save_csv(output_dir / "scenario_interesting_branches.csv", interesting, csv_paths)

        for path in [
            _plot_change_rates(scenario_summary, figure_dir / "scenario_change_rates.png"),
            _plot_dataset_heatmap(dataset_summary, figure_dir / "scenario_change_rates_by_dataset.png"),
            _plot_fpa_vs_decision(scenario_df, figure_dir / "scenario_fpa_vs_decision_shift.png"),
        ]:
            if path:
                figure_paths.append(path)

        if not interesting.empty:
            for i, (_, row) in enumerate(interesting.head(4).iterrows(), start=1):
                path = _plot_example_branch(steps, row, figure_dir / f"scenario_example_{i}.png")
                if path:
                    figure_paths.append(path)

    payload = {
        "analysis_version": ANALYSIS_VERSION,
        "run_dir": str(run_dir),
        "steps_path": str(steps_path),
        "summary_path": str(summary_path) if summary_path.exists() else None,
        "score_column": resolved_score,
        "decision_scale_column": scale_col,
        "branches_excluded": len(excluded),
        "exclusion_counts": excluded_df["reason"].value_counts().to_dict(),
        "branches_analyzed": len(scenario_df) // 6,
        "undefined_scenario_decisions": int(scenario_df["scenario_changed"].isna().sum()) if not scenario_df.empty else 0,
        "output_dir": str(output_dir),
        "warnings": warnings,
        "scenario_definitions": {
            "final_direction": "Final branch q50 direction relative to the base first q50, with flat band = 0.10 * decision_scale.",
            "upside_threshold_crossing": "Whether max q50 crosses base_start + 0.25 * decision_scale.",
            "downside_threshold_crossing": "Whether min q50 crosses base_start - 0.25 * decision_scale.",
            "risk_band_breach": "Whether q10/q90 interval breaches either decision threshold.",
            "peak_timing_bin": "Whether the peak q50 time bin changes among early/middle/late.",
            "trough_timing_bin": "Whether the trough q50 time bin changes among early/middle/late.",
        },
        "notes": [
            "This is not a domain action model. It is a generic decision-sensitivity probe.",
            "A scenario change means the branch changes a rule outcome compared with the forced-base branch.",
            "One decision scale column is selected for the entire analysis; missing, nonfinite, zero, and negative scales are excluded without fallback.",
            "Direction uses strict >/< 0.10 * scale; threshold crossings and interval breaches include equality at 0.25 * scale.",
            "Extrema must be unique (exact equality identifies ties); tied extrema have undefined timing, even within one time bin.",
            "Undefined decisions are excluded from change-rate denominators, not counted as unchanged.",
            "Correlations and change rates are descriptive; branches are not independent observations.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_json = output_dir / "scenario_sensitivity_summary.json"
    summary_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    csv_paths.append(summary_json)
    return ScenarioOutputs(output_dir=output_dir, csv_paths=csv_paths, figure_paths=figure_paths, warnings=warnings)
