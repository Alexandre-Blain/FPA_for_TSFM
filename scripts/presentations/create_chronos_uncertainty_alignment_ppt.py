from __future__ import annotations

import csv
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRESENTATION_CODE = ROOT / "scripts" / "presentations"
if str(PRESENTATION_CODE) not in sys.path:
    sys.path.insert(0, str(PRESENTATION_CODE))

from create_chronos_progress_ppt import (  # noqa: E402
    arrow,
    bullet_list,
    content_types,
    picture,
    presentation_rels,
    presentation_xml,
    shape,
    slide_rels,
    slide_xml,
    static_parts,
    text_box,
    title,
)


OUT = ROOT / "presentations" / "chronos_uncertainty_vs_fpa.pptx"
RUN = ROOT / "result" / "faster_global_scan_no_refinement_20260727_173315"
ALIGN = RUN / "recherche" / "model_uncertainty_alignment"
FIG = ALIGN / "figures"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_summary() -> dict:
    path = ALIGN / "model_uncertainty_alignment_summary.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def metric_corr(metric: str) -> float:
    rows = read_csv(ALIGN / "model_uncertainty_fpa_correlations.csv")
    for row in rows:
        if (
            row.get("group_name") == "global"
            and row.get("fpa_metric") == "selected_fpa_score"
            and row.get("model_metric") == metric
        ):
            return float(row.get("spearman_corr", "nan"))
    return float("nan")


def quadrant_rows() -> list[dict[str, str]]:
    rows = read_csv(ALIGN / "model_uncertainty_fpa_quadrant_summary.csv")
    order = {
        "high_model_uncertainty__high_fpa_shift": 0,
        "lower_model_uncertainty__high_fpa_shift": 1,
        "high_model_uncertainty__lower_fpa_shift": 2,
        "lower_model_uncertainty__lower_fpa_shift": 3,
    }
    return sorted(rows, key=lambda row: order.get(row.get("uncertainty_fpa_quadrant", ""), 99))


def example_rows() -> list[dict[str, str]]:
    rows = read_csv(ALIGN / "model_uncertainty_interesting_branches.csv")
    return [row for row in rows if row.get("case_type") == "low_model_uncertainty_high_fpa"][:3]


def small_caption(text: str) -> str:
    return text_box(910, 0.68, 6.08, 12.0, 0.25, [text], 850, "52606D")


def corr_table(x: float, y: float, w: float, rows: list[tuple[str, str, str]]) -> str:
    out = []
    widths = [4.8, 1.25, 4.5]
    headers = ["Metric Chronos", "Corr.", "Lecture"]
    cur = x
    for i, (h, width) in enumerate(zip(headers, widths)):
        out.append(shape(1000 + i, h, cur, y, width, 0.42, h, "E9EEF6", "CBD6E2", 1050, "18212F", True, False))
        cur += width
    for r, vals in enumerate(rows):
        cur = x
        yy = y + 0.46 + r * 0.54
        for c, (val, width) in enumerate(zip(vals, widths)):
            out.append(shape(1020 + r * 10 + c, val, cur, yy, width, 0.48, val, "FFFFFF", "E2E8F0", 930, "18212F", False, False))
            cur += width
    return "".join(out)


def quadrant_table(x: float, y: float, rows: list[dict[str, str]]) -> str:
    names = {
        "high_model_uncertainty__high_fpa_shift": "Modele incertain + fort FPA",
        "lower_model_uncertainty__high_fpa_shift": "Modele plutot confiant + fort FPA",
        "high_model_uncertainty__lower_fpa_shift": "Modele incertain + faible FPA",
        "lower_model_uncertainty__lower_fpa_shift": "Modele plutot confiant + faible FPA",
    }
    out = []
    widths = [4.8, 1.0, 1.35, 1.35]
    headers = ["Quadrant", "N", "Median FPA", "Max FPA"]
    cur = x
    for i, (h, width) in enumerate(zip(headers, widths)):
        out.append(shape(1300 + i, h, cur, y, width, 0.42, h, "E9EEF6", "CBD6E2", 920, "18212F", True, False))
        cur += width
    for r, row in enumerate(rows):
        vals = [
            names.get(row.get("uncertainty_fpa_quadrant", ""), row.get("uncertainty_fpa_quadrant", "")),
            row.get("rows", ""),
            fmt(float(row.get("median_fpa_score", "nan")), 3),
            fmt(float(row.get("max_fpa_score", "nan")), 3),
        ]
        fill = "FCEEEF" if r == 1 else "FFFFFF"
        cur = x
        yy = y + 0.46 + r * 0.54
        for c, (val, width) in enumerate(zip(vals, widths)):
            out.append(shape(1320 + r * 10 + c, val, cur, yy, width, 0.48, val, fill, "E2E8F0", 870, "18212F", c == 0 and r == 1, False))
            cur += width
    return "".join(out)


def examples_table(x: float, y: float, rows: list[dict[str, str]]) -> str:
    out = []
    widths = [2.7, 1.0, 1.0, 1.0, 1.05, 1.05, 2.1]
    headers = ["Exemple", "step", "rank", "FPA", "entropy", "margin", "regime"]
    cur = x
    for i, (h, width) in enumerate(zip(headers, widths)):
        out.append(shape(1500 + i, h, cur, y, width, 0.42, h, "E9EEF6", "CBD6E2", 820, "18212F", True, False))
        cur += width
    for r, row in enumerate(rows):
        label = f"{row.get('dataset_name')}/{row.get('series_id')}"
        vals = [
            label,
            row.get("branch_step", ""),
            row.get("token_rank", ""),
            fmt(float(row.get("selected_fpa_score", "nan")), 3),
            fmt(float(row.get("normalized_token_entropy", "nan")), 3),
            fmt(float(row.get("top1_top2_margin", "nan")), 3),
            row.get("topology_regime", ""),
        ]
        cur = x
        yy = y + 0.46 + r * 0.55
        for c, (val, width) in enumerate(zip(vals, widths)):
            out.append(shape(1520 + r * 10 + c, val, cur, yy, width, 0.49, val, "FFFFFF", "E2E8F0", 760, "18212F", c in {0, 3}, False))
            cur += width
    return "".join(out)


def build_slides() -> tuple[list[str], list[list[Path]]]:
    summary = read_summary()
    rows_alt = summary.get("rows_alternative", 1008)
    score_col = summary.get("score_column", "window_scaled_progressive_token_bin_forking_score")
    corr_unc = metric_corr("model_distribution_uncertainty_index")
    corr_entropy = metric_corr("normalized_token_entropy")
    corr_margin = metric_corr("inverse_top1_top2_margin")
    corr_surprisal = metric_corr("token_surprisal")
    corr_rank = metric_corr("token_rank")

    slides: list[str] = []
    images: list[list[Path]] = []

    slides.append(
        slide_xml(
            title("Chronos FPA", "Incertitude modele vs sensibilite structurelle")
            + shape(
                20,
                "Question",
                0.85,
                1.45,
                11.6,
                1.35,
                "Question simple\nEst-ce que la FPA mesure juste l'incertitude deja visible dans les logits Chronos ?",
                "EAF3FF",
                "B7CDFB",
                1850,
                "0D1B2A",
                True,
            )
            + bullet_list(
                30,
                1.05,
                3.25,
                11.2,
                [
                    "Run principal : faster_global_scan_no_refinement_20260727_173315.",
                    f"Branches alternatives analysees : {rows_alt}.",
                    "Analyse offline : aucun nouvel appel modele, uniquement les CSV existants.",
                ],
                1400,
            )
            + shape(
                45,
                "Takeaway",
                1.0,
                5.35,
                11.2,
                0.75,
                "Takeaway : faible correlation ne valide pas la FPA, mais montre qu'elle n'est pas redondante avec l'entropie/marge locale.",
                "FCEEEF",
                "F3B6C2",
                1280,
                "0D1B2A",
                True,
            )
        )
    )
    images.append([])

    slides.append(
        slide_xml(
            title("Deux notions differentes", "A ne pas melanger")
            + shape(
                60,
                "Model",
                0.75,
                1.25,
                5.55,
                1.45,
                "Incertitude interne Chronos\nDistribution locale des logits au branch_step",
                "EAF3FF",
                "B7CDFB",
                1450,
                "0D1B2A",
                True,
            )
            + shape(
                61,
                "FPA",
                6.95,
                1.25,
                5.55,
                1.45,
                "Sensibilite FPA\nEffet futur d'un token force sur toute la trajectoire",
                "FFF4E6",
                "F3C98B",
                1450,
                "0D1B2A",
                True,
            )
            + shape(62, "m1", 1.0, 3.05, 4.95, 1.35, "Mesures\nentropy, top1-top2 margin,\ntop1 probability", "FFFFFF", "DDE6F0", 1250, "18212F", True)
            + shape(63, "m2", 7.2, 3.05, 4.95, 1.35, "Mesures\nforking score, persistence,\nprogressive score", "FFFFFF", "DDE6F0", 1250, "18212F", True)
            + arrow(64, 5.95, 3.75, 7.15, 3.75)
            + shape(
                65,
                "Core",
                1.0,
                5.05,
                11.2,
                0.85,
                "Si ces deux objets etaient identiques, on attendrait une forte correlation positive. Ce n'est pas ce qu'on observe.",
                "ECFDF5",
                "BFE8D4",
                1350,
                "0D1B2A",
                True,
            )
        )
    )
    images.append([])

    slides.append(
        slide_xml(
            title("Protocole", "Correlation branche/token")
            + shape(
                80,
                "Pipeline",
                0.8,
                1.25,
                11.7,
                0.75,
                "Pour chaque branche alternative : metrics Chronos au branch_step  ->  score FPA sur l'horizon futur",
                "FFFFFF",
                "DDE6F0",
                1450,
                "18212F",
                True,
            )
            + corr_table(
                0.8,
                2.35,
                10.0,
                [
                    ("Entropy logits", "haut = incertain", "distribution plus plate"),
                    ("Marge top1-top2", "bas = incertain", "competition locale"),
                    ("Token probability/rank", "plausibilite", "token force lui-meme"),
                    ("FPA score", "shift futur", "deformation trajectoire"),
                ],
            )
            + shape(
                95,
                "Score",
                0.9,
                5.25,
                11.3,
                0.65,
                f"Score principal utilise ici : {score_col}",
                "EAF3FF",
                "B7CDFB",
                1050,
                "0D1B2A",
                True,
            )
        )
    )
    images.append([])

    slides.append(
        slide_xml(
            title("Point echelle", "Pourquoi les correlations sont comparables")
            + shape(
                98,
                "Scale OK",
                0.8,
                1.25,
                11.7,
                1.0,
                "Pas de probleme d'unites direct : les correlations principales sont des Spearman.\nElles comparent les rangs, donc elles sont robustes aux changements monotones d'echelle.",
                "ECFDF5",
                "BFE8D4",
                1450,
                "0D1B2A",
                True,
            )
            + bullet_list(
                100,
                1.05,
                2.75,
                11.2,
                [
                    "Le score FPA utilise ici est deja normalise par window_scale.",
                    "Spearman regarde si deux variables montent ensemble, pas leur unite physique brute.",
                    "Le vrai risque restant est un biais de composition : un dataset peut dominer la correlation globale.",
                    "C'est pour cela qu'on ajoute aussi une figure par dataset.",
                ],
                1350,
            )
            + shape(
                112,
                "Caution",
                0.95,
                5.35,
                11.3,
                0.65,
                "Nuance : ce run reste legacy window_scale. Pour une conclusion finale, refaire avec context_iqr et regarder global + par dataset.",
                "FFF4E6",
                "F3C98B",
                1160,
                "0D1B2A",
                True,
            )
        )
    )
    images.append([])

    slides.append(
        slide_xml(
            title("Resultat clef", "L'incertitude locale Chronos explique peu le score FPA")
            + corr_table(
                0.75,
                1.25,
                10.0,
                [
                    ("model_distribution_uncertainty_index", fmt(corr_unc), "tres faible"),
                    ("normalized_token_entropy", fmt(corr_entropy), "tres faible"),
                    ("inverse_top1_top2_margin", fmt(corr_margin), "tres faible"),
                    ("token_surprisal", fmt(corr_surprisal), "plutot inverse"),
                    ("token_rank", fmt(corr_rank), "plutot inverse"),
                ],
            )
            + picture(120, "rId2", 7.15, 1.28, 5.15, 3.45, "Correlation heatmap")
            + shape(
                122,
                "Heatmap read",
                7.2,
                4.78,
                5.05,
                0.55,
                "Figure : si Chronos uncertainty et FPA etaient la meme chose, on verrait des cases rouges fortes. Ici les valeurs restent proches de 0.",
                "FFFFFF",
                "DDE6F0",
                850,
                "18212F",
                False,
            )
            + shape(
                121,
                "Interpretation",
                0.95,
                5.25,
                11.2,
                0.8,
                "Interpretation correcte : faible correlation = la FPA n'est pas juste une reformulation de l'entropie/marge. Ce n'est pas encore une preuve qu'elle est une bonne incertitude.",
                "FCEEEF",
                "F3B6C2",
                1190,
                "0D1B2A",
                True,
            )
        )
    )
    images.append([FIG / "model_uncertainty_fpa_correlation_heatmap.png"])

    slides.append(
        slide_xml(
            title("Lecture visuelle", "Pas de relation simple")
            + picture(140, "rId2", 0.65, 1.2, 5.8, 3.65, "Score vs uncertainty")
            + picture(141, "rId3", 6.85, 1.2, 5.65, 3.65, "By dataset")
            + shape(
                142,
                "Left read",
                0.75,
                5.05,
                5.6,
                0.75,
                "Scatter gauche : les points sont disperses. A incertitude Chronos comparable, le score FPA peut etre faible ou fort.",
                "FFFFFF",
                "DDE6F0",
                900,
                "18212F",
                False,
            )
            + shape(
                143,
                "Right read",
                6.95,
                5.05,
                5.4,
                0.75,
                "Barplot droite : la correlation change selon le dataset. La lecture globale doit donc toujours etre controlee par dataset.",
                "FFFFFF",
                "DDE6F0",
                900,
                "18212F",
                False,
            )
        )
    )
    images.append([FIG / "score_vs_model_distribution_uncertainty.png", FIG / "model_uncertainty_correlations_by_dataset.png"])

    slides.append(
        slide_xml(
            title("Quadrants", "Le cas le plus interessant est en bas a droite")
            + quadrant_table(0.75, 1.25, quadrant_rows())
            + shape(
                170,
                "Focus",
                0.85,
                4.1,
                11.3,
                0.95,
                "Cas recherche fort : modele plutot confiant + fort shift FPA.\nChronos ne signale pas fortement l'incertitude locale, mais le branching deforme durablement le futur.",
                "FFF4E6",
                "F3C98B",
                1300,
                "0D1B2A",
                True,
            )
            + shape(
                171,
                "Not proof",
                0.85,
                5.35,
                11.3,
                0.65,
                "Ce quadrant suggere une perspective differente, pas encore une validation finale.",
                "FCEEEF",
                "F3B6C2",
                1250,
                "0D1B2A",
                True,
            )
        )
    )
    images.append([])

    slides.append(
        slide_xml(
            title("Exemples concrets", "Faible incertitude modele + fort shift FPA")
            + examples_table(0.55, 1.25, example_rows())
            + shape(
                200,
                "Read",
                0.75,
                3.55,
                11.7,
                0.95,
                "Exemple exchange_rate/currency_5 : entropy = 0.005, margin = 0.987, mais FPA = 0.406.\nC'est exactement le type de cas ou la FPA peut montrer une fragilite cachee.",
                "EAF3FF",
                "B7CDFB",
                1270,
                "0D1B2A",
                True,
            )
            + picture(201, "rId2", 1.0, 4.75, 5.55, 1.35, "Token probability scatter")
            + picture(202, "rId3", 6.85, 4.75, 5.55, 1.35, "Token rank scatter")
            + shape(
                203,
                "Figure read",
                1.0,
                6.15,
                11.4,
                0.38,
                "Figures : les plus gros shifts ne viennent pas uniquement des tokens improbables. Les alternatives plausibles/top-rank restent centrales.",
                "FFFFFF",
                "DDE6F0",
                850,
                "18212F",
                False,
            )
        )
    )
    images.append([FIG / "score_vs_token_probability.png", FIG / "score_vs_token_rank.png"])

    slides.append(
        slide_xml(
            title("Conclusion et suite", "Message a retenir")
            + shape(
                220,
                "Conclusion",
                0.8,
                1.25,
                11.7,
                1.0,
                "Conclusion provisoire\nLa FPA semble apporter un signal non redondant avec l'incertitude locale simple de Chronos.",
                "ECFDF5",
                "BFE8D4",
                1550,
                "0D1B2A",
                True,
            )
            + bullet_list(
                230,
                1.05,
                2.8,
                11.1,
                [
                    "Ce que ca soutient : FPA different de entropy/margin logits.",
                    "Ce que ca ne prouve pas encore : FPA = bonne incertitude decisionnelle.",
                    "Prochaine etape : scenarios decisionnels generiques pour voir si les branches changent une decision.",
                    "Run a refaire proprement : normalisation context_iqr + CSV sans append de schema incompatible.",
                ],
                1400,
            )
        )
    )
    images.append([])

    return slides, images


def create_pptx() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    slides, slide_images = build_slides()

    media_entries: dict[Path, str] = {}
    counter = 1
    for group in slide_images:
        for img in group:
            if img.exists() and img not in media_entries:
                media_entries[img] = f"image{counter}.png"
                counter += 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types(len(slides), list(media_entries.values())))
        z.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        z.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(slides)))
        for path, xml in static_parts(now, len(slides)).items():
            z.writestr(path, xml)
        for img, name in media_entries.items():
            z.write(img, f"ppt/media/{name}")
        for i, slide in enumerate(slides, start=1):
            z.writestr(f"ppt/slides/slide{i}.xml", slide)
            targets = [media_entries[img] for img in slide_images[i - 1] if img in media_entries]
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", slide_rels(targets))
    print(OUT)


if __name__ == "__main__":
    create_pptx()
