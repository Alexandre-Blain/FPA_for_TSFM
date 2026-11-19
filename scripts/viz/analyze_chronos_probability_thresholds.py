"""Compare stored single-token branches at probability cutoffs, without inference."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code" / "chronos_fpa"))
import bootstrap
from chronos_uncertainty_alignment import prepare_uncertainty_metrics
from research_schema import ANALYSIS_VERSION, read_csv, is_base_branch
from chronos_scales import NORMALIZED_SCORE_SPECS

DEFAULT_SCORE = "context_iqr_scaled_progressive_token_bin_forking_score"
WINDOW = ["dataset_name", "series_id", "window_id", "window_start"]
GROUP = WINDOW + ["branch_mode", "branch_step"]
BRANCH = GROUP + ["token_id"]
METRICS = [
    "normalized_token_entropy", "token_entropy", "model_distribution_uncertainty_index",
    "top1_top2_margin", "inverse_top1_top2_margin", "top1_probability",
    "inverse_top1_probability", "token_probability", "token_surprisal", "token_rank",
]
COLORS = {"ercot": "#267FAD", "exchange_rate": "#D97825", "m4_daily": "#389455"}


def threshold_name(value: float) -> str:
    return "unfiltered" if value == 0 else "p_ge_" + f"{value:g}".replace(".", "p")


def threshold_label(value: float) -> str:
    return "Unfiltered" if value == 0 else f"p >= {100 * value:g}%"


def prepare_branches(summary: pd.DataFrame, score: str) -> pd.DataFrame:
    required = set(BRANCH + [score, "token_probability", "normalized_token_entropy", "is_base_token"])
    missing = required.difference(summary.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    frame = summary.copy()
    if not frame["branch_mode"].eq("single").all():
        raise ValueError("This analysis expects single-token branches, not bundles.")
    if frame[BRANCH].isna().any().any() or frame.duplicated(BRANCH).any():
        raise ValueError("Missing identifiers or duplicate branches in source summary.")
    # Match the existing alignment study: build percentile indices on the complete
    # source frame, then freeze them before excluding bases and applying cutoffs.
    for column in set(METRICS + [score, "base_mae_over_context_iqr"]):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
    probability = frame["token_probability"]
    if not (np.isfinite(probability) & probability.between(0, 1)).all():
        raise ValueError("Token probabilities must be finite and in [0, 1].")
    frame = prepare_uncertainty_metrics(frame)
    frame = frame.loc[~is_base_branch(frame)].copy()
    if not np.isfinite(frame[score]).all():
        raise ValueError("The selected score must be finite for every alternative.")
    return frame


def populations(frame: pd.DataFrame, datasets: list[str]):
    yield "all", frame
    for dataset in datasets:
        yield dataset, frame.loc[frame.dataset_name == dataset]


def correlation(x: pd.Series, y: pd.Series, rank: bool = False) -> tuple[int, float]:
    pair = pd.concat([x.rename("x"), y.rename("y")], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(pair) < 3 or pair.x.nunique() < 2 or pair.y.nunique() < 2:
        return len(pair), float("nan")
    if rank:
        pair = pair.rank(method="average")
    return len(pair), float(pair.x.corr(pair.y))


def compare_thresholds(frame: pd.DataFrame, thresholds: list[float], score: str):
    datasets = sorted(frame.dataset_name.unique())
    selections = {p: frame.loc[frame.token_probability >= p].copy() for p in thresholds}
    group_sets = [set(part[GROUP].itertuples(index=False, name=None)) for part in selections.values()]
    common = set.intersection(*group_sets)
    coverage, correlations = [], []
    measures = [column for column in METRICS if column in frame]
    for threshold, selected in selections.items():
        for dataset, part in populations(selected, datasets):
            original = frame if dataset == "all" else frame.loc[frame.dataset_name == dataset]
            groups = part.groupby(GROUP, dropna=False)[[score] + measures].mean().reset_index()
            matched = groups.loc[[key in common for key in groups[GROUP].itertuples(index=False, name=None)]]
            coverage.append({
                "threshold": threshold, "dataset_name": dataset,
                "original_branches": len(original), "retained_branches": len(part),
                "retained_fraction": len(part) / len(original),
                "original_groups": len(original[GROUP].drop_duplicates()),
                "retained_groups": len(groups), "matched_groups": len(matched),
                "original_windows": len(original[WINDOW].drop_duplicates()),
                "retained_windows": len(part[WINDOW].drop_duplicates()),
                "retained_series": part.series_id.nunique(),
                "mean_fpa": part[score].mean(), "median_fpa": part[score].median(),
                "p90_fpa": part[score].quantile(.9), "max_fpa": part[score].max(),
                "median_entropy": part.normalized_token_entropy.median(),
            })
            for unit, work in [("branch", part), ("group_mean", groups), ("matched_group_mean", matched)]:
                for metric in measures:
                    n, pearson = correlation(work[metric], work[score])
                    _, spearman = correlation(work[metric], work[score], rank=True)
                    correlations.append({
                        "threshold": threshold, "dataset_name": dataset, "unit": unit,
                        "metric": metric, "n_pairs": n, "pearson": pearson, "spearman": spearman,
                    })
    return selections, pd.DataFrame(coverage), pd.DataFrame(correlations), common


def scenario_rates(path: Path, frame: pd.DataFrame, thresholds: list[float]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    scenarios = read_csv(path)
    if scenarios.duplicated(BRANCH + ["scenario_name"]).any():
        raise ValueError("Duplicate scenario decisions in source CSV.")
    joined = scenarios[BRANCH + ["scenario_name", "scenario_changed"]].merge(
        frame[BRANCH + ["token_probability"]], on=BRANCH, how="inner", validate="many_to_one",
    )
    if len(joined) != len(scenarios):
        raise ValueError("Scenario decisions do not match source alternative branches.")
    changed = joined.scenario_changed
    joined["scenario_changed"] = changed.astype(str).str.lower().isin(["true", "1"]).astype(float).where(changed.notna())
    rows = []
    for threshold in thresholds:
        selected = joined.loc[joined.token_probability >= threshold]
        for dataset, part in populations(selected, sorted(frame.dataset_name.unique())):
            for name, scenario in part.groupby("scenario_name"):
                rows.append({
                    "threshold": threshold, "dataset_name": dataset, "scenario_name": name,
                    "retained_branches": len(scenario), "changed": int(scenario.scenario_changed.sum()),
                    "defined_decisions": int(scenario.scenario_changed.notna().sum()),
                    "undefined_decisions": int(scenario.scenario_changed.isna().sum()),
                    "change_rate": scenario.scenario_changed.mean(),
                })
    return pd.DataFrame(rows)


def save_figures(output: Path, selections: dict, coverage: pd.DataFrame, correlations: pd.DataFrame, score: str):
    directory = output / "figures"
    directory.mkdir(exist_ok=True)
    thresholds = list(selections)
    labels = [threshold_label(p) for p in thresholds]
    datasets = sorted(next(iter(selections.values())).dataset_name.unique())

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for dataset in datasets:
        part = coverage.loc[coverage.dataset_name == dataset].set_index("threshold").loc[thresholds]
        color = COLORS.get(dataset)
        axes[0].plot(labels, 100 * part.retained_fraction, "o-", label=dataset, color=color)
        axes[1].plot(labels, 100 * part.retained_groups / part.original_groups, "o-", label=dataset, color=color)
    axes[0].set_ylabel("Retained alternatives (% of original alternatives)")
    axes[1].set_ylabel("Branch points with a retained alternative (%)")
    for ax in axes:
        ax.set_ylim(0, 105)
        ax.set_xlabel("Minimum stored probability of the forced token")
        ax.grid(alpha=.25)
    axes[0].legend()
    fig.suptitle("Probability filtering changes branch counts and context coverage")
    fig.tight_layout()
    fig.savefig(directory / "coverage_by_threshold.png", dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.7), sharey=True)
    for ax, unit in zip(axes, ["branch", "group_mean", "matched_group_mean"]):
        for dataset in ["all"] + datasets:
            part = correlations.loc[(correlations.unit == unit) & (correlations.metric == "normalized_token_entropy") & (correlations.dataset_name == dataset)]
            part = part.set_index("threshold").loc[thresholds]
            ax.plot(labels, part.spearman, "o-", label=dataset, color="black" if dataset == "all" else COLORS.get(dataset))
        ax.axhline(0, color="grey", lw=1)
        ax.set_ylim(-1, 1)
        ax.set_title(unit.replace("_", " "))
        ax.set_xlabel("Minimum forced-token probability")
        ax.grid(alpha=.25)
    axes[0].set_ylabel("Spearman rho: next-token entropy vs normalized FPA")
    axes[0].legend(fontsize=8)
    fig.suptitle("Internal uncertainty vs FPA: full coverage and matched branch points")
    fig.tight_layout()
    fig.savefig(directory / "entropy_correlations_by_threshold.png", dpi=170)
    plt.close(fig)

    for dataset in ["all"] + datasets:
        fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True, sharey=True)
        full = selections[thresholds[0]]
        full = full if dataset == "all" else full.loc[full.dataset_name == dataset]
        positive = full.loc[full[score] > 0, score]
        for ax, threshold in zip(axes.flat, thresholds):
            selected = selections[threshold]
            part = selected if dataset == "all" else selected.loc[selected.dataset_name == dataset]
            for name, group in part.groupby("dataset_name"):
                ax.scatter(group.normalized_token_entropy, group[score], s=15, alpha=.55, color=COLORS.get(name), label=name)
            ax.set_title(f"{threshold_label(threshold)} | n={len(part)} alternatives")
            ax.set_xlabel("Normalized entropy of P(next token | context + greedy prefix)")
            ax.set_ylabel("FPA score (context IQR normalization)")
            if len(positive) == len(full) and len(full):
                ax.set_yscale("log")
                ax.set_ylim(positive.min() * .8, positive.max() * 1.25)
            ax.grid(alpha=.2)
        axes[0, 0].legend(fontsize=8)
        fig.suptitle(f"{dataset}: same axes and unchanged branch scores across cutoffs")
        fig.tight_layout()
        destination = directory if dataset == "all" else directory / "by_dataset" / dataset
        destination.mkdir(parents=True, exist_ok=True)
        fig.savefig(destination / "entropy_vs_fpa_by_threshold.png", dpi=170)
        plt.close(fig)

    fig, axes = plt.subplots(1, len(datasets), figsize=(5 * len(datasets), 4.7), squeeze=False)
    for ax, dataset in zip(axes.flat, datasets):
        values = [part.loc[part.dataset_name == dataset, score].to_numpy() for part in selections.values()]
        ax.boxplot(values, tick_labels=labels, showfliers=True, flierprops={"markersize": 3})
        if all((values_ > 0).all() for values_ in values):
            ax.set_yscale("log")
        ax.set_title(dataset)
        ax.set_ylabel("FPA score (context IQR normalization; log axis)")
        ax.set_xlabel("Minimum forced-token probability")
        ax.grid(axis="y", alpha=.25)
    fig.tight_layout()
    fig.savefig(directory / "score_distributions_by_threshold.png", dpi=170)
    plt.close(fig)


def write_report(output: Path, coverage: pd.DataFrame, correlations: pd.DataFrame, source: Path, score: str):
    def value(number):
        return "NA" if pd.isna(number) else f"{number:.3f}"

    lines = [
        "# Filtrage des branches par probabilite", "",
        f"Source : `{source.as_posix()}`. Analyse offline : aucune inference.", "",
        f"Score unique pour toutes les comparaisons : `{score}`.", "",
        "Les branches base sont exclues. Les scores et les entropies sauvegardes ne sont pas recalcules.",
        "Le seuil est inclusif et porte sur P(token force | contexte + prefixe greedy), pas sur la probabilite de toute la trajectoire.", "",
        "## Couverture et scores", "",
        "| Seuil | Dataset | Alternatives | Points de branchement | Fenetres | Score median | Score maximal |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in coverage.itertuples():
        lines.append(f"| {threshold_label(row.threshold)} | {row.dataset_name} | {row.retained_branches}/{row.original_branches} | {row.retained_groups}/{row.original_groups} | {row.retained_windows}/{row.original_windows} | {value(row.median_fpa)} | {value(row.max_fpa)} |")
    lines += ["", "## Correlation entropie interne / FPA", "", "Spearman descriptif, sans p-value ni hypothese d'independance des branches.", "", "| Seuil | Dataset | Unite | n paires | Pearson | Spearman |", "|---|---|---|---:|---:|---:|"]
    selected = correlations.loc[correlations.metric == "normalized_token_entropy"]
    for row in selected.itertuples():
        lines.append(f"| {threshold_label(row.threshold)} | {row.dataset_name} | {row.unit} | {row.n_pairs} | {value(row.pearson)} | {value(row.spearman)} |")
    lines += [
        "", "## Interpretation et limites", "",
        "- `branch` : chaque alternative conservee compte une fois. L'entropie est repetee pour les alternatives d'un meme point.",
        "- `group_mean` : score moyen des alternatives retenues a chaque point de branchement ; une observation par contexte/prefixe/step.",
        "- `matched_group_mean` : memes points dans les quatre analyses (intersection), avec moyenne des alternatives admissibles a chaque seuil.",
        "- L'indice d'incertitude combine les rangs percentiles d'entropie, de marge inversee et de top1 inverse. Il est calcule une seule fois sur le summary complet, comme dans l'analyse originale, puis fige.",
        "- Un seuil eleve retire preferentiellement des zones certaines sans alternative assez probable. Les changements de correlation peuvent donc refleter la selection des contextes.",
        "- Les fenetres restent chevauchantes et les continuations partagent une base. Les correlations sont descriptives, pas des tests independants.",
        "- On filtre seulement les tokens deja testes. Les candidats hors top-k initial ne peuvent pas etre recuperes sans nouvelle inference.",
        "- Le filtre ne rend pas les taux de scenarios ponderes par la probabilite naturelle des tokens.",
        "- Les scenarios existants conservent leurs limites : plateaux pour les extrema et alertes parfois saturees.",
        "", "## Fichiers", "",
        "- `coverage_and_scores.csv` : effectifs, fenetres, points, distribution des scores.",
        "- `uncertainty_correlations.csv` : Pearson/Spearman, unites et effectifs, avec entropie et autres indicateurs.",
        "- `scenario_change_rates.csv` : taux filtres des scenarios, lorsque leurs sorties sont presentes.",
        "- `matched_branch_points.csv` : intersection des points de branchement dans les quatre seuils.",
        "- Un dossier par seuil contient `branches.csv` et `top_branches.csv` avec les identifiants d'origine.",
        "- `figures/coverage_by_threshold.png` : branches et points conserves par dataset.",
        "- `figures/entropy_correlations_by_threshold.png` : correlations par seuil, avec et sans appariement des points.",
        "- `figures/entropy_vs_fpa_by_threshold.png` et `figures/by_dataset/` : nuages de points a axes communs, score en echelle log.",
        "- `figures/score_distributions_by_threshold.png` : distributions par dataset/seuil.",
        "- `analysis_config.json` : protocole, colonne de score et empreintes des sources avant/apres analyse.",
    ]
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--score-column", default=DEFAULT_SCORE)
    parser.add_argument("--output-subdir", default="recherche/probability_thresholds")
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()
    source = args.run_dir / "chronos_scan_summary.csv"
    scenario_source = args.run_dir / "recherche/scenario_sensitivity/scenario_branch_decisions.csv"
    source_paths = [source] + ([scenario_source] if scenario_source.exists() else [])
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    output = args.run_dir / args.output_subdir
    if Path(args.output_subdir).is_absolute() or ".." in Path(args.output_subdir).parts:
        raise ValueError("Output must be a relative subdirectory of the source run.")
    if output.exists():
        raise FileExistsError(f"Analysis folder already exists: {output}. Choose another --output-subdir.")
    frame = prepare_branches(read_csv(source), args.score_column)
    if frame.empty:
        raise ValueError("No alternative branches in source summary.")
    if args.score_column not in {progressive for _, _, progressive in NORMALIZED_SCORE_SPECS}:
        raise ValueError("Select one of the saved normalized progressive score columns for the whole comparison.")
    thresholds = [0., .001, .01, .05]
    selections, coverage, correlations, common = compare_thresholds(frame, thresholds, args.score_column)
    scenarios = scenario_rates(scenario_source, frame, thresholds)
    output.mkdir(parents=True)
    coverage.to_csv(output / "coverage_and_scores.csv", index=False)
    correlations.to_csv(output / "uncertainty_correlations.csv", index=False)
    pd.DataFrame(sorted(common), columns=GROUP).to_csv(output / "matched_branch_points.csv", index=False)
    if not scenarios.empty:
        scenarios.to_csv(output / "scenario_change_rates.csv", index=False)
    columns = list(dict.fromkeys(BRANCH + ["token_rank", "token_probability", "token_surprisal", args.score_column] + [col for col in METRICS + ["mean_law_shift_over_context_iqr", "positive_law_amplification", "shape_break", "persistence_ratio", "base_mae_over_context_iqr", "topology_regime"] if col in frame]))
    for threshold, selected in selections.items():
        directory = output / threshold_name(threshold)
        directory.mkdir()
        selected[columns].to_csv(directory / "branches.csv", index=False)
        selected.nlargest(args.top_n, args.score_column)[columns].to_csv(directory / "top_branches.csv", index=False)
    save_figures(output, selections, coverage, correlations, args.score_column)
    write_report(output, coverage, correlations, source, args.score_column)
    after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    if hashes != after:
        raise RuntimeError("Source CSV changed during analysis.")
    (output / "analysis_config.json").write_text(json.dumps({
        "analysis_version": ANALYSIS_VERSION,
        "source_run": str(args.run_dir), "score_column": args.score_column,
        "thresholds": thresholds, "filter": "token_probability >= threshold; alternative branches only",
        "fixed_uncertainty_index": True, "matched_branch_groups": len(common),
        "source_sha256_before": hashes, "source_sha256_after": after,
        "source_files_unchanged": True, "new_inference": False,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Saved probability-threshold analysis to: {output}")
    print(coverage.loc[coverage.dataset_name == "all", ["threshold", "retained_branches", "retained_groups", "retained_windows", "median_fpa", "max_fpa"]].to_string(index=False))


if __name__ == "__main__":
    run()
