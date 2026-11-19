from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError

from create_chronos_progress_ppt import (
    bullet_list,
    content_types,
    picture,
    presentation_rels,
    presentation_xml,
    shape,
    slide_rels,
    slide_xml,
    static_parts,
    table,
    text_box,
    title,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT / "result" / "topology_temporal_single_20260724_175602"
OUT = ROOT / "presentations" / "chronos_fpa_findings_topology_temporal.pptx"


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except EmptyDataError:
        return pd.DataFrame()


def _fmt(value: float, digits: int = 3) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def _rank_corr(x: pd.Series, y: pd.Series) -> float:
    frame = pd.DataFrame({"x": x, "y": y}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 3:
        return float("nan")
    return float(frame["x"].rank().corr(frame["y"].rank()))


def collect_stats(run_dir: Path) -> dict:
    summary = _read_csv(run_dir / "chronos_scan_summary.csv")
    steps = _read_csv(run_dir / "chronos_scan_steps.csv")
    errors = _read_csv(run_dir / "chronos_scan_errors.csv")
    warnings = _read_csv(run_dir / "chronos_base_quality_warnings.csv")
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))

    score = "context_iqr_scaled_progressive_token_bin_forking_score"
    raw_score = "progressive_token_bin_forking_score"
    alt = summary[~summary["is_base_token"]].copy()
    top = alt.sort_values(score, ascending=False).iloc[0]

    by_dataset = (
        alt.groupby("dataset_name")
        .agg(
            rows=(score, "size"),
            mean_score=(score, "mean"),
            median_score=(score, "median"),
            max_score=(score, "max"),
            median_base_err=("base_mae_over_window_scale", "median"),
        )
        .sort_values("max_score", ascending=False)
        .reset_index()
    )

    low_entropy_high_margin = alt[
        (alt["normalized_token_entropy"] <= alt["normalized_token_entropy"].quantile(0.25))
        & (alt["top1_top2_margin"] >= alt["top1_top2_margin"].quantile(0.75))
    ]
    high_entropy_low_margin = alt[
        (alt["normalized_token_entropy"] >= alt["normalized_token_entropy"].quantile(0.75))
        & (alt["top1_top2_margin"] <= alt["top1_top2_margin"].quantile(0.25))
    ]
    improbable = alt[alt["token_probability"] <= alt["token_probability"].quantile(0.10)]
    probable = alt[alt["token_probability"] >= alt["token_probability"].quantile(0.90)]

    return {
        "run_dir": run_dir,
        "config": config,
        "summary": summary,
        "steps": steps,
        "errors": errors,
        "warnings": warnings,
        "score": score,
        "raw_score": raw_score,
        "alt": alt,
        "top": top,
        "by_dataset": by_dataset,
        "base_median": float(summary["base_mae_over_window_scale"].median()),
        "base_p90": float(summary["base_mae_over_window_scale"].quantile(0.90)),
        "base_max": float(summary["base_mae_over_window_scale"].max()),
        "raw_means": alt.groupby("dataset_name")[raw_score].mean().sort_values(ascending=False),
        "norm_means": alt.groupby("dataset_name")[score].mean().sort_values(ascending=False),
        "corr_probability": _rank_corr(alt[score], alt["token_probability"]),
        "corr_surprisal": _rank_corr(alt[score], alt["token_surprisal"]),
        "corr_entropy": _rank_corr(alt[score], alt["normalized_token_entropy"]),
        "corr_margin": _rank_corr(alt[score], alt["top1_top2_margin"]),
        "corr_persistence": _rank_corr(alt[score], alt["persistence_ratio"]),
        "corr_amplification": _rank_corr(alt[score], alt["positive_law_amplification"]),
        "n_flat_future_rows": int((summary["gt_range"].abs() < 1e-12).sum()),
        "low_entropy_high_margin": low_entropy_high_margin,
        "high_entropy_low_margin": high_entropy_low_margin,
        "improbable": improbable,
        "probable": probable,
    }


def mini_table(rows: list[list[str]], x0: float, y0: float, widths: list[float]) -> str:
    out = []
    for r, row in enumerate(rows):
        x = x0
        for c, value in enumerate(row):
            fill = "E9EEF6" if r == 0 else "FFFFFF"
            bold = r == 0
            out.append(
                shape(
                    700 + r * 20 + c,
                    f"Table {r}-{c}",
                    x,
                    y0 + r * 0.43,
                    widths[c],
                    0.39,
                    value,
                    fill,
                    "CBD6E2",
                    820,
                    "18212F",
                    bold,
                    False,
                )
            )
            x += widths[c]
    return "".join(out)


def example_card(shape_id: int, x: float, y: float, title_text: str, row: pd.Series, score_col: str) -> str:
    lines = [
        title_text,
        f"{row['dataset_name']} / {row['series_id']} / w{int(row['window_id'])}",
        f"step {int(row['branch_step'])}, rank {int(row['token_rank'])}, p={_fmt(float(row['token_probability']), 4)}",
        f"entropy={_fmt(float(row['normalized_token_entropy']))}, margin={_fmt(float(row['top1_top2_margin']))}",
        f"score={_fmt(float(row[score_col]))}, persistence={_fmt(float(row['persistence_ratio']))}",
    ]
    return shape(
        shape_id,
        title_text,
        x,
        y,
        5.65,
        1.45,
        "\n".join(lines),
        "FFFFFF",
        "CBD6E2",
        920,
        "18212F",
        True,
        True,
    )


def build_slides(stats: dict) -> tuple[list[str], list[list[Path]]]:
    run_dir = stats["run_dir"]
    fig_dir = run_dir / "figures"
    score = stats["score"]
    top = stats["top"]
    config = stats["config"]

    images = {
        "top_scores": fig_dir / "chronos_top_branch_scores.png",
        "raw_norm": fig_dir / "chronos_raw_vs_normalized_score.png",
        "dataset_box": fig_dir / "chronos_score_by_dataset_boxplot.png",
        "prob": fig_dir / "chronos_score_vs_token_probability.png",
        "entropy": fig_dir / "chronos_score_vs_token_entropy.png",
        "temporal": fig_dir / "chronos_temporal_shift_profile.png",
        "components": fig_dir / "chronos_score_component_contributions.png",
    }

    slides: list[str] = []
    slide_images: list[list[Path]] = []

    slides.append(
        slide_xml(
            title("Chronos FPA - Findings", "Run topology_temporal_single_20260724_175602")
            + shape(
                20,
                "Message",
                0.85,
                1.45,
                11.55,
                1.45,
                "Message principal\nLes gros shifts ne sont pas simplement expliques par l'improbabilite du token.",
                "EAF3FF",
                "B7CDFB",
                1800,
                "0D1B2A",
                True,
            )
            + bullet_list(
                30,
                1.05,
                3.35,
                11.0,
                [
                    "La normalisation reduit fortement le biais d'echelle ERCOT.",
                    "Deux regimes apparaissent : zone incertaine naturelle vs zone confiante fragilisee par un token improbable.",
                    "Les scores sont surtout portes par la persistance/amplification temporelle du shift.",
                ],
                1400,
            )
        )
    )
    slide_images.append([])

    slides.append(
        slide_xml(
            title("Protocole Du Run", "Ce qui a ete teste")
            + mini_table(
                [
                    ["Parametre", "Valeur"],
                    ["Mode", "single-token branching"],
                    ["Datasets", "5 max, 68 fenetres effectives"],
                    ["Branch steps", ",".join(str(x) for x in config["branch_steps"])],
                    ["Top-k", str(config["args"]["top_k"])],
                    ["Samples", str(config["args"]["num_samples"])],
                    ["Score ranking", config["rank_score_column"]],
                ],
                0.85,
                1.35,
                [3.3, 8.2],
            )
            + shape(
                100,
                "Sanity",
                0.95,
                4.8,
                11.2,
                0.95,
                f"Sanity checks : {len(stats['summary'])} lignes summary, {len(stats['steps'])} lignes steps, "
                f"{len(stats['errors'])} erreurs, {len(stats['warnings'])} warnings base.",
                "ECFDF5",
                "9AD8C2",
                1250,
                "0D1B2A",
                True,
            )
        )
    )
    slide_images.append([])

    slides.append(
        slide_xml(
            title("Qualite De La Base", "Chronos n'est pas catastrophique sur ce run")
            + shape(
                120,
                "Base",
                0.85,
                1.25,
                3.55,
                1.25,
                f"median\n{_fmt(stats['base_median'])}",
                "FFFFFF",
                "CBD6E2",
                1700,
                "18212F",
                True,
            )
            + shape(
                121,
                "Base p90",
                4.85,
                1.25,
                3.55,
                1.25,
                f"p90\n{_fmt(stats['base_p90'])}",
                "FFFFFF",
                "CBD6E2",
                1700,
                "18212F",
                True,
            )
            + shape(
                122,
                "Base max",
                8.85,
                1.25,
                3.55,
                1.25,
                f"max\n{_fmt(stats['base_max'])}",
                "FFFFFF",
                "CBD6E2",
                1700,
                "18212F",
                True,
            )
            + bullet_list(
                130,
                1.05,
                3.25,
                11.0,
                [
                    "Aucun warning base forecast avec le seuil actuel base_mae/window_scale >= 1.",
                    "Les gros shifts sont donc plus interpretables que dans les anciens runs ou Chronos etait parfois deja tres loin du GT.",
                    "Biais restant : certains futurs Dominick sont plats; la prediction base peut etre parfaite sur un futur trivial.",
                ],
                1320,
            )
        )
    )
    slide_images.append([])

    top_text = (
        f"Top shift\n{top['dataset_name']} / {top['series_id']} / w{int(top['window_id'])}\n"
        f"branch_step={int(top['branch_step'])}, token_rank={int(top['token_rank'])}\n"
        f"score={_fmt(float(top[score]))}, p={_fmt(float(top['token_probability']), 4)}"
    )
    slides.append(
        slide_xml(
            title("Exemple Principal", "Le plus gros shift du run")
            + shape(150, "Top example", 0.8, 1.25, 4.25, 2.05, top_text, "FFF4E6", "F3C98B", 1200, "0D1B2A", True)
            + picture(151, "rId2", 5.35, 1.05, 7.0, 4.4, "Top branch scores")
            + bullet_list(
                160,
                0.95,
                4.25,
                4.25,
                [
                    "Token pas ultra-improbable.",
                    "Entropie locale haute.",
                    "Marge top1/top2 faible.",
                    "Cas typique : incertitude locale -> divergence.",
                ],
                1050,
            )
        )
    )
    slide_images.append([images["top_scores"]])

    rows = [["Dataset", "raw moyen", "score norm. moyen"]]
    for ds in sorted(stats["norm_means"].index):
        rows.append(
            [
                str(ds),
                _fmt(float(stats["raw_means"].get(ds, np.nan)), 2),
                _fmt(float(stats["norm_means"].get(ds, np.nan)), 3),
            ]
        )
    slides.append(
        slide_xml(
            title("Normalisation", "ERCOT domine le brut, moins le score normalise")
            + mini_table(rows, 0.75, 1.25, [2.6, 2.2, 2.6])
            + picture(180, "rId2", 7.85, 1.1, 4.8, 3.25, "Raw vs normalized")
            + bullet_list(
                190,
                0.9,
                4.55,
                11.2,
                [
                    "Le score brut reste utile intra-dataset, mais pas pour comparer ERCOT et exchange_rate.",
                    "Le score window_scaled normalise les composantes avec unites par window_scale.",
                    "Le signal ERCOT reste present, mais m4_daily et Dominick ressortent aussi.",
                ],
                1170,
            )
        )
    )
    slide_images.append([images["raw_norm"]])

    conf = stats["low_entropy_high_margin"].sort_values(score, ascending=False).iloc[0]
    uncer = stats["high_entropy_low_margin"].sort_values(score, ascending=False).iloc[0]
    slides.append(
        slide_xml(
            title("Deux Regimes De Shift", "Hypothese centrale a tester")
            + example_card(210, 0.75, 1.25, "Zone confiante + token improbable", conf, score)
            + example_card(211, 6.85, 1.25, "Zone incertaine + token plausible", uncer, score)
            + picture(212, "rId2", 0.85, 3.25, 5.55, 2.45, "Probability")
            + picture(213, "rId3", 6.95, 3.25, 5.55, 2.45, "Entropy")
        )
    )
    slide_images.append([images["prob"], images["entropy"]])

    slides.append(
        slide_xml(
            title("Temporalite Du Shift", "Le score actuel favorise les divergences persistantes")
            + picture(230, "rId2", 0.8, 1.1, 6.0, 3.65, "Temporal profile")
            + picture(231, "rId3", 7.05, 1.1, 5.45, 3.65, "Score components")
            + bullet_list(
                240,
                0.95,
                5.05,
                11.0,
                [
                    f"Correlation rank score/persistence = {_fmt(stats['corr_persistence'])}.",
                    f"Correlation rank score/amplification = {_fmt(stats['corr_amplification'])}.",
                    "Prochaine etape : separer score instantane, score persistant et score progressif.",
                ],
                1150,
            )
        )
    )
    slide_images.append([images["temporal"], images["components"]])

    slides.append(
        slide_xml(
            title("Biais Et Incoherences A Surveiller")
            + bullet_list(
                260,
                0.95,
                1.35,
                11.2,
                [
                    "Les lignes is_base_token=True ont un score zero : les filtrer pour analyser les vrais shifts.",
                    f"{stats['n_flat_future_rows']} lignes ont un futur plat; la normalisation tient, mais l'interpretation change.",
                    "Dominick est court et souvent limite a window=0 avec adaptive-context.",
                    "num_samples=10 donne des quantiles encore bruites; confirmer les top windows avec 50 ou 100 samples.",
                    "Run single only : les conclusions ne couvrent pas encore les bundles.",
                    "Le run date d'avant checkpoint.json, mais les CSV finaux sont complets.",
                ],
                1330,
            )
            + shape(
                280,
                "Audit",
                1.0,
                5.55,
                11.1,
                0.68,
                "Checks math : pas de doublons, entropie dans [0,1], top1 >= top2, score recompute diff ~ 3e-16.",
                "ECFDF5",
                "9AD8C2",
                1150,
                "0D1B2A",
                True,
            )
        )
    )
    slide_images.append([])

    slides.append(
        slide_xml(
            title("A Faire Ensuite", "Plan de travail recherche")
            + bullet_list(
                300,
                0.95,
                1.25,
                11.2,
                [
                    "Rerun les top windows avec num_samples=50/100 pour verifier la stabilite Monte Carlo.",
                    "Formaliser une typologie topologique : uncertain/plausible vs confident/improbable.",
                    "Creer trois scores separes : instant_forking, persistent_forking, progressive_forking.",
                    "Faire des rankings par dataset puis comparer au ranking global normalise.",
                    "Ajouter bundle sur un sous-ensemble top-ranked pour tester les deviations multi-step.",
                    "Relier FPA score a l'erreur future et a des changements structurels visibles dans la serie.",
                ],
                1270,
            )
            + shape(
                330,
                "Research",
                1.0,
                5.55,
                11.1,
                0.72,
                "Question centrale : les bifurcations Chronos revelent-elles une incertitude structurelle utile ?",
                "EAF3FF",
                "B7CDFB",
                1250,
                "0D1B2A",
                True,
            )
        )
    )
    slide_images.append([])

    return slides, slide_images


def create_pptx(run_dir: Path = DEFAULT_RUN, out: Path = OUT) -> Path:
    stats = collect_stats(run_dir)
    slides, slide_images = build_slides(stats)

    media_entries: dict[Path, str] = {}
    media_counter = 1
    for paths in slide_images:
        for path in paths:
            if path.exists() and path not in media_entries:
                media_entries[path] = f"findings_image{media_counter}.png"
                media_counter += 1

    out.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types(len(slides), list(media_entries.values())))
        z.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        z.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(slides)))
        for path, xml in static_parts(now, len(slides)).items():
            z.writestr(path, xml)
        for img_path, media_name in media_entries.items():
            z.write(img_path, f"ppt/media/{media_name}")
        for i, slide in enumerate(slides, start=1):
            z.writestr(f"ppt/slides/slide{i}.xml", slide)
            targets = [media_entries[img] for img in slide_images[i - 1] if img in media_entries]
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", slide_rels(targets))
    return out


if __name__ == "__main__":
    print(create_pptx())




