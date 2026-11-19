from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError

from create_chronos_progress_ppt import (
    arrow,
    bullet_list,
    color,
    content_types,
    emu,
    picture,
    presentation_rels,
    presentation_xml,
    shape,
    slide_rels,
    slide_xml,
    static_parts,
    text_box,
    title,
    xml_text,
)


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "presentations" / "chronos_fpa_project_intro_v2.pptx"
ASSET_DIR = ROOT / "presentations" / "assets" / "chronos_intro"

RUNS = [
    ROOT / "result" / "topology_temporal_single_20260724_175602",
    ROOT / "result" / "faster_global_scan_no_refinement_20260727_173315",
    ROOT / "result" / "refinement_faster_global_20260728_125930",
]


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, EmptyDataError):
        return pd.DataFrame()


def _fig_setup():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": 13,
            "axes.titlesize": 15,
            "axes.labelsize": 13,
            "legend.fontsize": 11,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    return plt


def save_law_shift_figure(path: Path) -> None:
    plt = _fig_setup()
    h = np.arange(0, 24)
    base_q50 = 10 + 0.10 * h + 0.45 * np.sin(h / 4.5)
    base_spread = 0.8 + 0.08 * np.sin(h / 3)
    branch_q50 = base_q50 + 0.25 + 0.055 * h + 0.25 * np.maximum(h - 10, 0) / 10
    branch_spread = base_spread + 0.15 + 0.015 * h
    base_q10, base_q90 = base_q50 - base_spread, base_q50 + base_spread
    branch_q10, branch_q90 = branch_q50 - branch_spread, branch_q50 + branch_spread
    law_shift = (
        np.abs(branch_q10 - base_q10)
        + np.abs(branch_q50 - base_q50)
        + np.abs(branch_q90 - base_q90)
    ) / 3

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 3.4), gridspec_kw={"width_ratios": [1.35, 1]})
    ax1.fill_between(h, base_q10, base_q90, color="#246BFE", alpha=0.13, label="base q10-q90")
    ax1.plot(h, base_q50, color="#246BFE", linewidth=2.2, label="base median")
    ax1.fill_between(h, branch_q10, branch_q90, color="#E76F51", alpha=0.14, label="forced branch q10-q90")
    ax1.plot(h, branch_q50, color="#E76F51", linewidth=2.2, label="branch median")
    for hh in [5, 12, 20]:
        ax1.annotate("", xy=(hh, branch_q50[hh]), xytext=(hh, base_q50[hh]), arrowprops=dict(arrowstyle="<->", color="#0D1B2A", lw=1.5))
    ax1.set_title("Quantile distributions after one forced token")
    ax1.set_xlabel("forecast horizon h")
    ax1.set_ylabel("forecast value")
    ax1.legend(fontsize=10, loc="upper left")
    ax1.grid(alpha=0.25)

    ax2.plot(h, law_shift, color="#0D1B2A", linewidth=2.3)
    ax2.scatter([int(np.argmax(law_shift))], [float(np.max(law_shift))], color="#E76F51", s=52, zorder=3, label="max_law_shift")
    ax2.axhline(float(np.mean(law_shift)), color="#2A9D8F", linestyle="--", linewidth=1.7, label="mean_law_shift")
    ax2.set_title("Primitive curve: law_shift_h")
    ax2.set_xlabel("forecast horizon h")
    ax2.set_ylabel("mean quantile distance")
    ax2.legend(fontsize=10)
    ax2.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_amplitude_figure(path: Path) -> None:
    plt = _fig_setup()
    h = np.arange(0, 30)
    smooth = 0.25 + 0.018 * h + 0.08 * np.sin(h / 4)
    spike = smooth.copy()
    spike[15:18] += [0.8, 1.1, 0.55]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.1), sharey=True)
    for ax, curve, name in zip(axes, [smooth, spike], ["broad displacement", "local peak displacement"]):
        ax.plot(h, curve, color="#246BFE", linewidth=2.3)
        ax.fill_between(h, 0, curve, color="#246BFE", alpha=0.10)
        ax.axhline(curve.mean(), color="#2A9D8F", linestyle="--", label="mean")
        ax.scatter([curve.argmax()], [curve.max()], color="#E76F51", label="max", zorder=3)
        ax.set_title(name)
        ax.set_xlabel("h")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=10)
    axes[0].set_ylabel("law_shift_h")
    fig.suptitle("Amplitude terms read the same curve in two ways", y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_shape_figure(path: Path) -> None:
    plt = _fig_setup()
    h = np.arange(0, 30)
    convergent = 1.0 * np.exp(-h / 10) + 0.15
    progressive = 0.15 + 0.035 * h + 0.012 * np.maximum(h - 14, 0) ** 1.3
    oscillatory = 0.55 + 0.22 * np.sin(h / 2.3) + 0.05 * np.sin(h / 0.9)
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.1), sharey=True)
    curves = [
        (convergent, "convergent\nlow persistence"),
        (progressive, "progressive\npositive amplification"),
        (oscillatory, "shape break\nirregular curve"),
    ]
    for ax, (curve, name) in zip(axes, curves):
        ax.plot(h, curve, color="#246BFE", linewidth=2.3)
        ax.scatter([h[-1]], [curve[-1]], color="#2A9D8F", s=40, label="last")
        ax.scatter([curve.argmax()], [curve.max()], color="#E76F51", s=45, label="peak")
        ax.set_title(name)
        ax.set_xlabel("h")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("law_shift_h")
    axes[2].legend(fontsize=10, loc="upper left")
    fig.suptitle("Temporal geometry: persistence, amplification, and shape", y=1.04)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_widening_figure(path: Path) -> None:
    plt = _fig_setup()
    h = np.arange(0, 25)
    base_m = 8 + 0.06 * h
    branch_m = base_m + 0.6
    base_spread = 0.65 + 0.02 * np.sin(h / 3)
    branch_spread = 0.75 + 0.035 * h
    base_q10, base_q90 = base_m - base_spread, base_m + base_spread
    branch_q10, branch_q90 = branch_m - branch_spread, branch_m + branch_spread
    widening = (branch_q90 - branch_q10) - (base_q90 - base_q10)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 3.2), gridspec_kw={"width_ratios": [1.35, 1]})
    ax1.fill_between(h, base_q10, base_q90, color="#246BFE", alpha=0.17, label="base interval")
    ax1.fill_between(h, branch_q10, branch_q90, color="#F4A261", alpha=0.23, label="branch interval")
    ax1.plot(h, base_m, color="#246BFE", linewidth=1.8)
    ax1.plot(h, branch_m, color="#E76F51", linewidth=1.8)
    ax1.set_title("Shift can also widen uncertainty")
    ax1.set_xlabel("h")
    ax1.set_ylabel("forecast value")
    ax1.legend(fontsize=10)
    ax1.grid(alpha=0.25)
    ax2.plot(h, widening, color="#E76F51", linewidth=2.3)
    ax2.scatter([widening.argmax()], [widening.max()], color="#0D1B2A", s=50)
    ax2.set_title("max_widening_10_90")
    ax2.set_xlabel("h")
    ax2.set_ylabel("extra q10-q90 width")
    ax2.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_variants_figure(path: Path) -> None:
    plt = _fig_setup()
    h = np.arange(0, 30)
    instant = 0.95 * np.exp(-h / 8) + 0.07
    persistent = 0.35 + 0.03 * np.sin(h / 5)
    progressive = 0.08 + 0.02 * h + 0.006 * np.maximum(h - 14, 0) ** 1.55
    fig, ax = plt.subplots(figsize=(9.8, 3.2))
    ax.plot(h, instant, color="#E76F51", linewidth=2.2, label="instant: high early shift")
    ax.plot(h, persistent, color="#2A9D8F", linewidth=2.2, label="persistent: high late shift")
    ax.plot(h, progressive, color="#246BFE", linewidth=2.2, label="progressive: growing shift")
    ax.axvspan(0, 9, color="#E76F51", alpha=0.06)
    ax.axvspan(20, 29, color="#2A9D8F", alpha=0.06)
    ax.set_title("Three temporal score variants classify different curve shapes")
    ax.set_xlabel("h after branch")
    ax.set_ylabel("law_shift_h / window_scale")
    ax.legend(fontsize=10, ncol=3, loc="upper center")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def build_assets() -> dict[str, Path]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "law": ASSET_DIR / "law_shift_geometry.png",
        "amp": ASSET_DIR / "amplitude_terms.png",
        "shape": ASSET_DIR / "shape_terms.png",
        "widen": ASSET_DIR / "widening_terms.png",
        "variants": ASSET_DIR / "temporal_variants.png",
    }
    save_law_shift_figure(paths["law"])
    save_amplitude_figure(paths["amp"])
    save_shape_figure(paths["shape"])
    save_widening_figure(paths["widen"])
    save_variants_figure(paths["variants"])
    return paths


def run_summary(run_dir: Path) -> dict[str, str]:
    summary = _read_csv(run_dir / "chronos_scan_summary.csv")
    checkpoint_path = run_dir / "checkpoint.json"
    config_path = run_dir / "config.json"
    status = "complete"
    if checkpoint_path.exists():
        try:
            status = json.loads(checkpoint_path.read_text(encoding="utf-8")).get("status", status)
        except json.JSONDecodeError:
            pass
    score = "context_iqr_scaled_progressive_token_bin_forking_score"
    if summary.empty or score not in summary.columns:
        return {"folder": run_dir.name, "status": status, "windows": "n/a", "top": "n/a", "lesson": "CSV not available"}
    windows = len(summary[["dataset_name", "series_id", "window_id", "window_start"]].drop_duplicates())
    top = float(pd.to_numeric(summary[score], errors="coerce").max())
    datasets = ",".join(sorted(summary["dataset_name"].astype(str).unique()))
    if "refinement" in run_dir.name:
        lesson = "Dense branch-step/token-rank map; current snapshot is partial."
    elif "faster_global" in run_dir.name:
        lesson = "Global scan without refinement; useful baseline across ERCOT/exchange_rate/m4_daily."
    else:
        lesson = "First clean topology/temporal scan; validated normalization and logit diagnostics."
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            samples = cfg.get("args", {}).get("num_samples", "")
            lesson = f"{lesson} num_samples={samples}."
        except json.JSONDecodeError:
            pass
    return {
        "folder": run_dir.name,
        "status": status,
        "windows": str(windows),
        "top": f"{top:.3f}",
        "datasets": datasets,
        "lesson": lesson,
    }


def mini_table(rows: list[list[str]], x0: float, y0: float, widths: list[float], font_size: int = 820) -> str:
    out = []
    sid = 700
    for r, row in enumerate(rows):
        x = x0
        for c, value in enumerate(row):
            out.append(
                shape(
                    sid,
                    f"cell-{r}-{c}",
                    x,
                    y0 + r * 0.42,
                    widths[c],
                    0.39,
                    value,
                    "E9EEF6" if r == 0 else "FFFFFF",
                    "CBD6E2",
                    font_size,
                    "18212F",
                    r == 0,
                    False,
                )
            )
            sid += 1
            x += widths[c]
    return "".join(out)


def footer(text: str) -> str:
    return text_box(980, 0.65, 6.25, 12.0, 0.32, [text], 950, "667085")


def big_title(text: str, subtitle: str | None = None) -> str:
    parts = [
        text_box(10, 0.55, 0.24, 12.0, 0.55, [text], 3000, "0D1B2A", True),
    ]
    if subtitle:
        parts.append(text_box(11, 0.58, 0.82, 11.5, 0.35, [subtitle], 1450, "52606D"))
    return "".join(parts)


def rich_box(
    shape_id: int,
    x: float,
    y: float,
    w: float,
    h: float,
    lines: list[tuple[str, bool, bool]],
    fill: str = "FFFFFF",
    line: str = "CBD6E2",
    font_size: int = 1350,
    font_color: str = "18212F",
    radius: bool = True,
) -> str:
    paragraphs = []
    for text, bold, italic in lines:
        bold_xml = ' b="1"' if bold else ""
        italic_xml = ' i="1"' if italic else ""
        paragraphs.append(
            f"""
            <a:p>
              <a:pPr algn="l"/>
              <a:r>
                <a:rPr lang="en-US" sz="{font_size}"{bold_xml}{italic_xml}>
                  <a:solidFill><a:srgbClr val="{color(font_color)}"/></a:solidFill>
                </a:rPr>
                <a:t>{xml_text(text)}</a:t>
              </a:r>
            </a:p>"""
        )
    preset = "roundRect" if radius else "rect"
    return f"""
    <p:sp>
      <p:nvSpPr><p:cNvPr id="{shape_id}" name="Rich {shape_id}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr>
        <a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>
        <a:prstGeom prst="{preset}"><a:avLst/></a:prstGeom>
        <a:solidFill><a:srgbClr val="{color(fill)}"/></a:solidFill>
        <a:ln w="12700"><a:solidFill><a:srgbClr val="{color(line)}"/></a:solidFill></a:ln>
      </p:spPr>
      <p:txBody>
        <a:bodyPr anchor="mid" wrap="square" lIns="121920" rIns="121920" tIns="91440" bIns="91440"/>
        <a:lstStyle/>
        {''.join(paragraphs)}
      </p:txBody>
    </p:sp>"""


def save_progressive_terms_figure(path: Path) -> None:
    plt = _fig_setup()
    h = np.arange(0, 30)
    persistent = 0.22 + 0.018 * h + 0.08 * np.sin(h / 5)
    decaying = 0.85 * np.exp(-h / 10) + 0.08
    bumpy = 0.2 + 0.015 * h + 0.25 * np.sin(h / 3.5).clip(min=-0.5)

    curves = [
        (persistent, "persistent shift\nlast close to max", "#2A9D8F"),
        (decaying, "transient shock\nlast far below max", "#E76F51"),
        (bumpy, "partly monotonic\nmixed growth", "#246BFE"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.4), sharey=True)
    for ax, (curve, name, col) in zip(axes, curves):
        diffs = np.diff(curve)
        mono = np.mean(diffs >= 0)
        last_over_max = curve[-1] / curve.max()
        ax.plot(h, curve, color=col, linewidth=2.7)
        ax.scatter([curve.argmax()], [curve.max()], color="#0D1B2A", s=55, label="max")
        ax.scatter([h[-1]], [curve[-1]], color=col, edgecolor="#0D1B2A", s=65, label="last")
        ax.set_title(f"{name}\nlast/max={last_over_max:.2f}, monotonic={mono:.2f}")
        ax.set_xlabel("h after branch")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("law_shift_h")
    axes[2].legend(fontsize=10, loc="upper left")
    fig.suptitle("Progressive multipliers reward persistent and mostly growing shifts", y=1.05)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_window_scale_figure(path: Path) -> None:
    plt = _fig_setup()
    labels = ["gt mean_abs", "gt std", "gt rms", "gt range", "ctx mean_abs", "ctx std", "ctx rms", "ctx range"]
    ercot = np.array([8600, 720, 8650, 2300, 8450, 810, 8500, 2600], dtype=float)
    exch = np.array([0.73, 0.018, 0.731, 0.065, 0.72, 0.020, 0.722, 0.061], dtype=float)
    values = np.vstack([ercot / ercot.max(), exch / exch.max()])

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.5), sharey=True)
    for ax, vals, title_text, raw in zip(axes, values, ["large-scale load series", "small-scale exchange-rate series"], [ercot, exch]):
        ax.barh(np.arange(len(labels)), vals, color=["#246BFE"] * 4 + ["#2A9D8F"] * 4, alpha=0.82)
        ax.set_yticks(np.arange(len(labels)))
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_xlim(0, 1.08)
        ax.set_title(f"{title_text}\nwindow_scale = max candidate = {raw.max():.3g}")
        ax.set_xlabel("candidate / window_scale")
        ax.grid(axis="x", alpha=0.25)
    fig.suptitle("Window normalization chooses one local denominator per window", y=1.05)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def build_slides(assets: dict[str, Path]) -> tuple[list[str], list[list[Path]]]:
    assets["progressive_terms"] = ASSET_DIR / "progressive_multipliers.png"
    assets["window_scale"] = ASSET_DIR / "window_scale_normalization.png"
    save_progressive_terms_figure(assets["progressive_terms"])
    save_window_scale_figure(assets["window_scale"])

    slides: list[str] = []
    images: list[list[Path]] = []

    pipeline = big_title("Chronos FPA Pipeline", "Token-level branching for time-series forecasts")
    labels = [
        ("Local benchmark\nexports", "E9EEF6"),
        ("Sliding windows\ncontext + horizon", "FFFFFF"),
        ("Chronos logits\nnext-token distribution", "EAF3FF"),
        ("Force token\nat branch_step", "FFF4E6"),
        ("Sample future\ncontinuations", "ECFDF5"),
        ("Compare quantile\nlaws", "FFFFFF"),
        ("Score + rank\nsensitive zones", "FCEEEF"),
    ]
    x0, y0 = 0.42, 1.55
    for i, (label, fill) in enumerate(labels):
        x = x0 + i * 1.78
        y = y0 + (0.20 if i % 2 else 0)
        pipeline += shape(30 + i, label, x, y, 1.48, 1.12, label, fill, "CBD6E2", 1050, "18212F", True)
        if i < len(labels) - 1:
            pipeline += arrow(60 + i, x + 1.50, y + 0.56, x0 + (i + 1) * 1.78 - 0.05, y0 + (0.20 if (i + 1) % 2 else 0) + 0.56)
    pipeline += rich_box(
        80,
        0.75,
        3.75,
        11.9,
        1.05,
        [
            ("Core question", True, False),
            ("If Chronos is forced to take a different plausible token now, how far does the future predictive distribution move?", False, True),
        ],
        "FFFFFF",
        "DDE6F0",
        1450,
    )
    pipeline += bullet_list(
        90,
        0.95,
        5.15,
        11.2,
        [
            "Single scan: broad coverage with a few branch steps and top-k tokens.",
            "Targeted refinement: rerun sensitive windows with denser steps and more token ranks.",
        ],
        1350,
    )
    pipeline += footer("Traceability: input_config.json, config.json, checkpoint.json, chronos_scan_summary.csv.")
    slides.append(slide_xml(pipeline))
    images.append([])

    slides.append(
        slide_xml(
            big_title("Primitive Signal: Quantile Law Shift", "The score compresses this curve, so the geometry matters")
            + picture(110, "rId2", 0.58, 1.28, 7.25, 4.05, "law_shift")
            + rich_box(
                120,
                8.05,
                1.35,
                4.55,
                1.45,
                [
                    ("law_shift_h", True, False),
                    ("= mean_q | Q_branch(h,q) - Q_base(h,q) |", True, False),
                    ("q = 10, 20, ..., 90", False, True),
                ],
                "EAF3FF",
                "B7CDFB",
                1250,
            )
            + bullet_list(
                130,
                8.15,
                3.15,
                4.1,
                [
                    "Both base and branch are sampled futures.",
                    "Each h compares two predictive distributions.",
                    "The curve tells whether the branch converges, persists, or amplifies.",
                ],
                1180,
            )
            + footer("Visual reading: vertical distance between base and forced-branch quantile bands.")
        )
    )
    images.append([assets["law"]])

    formula = (
        big_title("Forking Score Equation", "Five components plus two progressive multipliers")
        + rich_box(
            150,
            0.7,
            1.15,
            12.0,
            1.45,
            [
                ("token_bin_forking_score =", True, False),
                ("0.40 mean_law_shift + 0.25 max_law_shift + 0.15 positive_law_amplification", True, False),
                ("+ 0.10 shape_break + 0.10 max_widening_10_90", True, False),
            ],
            "FFFFFF",
            "CBD6E2",
            1180,
        )
        + rich_box(
            151,
            0.7,
            2.95,
            12.0,
            1.30,
            [
                ("progressive_token_bin_forking_score =", True, False),
                ("token_bin_forking_score * (0.5 + 0.5 last_over_max_law)", True, False),
                ("* (0.5 + 0.5 monotonic_growth_fraction)", True, False),
            ],
            "EAF3FF",
            "B7CDFB",
            1180,
        )
        + shape(
            152,
            "Grouped meaning",
            0.8,
            4.75,
            11.8,
            0.85,
            "Amplitude terms measure how far the law moved; shape terms measure how the movement behaves over time.",
            "FFF4E6",
            "F3C98B",
            1250,
            "0D1B2A",
            True,
        )
        + footer("Next slides explain each geometric family separately.")
    )
    slides.append(slide_xml(formula))
    images.append([])

    slides.append(
        slide_xml(
            big_title("Amplitude Terms", "mean_law_shift and max_law_shift")
            + picture(180, "rId2", 0.62, 1.28, 7.4, 3.75, "amplitude")
            + rich_box(
                190,
                8.25,
                1.35,
                4.2,
                1.25,
                [
                    ("mean_law_shift", True, False),
                    ("Average displacement across the horizon.", False, False),
                    ("Broad sensitivity.", False, True),
                ],
                "ECFDF5",
                "B7E4D7",
                1240,
            )
            + rich_box(
                191,
                8.25,
                2.95,
                4.2,
                1.25,
                [
                    ("max_law_shift", True, False),
                    ("Largest local displacement.", False, False),
                    ("Peak sensitivity.", False, True),
                ],
                "FFF4E6",
                "F3C98B",
                1240,
            )
            + footer("Both terms have data units, so they must be divided by window_scale for global comparison.")
        )
    )
    images.append([assets["amp"]])

    slides.append(
        slide_xml(
            big_title("Temporal Shape Terms", "Amplification, shape break, and the progressive multipliers")
            + picture(210, "rId2", 0.58, 1.20, 6.35, 2.65, "shape")
            + picture(211, "rId3", 0.58, 3.92, 6.35, 2.15, "progressive")
            + rich_box(
                220,
                7.25,
                1.25,
                5.15,
                1.15,
                [
                    ("positive_law_amplification", True, False),
                    ("max((law_last - law_first) / mean_law, 0)", False, False),
                ],
                "EAF3FF",
                "B7CDFB",
                1070,
            )
            + rich_box(
                221,
                7.25,
                2.62,
                5.15,
                1.15,
                [
                    ("shape_break", True, False),
                    ("Detects temporal deformation, not just a constant offset.", False, True),
                ],
                "FFF4E6",
                "F3C98B",
                1120,
            )
            + rich_box(
                222,
                7.25,
                4.00,
                5.15,
                1.45,
                [
                    ("last_over_max_law = law_last / max_law", True, False),
                    ("High when the final shift stays close to the peak.", False, False),
                    ("monotonic_growth_fraction = fraction of non-decreasing steps", True, False),
                    ("High when the shift mostly grows instead of oscillating down.", False, False),
                ],
                "FFFFFF",
                "CBD6E2",
                980,
            )
            + footer("The two multipliers reward branches whose effect is persistent and mostly growing.")
        )
    )
    images.append([assets["shape"], assets["progressive_terms"]])

    slides.append(
        slide_xml(
            big_title("Distribution Widening", "max_widening_10_90")
            + picture(250, "rId2", 0.65, 1.28, 7.25, 3.75, "widening")
            + rich_box(
                260,
                8.15,
                1.55,
                4.25,
                1.35,
                [
                    ("widening_10_90_h", True, False),
                    ("= width_branch(h) - width_base(h)", False, False),
                    ("where width = q90 - q10", False, True),
                ],
                "FCEEEF",
                "F3B6C2",
                1180,
            )
            + bullet_list(
                270,
                8.25,
                3.35,
                4.0,
                [
                    "Captures uncertainty expansion.",
                    "Separate from median displacement.",
                    "Normalized by window_scale in global scores.",
                ],
                1180,
            )
            + footer("A branch can be important because it widens future uncertainty, even if the median shift is modest.")
        )
    )
    images.append([assets["widen"]])

    slides.append(
        slide_xml(
            big_title("Window Normalization", "Why raw scores were misleading across datasets")
            + picture(280, "rId2", 0.65, 1.25, 6.6, 3.45, "window_scale")
            + rich_box(
                290,
                7.55,
                1.25,
                4.95,
                1.25,
                [
                    ("Problem", True, False),
                    ("A 100 MW shift and a 0.01 exchange-rate shift are not comparable in raw units.", False, False),
                ],
                "FFF4E6",
                "F3C98B",
                1100,
            )
            + rich_box(
                291,
                7.55,
                2.80,
                4.95,
                1.55,
                [
                    ("window_scale", True, False),
                    ("max of non-zero finite scale candidates from both ground truth and context:", False, False),
                    ("mean_abs, std, rms, range", True, True),
                ],
                "ECFDF5",
                "B7E4D7",
                1040,
            )
            + rich_box(
                292,
                0.85,
                5.00,
                11.6,
                0.85,
                [
                    ("Only dimensional components are divided by window_scale:", True, False),
                    ("mean_law_shift, max_law_shift, max_widening_10_90. Shape and amplification stay dimensionless.", False, True),
                ],
                "FFFFFF",
                "CBD6E2",
                1120,
            )
            + footer("This correction prevents large-scale datasets such as ERCOT from dominating only because of units.")
        )
    )
    images.append([assets["window_scale"]])

    slides.append(
        slide_xml(
            big_title("Score Variants And Guardrails", "Interpreting what kind of sensitivity was found")
            + picture(300, "rId2", 0.65, 1.18, 6.7, 3.10, "variants")
            + rich_box(
                310,
                7.65,
                1.18,
                4.75,
                1.05,
                [("instant_forking_score", True, False), ("early_law_shift / window_scale", False, True)],
                "FCEEEF",
                "F3B6C2",
                1180,
            )
            + rich_box(
                311,
                7.65,
                2.45,
                4.75,
                1.05,
                [("persistent_forking_score", True, False), ("late_law_shift / window_scale * persistence factor", False, True)],
                "ECFDF5",
                "B7E4D7",
                1050,
            )
            + rich_box(
                312,
                7.65,
                3.72,
                4.75,
                1.05,
                [("progressive_forking_score", True, False), ("late-vs-early growth, weighted by monotonicity", False, True)],
                "EAF3FF",
                "B7CDFB",
                1080,
            )
            + shape(
                313,
                "Guardrail",
                0.9,
                4.95,
                11.35,
                0.85,
                "Base-quality warning: base_mae / window_scale flags windows where Chronos is already poor before branching.",
                "FFFFFF",
                "CBD6E2",
                1250,
                "0D1B2A",
                True,
            )
            + footer("The variants do not replace the main ranking; they classify immediate, persistent, or progressive shifts.")
        )
    )
    images.append([assets["variants"]])

    summaries = [run_summary(path) for path in RUNS if path.exists()]
    rows = [["Run folder", "status", "windows", "top"]]
    for item in summaries:
        rows.append([item["folder"], item["status"], item["windows"], item["top"]])
    experiments = (
        big_title("Experiments And Lessons Learned", "High-level findings; folders provide traceability")
        + mini_table(rows, 0.55, 1.20, [5.2, 1.2, 1.0, 1.0], 920)
        + rich_box(
            340,
            0.75,
            3.35,
            11.9,
            1.10,
            [
                ("What we learned", True, False),
                ("Large shifts are often associated with plausible/high-probability tokens, not only unlikely stress tokens.", False, False),
            ],
            "EAF3FF",
            "B7CDFB",
            1250,
        )
        + bullet_list(
            350,
            0.95,
            4.80,
            11.2,
            [
                "Dense refinement helps localize sensitive branch_steps between coarse scan points.",
                "Normalization and base-quality warnings were two major methodological corrections.",
                "Next: topology classification at high-shift points and dynamic branch-step selection.",
            ],
            1250,
        )
        + footer("Folders: topology_temporal_single_20260724_175602; faster_global_scan_no_refinement_20260727_173315; refinement_faster_global_20260728_125930.")
    )
    slides.append(slide_xml(experiments))
    images.append([])

    return slides, images


def build_slides_legacy(assets: dict[str, Path]) -> tuple[list[str], list[list[Path]]]:
    slides: list[str] = []
    images: list[list[Path]] = []

    pipeline = title("Chronos FPA Pipeline", "Token-level branching for time-series forecasts")
    labels = [
        ("Local benchmark\nexports", "E9EEF6"),
        ("Sliding windows\ncontext + horizon", "FFFFFF"),
        ("Chronos base\nnext-token logits", "EAF3FF"),
        ("Force token\nat branch_step", "FFF4E6"),
        ("Sample future\ncontinuations", "ECFDF5"),
        ("Quantile law\ncomparison", "FFFFFF"),
        ("Forking scores\n+ figures", "FCEEEF"),
    ]
    x0, y0 = 0.45, 1.48
    for i, (label, fill) in enumerate(labels):
        x = x0 + i * 1.78
        y = y0 + (0.22 if i % 2 else 0)
        pipeline += shape(30 + i, label, x, y, 1.45, 1.05, label, fill, "CBD6E2", 900, "18212F", True)
        if i < len(labels) - 1:
            pipeline += arrow(60 + i, x + 1.47, y + 0.53, x0 + (i + 1) * 1.78 - 0.05, y0 + (0.22 if (i + 1) % 2 else 0) + 0.53)
    pipeline += shape(
        80,
        "Principle",
        0.85,
        3.65,
        11.7,
        1.05,
        "Core question: if Chronos is forced to take a different plausible token now,\nhow far does the future predictive distribution move?",
        "FFFFFF",
        "DDE6F0",
        1350,
        "0D1B2A",
        True,
    )
    pipeline += bullet_list(
        90,
        1.05,
        5.05,
        11.0,
        [
            "Single mode: test top-k candidate tokens at one forecast step.",
            "Refinement mode: rerun selected sensitive windows with denser branch steps and more token ranks.",
            "Outputs are traceable through input_config.json, config.json, checkpoint.json and CSV summaries.",
        ],
        1150,
    )
    pipeline += footer("Traceability docs: docs/CHRONOS_METRICS.md, docs/recherche/, configs/")
    slides.append(slide_xml(pipeline))
    images.append([])

    slides.append(
        slide_xml(
            title("Primitive Signal: Quantile Law Shift", "Everything starts from the curve law_shift_h")
            + picture(110, "rId2", 0.65, 1.25, 7.05, 3.95, "law_shift")
            + shape(
                120,
                "Formula",
                8.05,
                1.35,
                4.55,
                1.35,
                "law_shift_h = mean_q |\nQ_branch(h,q) - Q_base(h,q) |",
                "EAF3FF",
                "B7CDFB",
                1300,
                "0D1B2A",
                True,
            )
            + bullet_list(
                130,
                8.15,
                3.05,
                4.15,
                [
                    "q in {10,20,...,90}.",
                    "Base and branch are both sampled distributions.",
                    "The curve keeps the temporal geometry of the shift.",
                    "The final score compresses this curve into interpretable components.",
                ],
                980,
            )
            + footer("Geometric intuition: distance between two quantile laws across the forecast horizon.")
        )
    )
    images.append([assets["law"]])

    formula = (
        title("Forking Score: Full Equation", "Raw, normalized and progressive variants")
        + shape(
            150,
            "Raw",
            0.75,
            1.2,
            11.9,
            1.25,
            "token_bin_forking_score = 0.40 mean_law_shift + 0.25 max_law_shift\n"
            "+ 0.15 positive_law_amplification + 0.10 shape_break + 0.10 max_widening_10_90",
            "FFFFFF",
            "CBD6E2",
            1040,
            "0D1B2A",
            True,
        )
        + shape(
            151,
            "Progressive",
            0.75,
            2.75,
            11.9,
            1.05,
            "progressive_token_bin_forking_score = token_bin_forking_score\n"
            "* (0.5 + 0.5 last_over_max_law) * (0.5 + 0.5 monotonic_growth_fraction)",
            "EAF3FF",
            "B7CDFB",
            1040,
            "0D1B2A",
            True,
        )
        + shape(
            152,
            "Normalized",
            0.75,
            4.15,
            5.75,
            1.25,
            "window_scaled score\nDivide dimensional terms by window_scale:\nmean, max, widening.",
            "ECFDF5",
            "B7E4D7",
            1060,
            "0D1B2A",
            True,
        )
        + shape(
            153,
            "Window scale",
            6.9,
            4.15,
            5.75,
            1.25,
            "window_scale = max(gt/context mean_abs, std, rms, range)\nAvoids division by zero and dataset-scale domination.",
            "FFF4E6",
            "F3C98B",
            980,
            "0D1B2A",
            True,
        )
        + footer("Global rankings should use context_iqr_scaled_progressive_token_bin_forking_score, with fallback recorded in config.json.")
    )
    slides.append(slide_xml(formula))
    images.append([])

    slides.append(
        slide_xml(
            title("Term Family 1: Amplitude", "mean_law_shift and max_law_shift")
            + picture(180, "rId2", 0.72, 1.25, 7.2, 3.65, "amplitude")
            + bullet_list(
                190,
                8.15,
                1.55,
                4.0,
                [
                    "mean_law_shift: average displacement over horizon.",
                    "max_law_shift: strongest local displacement.",
                    "Together: broad sensitivity vs sharp peak sensitivity.",
                    "Both have data units, so both need window_scale normalization.",
                ],
                1030,
            )
            + footer("Both terms are derived from the same law_shift_h curve.")
        )
    )
    images.append([assets["amp"]])

    slides.append(
        slide_xml(
            title("Term Family 2: Temporal Shape", "positive amplification and shape break")
            + picture(210, "rId2", 0.68, 1.25, 7.35, 3.55, "shape")
            + shape(
                220,
                "Amplification",
                8.25,
                1.35,
                4.15,
                1.15,
                "positive_law_amplification\nrewards curves that grow after the branch.",
                "EAF3FF",
                "B7CDFB",
                1050,
                "0D1B2A",
                True,
            )
            + shape(
                221,
                "Shape",
                8.25,
                2.8,
                4.15,
                1.15,
                "shape_break\ncaptures non-trivial temporal deformation, not just a constant offset.",
                "FFF4E6",
                "F3C98B",
                1000,
                "0D1B2A",
                True,
            )
            + bullet_list(230, 8.35, 4.35, 3.95, ["Interpretation: immediate shock, persistent divergence, or delayed amplification are different phenomena."], 920)
            + footer("These terms are dimensionless geometry descriptors of the law_shift_h curve.")
        )
    )
    images.append([assets["shape"]])

    slides.append(
        slide_xml(
            title("Term Family 3: Distribution Widening", "max_widening_10_90")
            + picture(250, "rId2", 0.75, 1.25, 7.05, 3.65, "widening")
            + bullet_list(
                260,
                8.1,
                1.55,
                4.15,
                [
                    "A branch can shift the median and/or widen the predictive band.",
                    "widening_10_90_h compares q90-q10 branch width to q90-q10 base width.",
                    "max_widening_10_90 keeps the largest extra uncertainty introduced by the branch.",
                    "It has data units, so it is normalized by window_scale in global comparisons.",
                ],
                970,
            )
            + footer("This term captures uncertainty expansion, not only central displacement.")
        )
    )
    images.append([assets["widen"]])

    slides.append(
        slide_xml(
            title("Corrections And Score Variants", "Making scores comparable and interpretable")
            + picture(280, "rId2", 0.7, 1.2, 6.65, 3.2, "variants")
            + shape(
                290,
                "Method corrections",
                7.65,
                1.2,
                4.95,
                1.25,
                "Normalization\nUse one window_scale across comparisons to avoid ERCOT-scale domination.",
                "ECFDF5",
                "B7E4D7",
                980,
                "0D1B2A",
                True,
            )
            + shape(
                291,
                "Data handling",
                7.65,
                2.7,
                4.95,
                1.25,
                "Quality guardrails\nbase_mae/window_scale warnings identify windows where Chronos is already poor.",
                "FFF4E6",
                "F3C98B",
                930,
                "0D1B2A",
                True,
            )
            + shape(
                292,
                "Variants",
                0.95,
                4.85,
                11.35,
                0.85,
                "instant = early/window_scale    persistent = late/window_scale * persistence    progressive = growing late-vs-early shift",
                "FFFFFF",
                "CBD6E2",
                980,
                "0D1B2A",
                True,
            )
            + footer("Engineering corrections: local dataset exports, JSON configs, checkpoints, resume, and targeted refinement.")
        )
    )
    images.append([assets["variants"]])

    summaries = [run_summary(path) for path in RUNS if path.exists()]
    rows = [["Run folder", "status", "windows", "top", "lesson"]]
    for item in summaries:
        rows.append([item["folder"], item["status"], item["windows"], item["top"], item["lesson"]])
    experiments = (
        title("Experiments And Lessons Learned", "High-level findings; folders provide traceability")
        + mini_table(rows, 0.45, 1.25, [3.15, 0.75, 0.75, 0.65, 7.0], 680)
        + bullet_list(
            340,
            0.8,
            4.45,
            11.45,
            [
                "Large shifts are often associated with plausible/high-probability tokens, not only unlikely stress tokens.",
                "Dense refinement is useful: sensitive locations can appear between coarse branch steps.",
                "Normalization and base-quality warnings were necessary before comparing datasets.",
                "Next research step: classify topology at high-shift points and move toward dynamic step selection.",
            ],
            1070,
        )
        + footer("Current partial refinement snapshot: result/refinement_faster_global_20260728_125930.")
    )
    slides.append(slide_xml(experiments))
    images.append([])

    return slides, images


def create_pptx() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    assets = build_assets()
    slides, slide_images = build_slides(assets)

    media_entries: dict[Path, str] = {}
    counter = 1
    for paths in slide_images:
        for path in paths:
            if path.exists() and path not in media_entries:
                media_entries[path] = f"image{counter}.png"
                counter += 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types(len(slides), list(media_entries.values())))
        archive.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        archive.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(slides)))
        for path, xml in static_parts(now, len(slides)).items():
            archive.writestr(path, xml)
        for img_path, media_name in media_entries.items():
            archive.write(img_path, f"ppt/media/{media_name}")
        for i, slide in enumerate(slides, start=1):
            archive.writestr(f"ppt/slides/slide{i}.xml", slide)
            targets = [media_entries[p] for p in slide_images[i - 1] if p in media_entries]
            archive.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", slide_rels(targets))
    return OUT


if __name__ == "__main__":
    print(create_pptx())




