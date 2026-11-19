from __future__ import annotations

import csv
import json
import math
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[2]
RUN_DIRS = [
    ROOT / "result" / "chronos_benchmark_scan_20260724_100706",
    ROOT / "result" / "chronos_benchmark_scan_20260722_105802",
    ROOT / "result" / "chronos_benchmark_scan_20260721_151625",
]
OUT = ROOT / "presentations" / "chronos_fpa_avancement.pptx"

SLIDE_W = 12192000
SLIDE_H = 6858000


def emu(inches: float) -> int:
    return int(inches * 914400)


def xml_text(text: str) -> str:
    return escape(text or "")


def color(hex_color: str) -> str:
    return hex_color.replace("#", "").upper()


def shape(
    shape_id: int,
    name: str,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str = "",
    fill: str = "FFFFFF",
    line: str = "D7DEE8",
    font_size: int = 1800,
    font_color: str = "18212F",
    bold: bool = False,
    radius: bool = True,
    align: str = "ctr",
    valign: str = "mid",
) -> str:
    preset = "roundRect" if radius else "rect"
    bold_xml = ' b="1"' if bold else ""
    paragraphs = []
    for part in text.split("\n"):
        paragraphs.append(
            f"""
            <a:p>
              <a:pPr algn="{align}"/>
              <a:r>
                <a:rPr lang="fr-FR" sz="{font_size}"{bold_xml}>
                  <a:solidFill><a:srgbClr val="{color(font_color)}"/></a:solidFill>
                </a:rPr>
                <a:t>{xml_text(part)}</a:t>
              </a:r>
            </a:p>"""
        )
    return f"""
    <p:sp>
      <p:nvSpPr>
        <p:cNvPr id="{shape_id}" name="{xml_text(name)}"/>
        <p:cNvSpPr/>
        <p:nvPr/>
      </p:nvSpPr>
      <p:spPr>
        <a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>
        <a:prstGeom prst="{preset}"><a:avLst/></a:prstGeom>
        <a:solidFill><a:srgbClr val="{color(fill)}"/></a:solidFill>
        <a:ln w="12700"><a:solidFill><a:srgbClr val="{color(line)}"/></a:solidFill></a:ln>
      </p:spPr>
      <p:txBody>
        <a:bodyPr anchor="{valign}" wrap="square" lIns="91440" rIns="91440" tIns="45720" bIns="45720"/>
        <a:lstStyle/>
        {''.join(paragraphs)}
      </p:txBody>
    </p:sp>"""


def text_box(
    shape_id: int,
    x: float,
    y: float,
    w: float,
    h: float,
    lines: list[str],
    font_size: int = 1800,
    font_color: str = "18212F",
    bold_first: bool = False,
) -> str:
    paragraphs = []
    for i, line in enumerate(lines):
        bold_xml = ' b="1"' if i == 0 and bold_first else ""
        paragraphs.append(
            f"""
            <a:p>
              <a:pPr marL="0" indent="0"/>
              <a:r>
                <a:rPr lang="fr-FR" sz="{font_size}"{bold_xml}>
                  <a:solidFill><a:srgbClr val="{color(font_color)}"/></a:solidFill>
                </a:rPr>
                <a:t>{xml_text(line)}</a:t>
              </a:r>
            </a:p>"""
        )
    return f"""
    <p:sp>
      <p:nvSpPr><p:cNvPr id="{shape_id}" name="Text {shape_id}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr>
        <a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>
        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
        <a:noFill/><a:ln><a:noFill/></a:ln>
      </p:spPr>
      <p:txBody>
        <a:bodyPr wrap="square" lIns="0" rIns="0" tIns="0" bIns="0"/>
        <a:lstStyle/>
        {''.join(paragraphs)}
      </p:txBody>
    </p:sp>"""


def title(text: str, subtitle: str | None = None) -> str:
    parts = [
        text_box(10, 0.55, 0.28, 11.8, 0.45, [text], 2600, "0D1B2A", True),
    ]
    if subtitle:
        parts.append(text_box(11, 0.58, 0.78, 11.0, 0.3, [subtitle], 1200, "52606D"))
    return "".join(parts)


def bullet_list(
    start_id: int,
    x: float,
    y: float,
    w: float,
    items: list[str],
    font_size: int = 1450,
    line_h: float = 0.47,
    color_hex: str = "18212F",
) -> str:
    out = []
    for i, item in enumerate(items):
        out.append(shape(start_id + i * 2, f"Dot {i}", x, y + i * line_h + 0.08, 0.08, 0.08, "", "246BFE", "246BFE", radius=True))
        out.append(text_box(start_id + i * 2 + 1, x + 0.22, y + i * line_h, w - 0.25, 0.35, [item], font_size, color_hex))
    return "".join(out)


def arrow(shape_id: int, x1: float, y1: float, x2: float, y2: float, line: str = "698096") -> str:
    return f"""
    <p:cxnSp>
      <p:nvCxnSpPr><p:cNvPr id="{shape_id}" name="Arrow {shape_id}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
      <p:spPr>
        <a:xfrm><a:off x="{emu(min(x1, x2))}" y="{emu(min(y1, y2))}"/><a:ext cx="{emu(abs(x2-x1))}" cy="{emu(abs(y2-y1))}"/></a:xfrm>
        <a:prstGeom prst="line"><a:avLst/></a:prstGeom>
        <a:ln w="25400">
          <a:solidFill><a:srgbClr val="{color(line)}"/></a:solidFill>
          <a:tailEnd type="triangle"/>
        </a:ln>
      </p:spPr>
      <p:style><a:lnRef idx="1"><a:schemeClr val="accent1"/></a:lnRef><a:fillRef idx="0"><a:schemeClr val="accent1"/></a:fillRef><a:effectRef idx="0"><a:schemeClr val="accent1"/></a:effectRef><a:fontRef idx="minor"><a:schemeClr val="tx1"/></a:fontRef></p:style>
    </p:cxnSp>"""


def picture(shape_id: int, rel_id: str, x: float, y: float, w: float, h: float, name: str) -> str:
    return f"""
    <p:pic>
      <p:nvPicPr><p:cNvPr id="{shape_id}" name="{xml_text(name)}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
      <p:blipFill>
        <a:blip r:embed="{rel_id}"/>
        <a:stretch><a:fillRect/></a:stretch>
      </p:blipFill>
      <p:spPr>
        <a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>
        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
      </p:spPr>
    </p:pic>"""


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def summarize_run(run_dir: Path) -> dict[str, object]:
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    ranking = read_csv(run_dir / "chronos_scan_ranking.csv")
    warnings = read_csv(run_dir / "chronos_base_quality_warnings.csv")
    datasets = sorted({row.get("dataset_name", "") for row in ranking if row.get("dataset_name")})
    top = ranking[0] if ranking else {}
    scores = []
    for row in ranking:
        try:
            scores.append(float(row.get("progressive_token_bin_forking_score", "nan")))
        except ValueError:
            pass
    return {
        "name": run_dir.name.replace("chronos_benchmark_scan_", ""),
        "branch_modes": ", ".join(config.get("branch_modes", [])),
        "branch_steps": ", ".join(str(v) for v in config.get("branch_steps", [])),
        "windows": config.get("scanned_windows", 0),
        "samples": config.get("args", {}).get("num_samples", ""),
        "datasets": ", ".join(datasets[:4]) + ("..." if len(datasets) > 4 else ""),
        "top_dataset": top.get("dataset_name", ""),
        "top_series": top.get("series_id", ""),
        "top_score": max(scores) if scores else 0.0,
        "warnings": len(warnings),
    }


def table(run_summaries: list[dict[str, object]]) -> str:
    headers = ["Run", "Mode", "Fen.", "Datasets", "Top score", "Top dataset", "Warnings"]
    widths = [1.7, 1.25, 0.65, 2.9, 1.2, 1.25, 0.8]
    x0, y0 = 0.65, 1.55
    out = []
    x = x0
    for h, w in zip(headers, widths):
        out.append(shape(200 + len(out), h, x, y0, w, 0.38, h, "E9EEF6", "CBD6E2", 950, "223044", True, False))
        x += w
    for r, row in enumerate(run_summaries):
        y = y0 + 0.42 + r * 0.52
        vals = [
            str(row["name"]),
            str(row["branch_modes"]),
            str(row["windows"]),
            str(row["datasets"]),
            f"{float(row['top_score']):.1f}",
            str(row["top_dataset"]),
            str(row["warnings"]),
        ]
        x = x0
        for val, w in zip(vals, widths):
            out.append(shape(230 + r * 10 + len(out), val, x, y, w, 0.46, val, "FFFFFF", "E2E8F0", 850, "18212F", False, False))
            x += w
    return "".join(out)


def slide_xml(content: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="F8FAFC"/></a:solidFill></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      {content}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def slide_rels(image_targets: list[str]) -> str:
    rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>']
    for i, target in enumerate(image_targets, start=2):
        rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{target}"/>')
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{''.join(rels)}</Relationships>"""


def content_types(n_slides: int, media_names: list[str]) -> str:
    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for i in range(1, n_slides + 1):
        overrides.append(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  {''.join(overrides)}
</Types>"""


def presentation_xml(n_slides: int) -> str:
    ids = "".join(f'<p:sldId id="{255+i}" r:id="rId{i}"/>' for i in range(1, n_slides + 1))
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId{n_slides + 1}"/></p:sldMasterIdLst>
  <p:sldIdLst>{ids}</p:sldIdLst>
  <p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""


def presentation_rels(n_slides: int) -> str:
    rels = []
    for i in range(1, n_slides + 1):
        rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>')
    rels.append(f'<Relationship Id="rId{n_slides + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>')
    rels.append(f'<Relationship Id="rId{n_slides + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>')
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{''.join(rels)}</Relationships>"""


def static_parts(now: str, n_slides: int) -> dict[str, str]:
    master = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>"""
    layout = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""
    theme = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Chronos FPA">
  <a:themeElements>
    <a:clrScheme name="Chronos"><a:dk1><a:srgbClr val="0D1B2A"/></a:dk1><a:lt1><a:srgbClr val="F8FAFC"/></a:lt1><a:dk2><a:srgbClr val="18212F"/></a:dk2><a:lt2><a:srgbClr val="E9EEF6"/></a:lt2><a:accent1><a:srgbClr val="246BFE"/></a:accent1><a:accent2><a:srgbClr val="00A896"/></a:accent2><a:accent3><a:srgbClr val="F4A261"/></a:accent3><a:accent4><a:srgbClr val="E76F51"/></a:accent4><a:accent5><a:srgbClr val="6D5DF6"/></a:accent5><a:accent6><a:srgbClr val="2A9D8F"/></a:accent6><a:hlink><a:srgbClr val="246BFE"/></a:hlink><a:folHlink><a:srgbClr val="6D5DF6"/></a:folHlink></a:clrScheme>
    <a:fontScheme name="Aptos"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme>
    <a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle/></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
  </a:themeElements>
</a:theme>"""
    core = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>FPA sur Chronos - Ã©tat d'avancement</dc:title><dc:creator>Codex</dc:creator><cp:lastModifiedBy>Codex</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>"""
    app = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Codex</Application><PresentationFormat>On-screen Show (16:9)</PresentationFormat><Slides>{n_slides}</Slides></Properties>"""
    return {
        "ppt/slideMasters/slideMaster1.xml": master,
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>',
        "ppt/slideLayouts/slideLayout1.xml": layout,
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>',
        "ppt/theme/theme1.xml": theme,
        "docProps/core.xml": core,
        "docProps/app.xml": app,
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>',
    }


def build_slides(run_summaries: list[dict[str, object]]) -> tuple[list[str], list[list[Path]]]:
    recent = RUN_DIRS[0]
    single = RUN_DIRS[1]
    images = [
        recent / "figures" / "chronos_score_distribution.png",
        recent / "figures" / "chronos_base_quality.png",
        single / "figures" / "chronos_top_branch_scores.png",
    ]

    slides: list[str] = []
    slide_images: list[list[Path]] = []

    slides.append(slide_xml(
        title("FPA sur Chronos", "Ã‰tat d'avancement - pipeline token-level branching")
        + shape(20, "Main", 0.85, 1.75, 11.6, 1.4, "Objectif actuel\nIdentifier oÃ¹ les prÃ©visions Chronos deviennent sensibles au choix du token forcÃ©.", "FFFFFF", "DDE6F0", 2100, "0D1B2A", True)
        + bullet_list(30, 1.1, 3.6, 11.0, [
            "Statut : pipeline fonctionnelle sur exports locaux des datasets Chronos.",
            "Lecture prudente : les scores bruts dÃ©tectent des shifts, mais ne sont pas encore comparables entre datasets.",
            "But de la suite : normaliser, isoler les cas rÃ©ellement interprÃ©tables, puis Ã©largir le scan.",
        ], 1450)
    ))
    slide_images.append([])

    slides.append(slide_xml(
        title("Message Principal")
        + shape(40, "Claim", 0.8, 1.3, 11.8, 1.45, "La mÃ©thode FPA est utilisÃ©e comme sonde de sensibilitÃ© locale,\npas encore comme mÃ©trique finale de performance.", "EAF3FF", "B7CDFB", 1900, "0D1B2A", True)
        + bullet_list(50, 1.0, 3.05, 11.1, [
            "On force des tokens alternatifs dans Chronos puis on observe les trajectoires futures.",
            "Un fort shift signale une zone oÃ¹ le modÃ¨le dÃ©pend fortement du chemin de dÃ©codage.",
            "La question de recherche devient : ce shift correspond-il Ã  une ambiguÃ¯tÃ© utile, Ã  une erreur Chronos, ou Ã  un artefact d'Ã©chelle ?",
        ], 1500)
    ))
    slide_images.append([])

    slides.append(slide_xml(
        title("Pourquoi Chronos", "Transition depuis TimesFM vers un modÃ¨le plus naturel pour le branching")
        + shape(60, "TimesFM", 0.9, 1.6, 4.9, 1.2, "TimesFM\nPrÃ©vision directe / patch-based", "FFFFFF", "DDE6F0", 1600, "18212F", True)
        + arrow(61, 5.95, 2.2, 7.25, 2.2)
        + shape(62, "Chronos", 7.45, 1.6, 4.9, 1.2, "Chronos v1\nPrÃ©vision via tokens quantifiÃ©s", "EAF3FF", "B7CDFB", 1600, "0D1B2A", True)
        + bullet_list(70, 1.1, 3.45, 11.0, [
            "Chronos convertit la sÃ©rie en tokens de valeur, puis dÃ©code une sÃ©quence future.",
            "Cette structure permet de faire un Ã©quivalent FPA proche du branching LLM : forcer un token, puis Ã©chantillonner la suite.",
            "On ne cherche pas ici Ã  battre un benchmark, mais Ã  comprendre les zones de dÃ©viation/convergence du modÃ¨le.",
        ], 1400)
    ))
    slide_images.append([])

    pipeline = title("Pipeline Actuelle", "Vue globale du scan Chronos FPA")
    labels = [
        ("Exports locaux\nbenchmark Chronos", "E9EEF6"),
        ("Sliding windows\ncontexte + horizon", "FFFFFF"),
        ("Chronos base\ngreedy/token top-k", "EAF3FF"),
        ("Branching\nsingle / bundle", "FFF4E6"),
        ("Sampling\ncontinuations", "ECFDF5"),
        ("Quantiles\nq10/q50/q90", "FFFFFF"),
        ("Scores + ranking\nwarnings + figures", "FCEEEF"),
    ]
    x, y = 0.55, 1.75
    for i, (lab, fill) in enumerate(labels):
        pipeline += shape(90 + i, f"Step {i}", x + i * 1.78, y + (0.22 if i % 2 else 0), 1.48, 1.0, lab, fill, "CBD6E2", 980, "18212F", True)
        if i < len(labels) - 1:
            pipeline += arrow(110 + i, x + i * 1.78 + 1.5, y + 0.5 + (0.22 if i % 2 else 0), x + (i + 1) * 1.78 - 0.05, y + 0.5 + (0.22 if (i + 1) % 2 else 0))
    pipeline += shape(130, "Output", 1.0, 4.15, 11.3, 1.3, "Sorties principales : chronos_scan_steps.csv, chronos_scan_summary.csv, chronos_scan_ranking.csv,\nchronos_base_quality_warnings.csv, figures PNG.", "FFFFFF", "DDE6F0", 1250, "18212F")
    slides.append(slide_xml(pipeline))
    slide_images.append([])

    slides.append(slide_xml(
        title("Branching TestÃ©")
        + shape(150, "Single", 0.9, 1.35, 5.55, 1.45, "Mode single\nÃ€ un step donnÃ©, on teste les top-k tokens alternatifs puis on sample la suite.", "EAF3FF", "B7CDFB", 1350, "0D1B2A", True)
        + shape(151, "Bundle", 6.85, 1.35, 5.55, 1.45, "Mode bundle\nToken initial top-5, puis continuation dÃ©terministe top-1 / top-5 / top-10 sur les deux steps suivants.", "FFF4E6", "F3C98B", 1270, "0D1B2A", True)
        + bullet_list(160, 1.1, 3.45, 11.0, [
            "La branche base forcÃ©e sert de rÃ©fÃ©rence distributionnelle plus juste que la seule ligne greedy.",
            "Les tokens spÃ©ciaux sont interdits pendant le dÃ©codage FPA : on ne branche que sur des tokens de valeur Chronos.",
            "Les quantiles rÃ©sument les trajectoires samplÃ©es pour comparer les branches dans l'espace des valeurs rÃ©elles.",
        ], 1400)
    ))
    slide_images.append([])

    slides.append(slide_xml(
        title("RÃ©sultats PrÃ©liminaires", "Trois derniers runs disponibles")
        + table(run_summaries)
        + bullet_list(280, 0.9, 4.0, 11.4, [
            "Les runs produisent bien des rankings de fenÃªtres/branches et des warnings de qualitÃ© de base.",
            "ERCOT domine fortement les plus hauts scores bruts : signal intÃ©ressant, mais visualisation globale dÃ©sÃ©quilibrÃ©e.",
            "Dominick donne des shifts plus faibles; cela peut reflÃ©ter l'Ã©chelle, la dynamique locale ou la performance Chronos.",
        ], 1300)
    ))
    slide_images.append([])

    vis = (
        title("Visualisations", "Ã€ utiliser comme diagnostic, pas encore comme conclusion finale")
        + picture(310, "rId2", 0.75, 1.35, 5.9, 3.0, "Score distribution")
        + picture(311, "rId3", 6.95, 1.35, 5.6, 3.0, "Base quality")
        + bullet_list(320, 0.9, 4.85, 11.5, [
            "Distribution : montre si quelques fenÃªtres dominent tout le score.",
            "QualitÃ© base : prÃ©vient quand Chronos est dÃ©jÃ  loin du ground truth.",
            "ProblÃ¨me actuel : les scores absolus masquent les datasets plus petits quand ERCOT est inclus.",
        ], 1250)
    )
    slides.append(slide_xml(vis))
    slide_images.append([images[0], images[1]])

    slides.append(slide_xml(
        title("Limites ObservÃ©es")
        + bullet_list(340, 0.95, 1.45, 11.2, [
            "ComparabilitÃ© inter-datasets fragile : un score brut dÃ©pend de l'Ã©chelle et de la variance locale.",
            "Un gros shift peut Ãªtre une vraie instabilitÃ©, mais aussi une consÃ©quence d'une prÃ©diction de base mauvaise.",
            "Les sÃ©ries courtes produisent souvent seulement window=0 avec contexte adaptatif, donc biais possible.",
            "Le sampling rend les quantiles plus informatifs, mais demande plus de samples pour stabiliser l'analyse.",
            "Le bundle est coÃ»teux; il faut choisir entre couverture large et profondeur d'analyse.",
        ], 1420)
        + shape(360, "Takeaway", 1.0, 5.45, 11.2, 0.72, "Conclusion prudente : la pipeline dÃ©tecte des zones sensibles, mais la mÃ©trique doit Ãªtre calibrÃ©e avant un discours global.", "FCEEEF", "F3B6C2", 1350, "0D1B2A", True)
    ))
    slide_images.append([])

    slides.append(slide_xml(
        title("Prochaines Ã‰tapes")
        + bullet_list(370, 0.95, 1.35, 11.2, [
            "Normaliser les scores : par Ã©chelle locale, erreur base, variance rÃ©cente ou ratio shift/base_error.",
            "Comparer les rankings par dataset avant de fusionner tous les datasets.",
            "Analyser qualitativement quelques fenÃªtres top-ranked : contexte, ground truth, base forecast, branches.",
            "SÃ©parer les cas : divergence persistante, convergence rapide, explosion d'incertitude.",
            "Ã‰largir progressivement le benchmark une fois les mÃ©triques stabilisÃ©es.",
        ], 1420)
        + shape(390, "Discussion", 1.0, 5.55, 11.2, 0.7, "Questions Ã  discuter : quelle normalisation adopter ? quel type de shift est scientifiquement le plus intÃ©ressant ?", "EAF3FF", "B7CDFB", 1300, "0D1B2A", True)
    ))
    slide_images.append([])

    return slides, slide_images


def create_pptx() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    run_summaries = [summarize_run(path) for path in RUN_DIRS if path.exists()]
    slides, slide_images = build_slides(run_summaries)

    media_entries: dict[Path, str] = {}
    media_counter = 1
    for paths in slide_images:
        for path in paths:
            if path.exists() and path not in media_entries:
                media_entries[path] = f"image{media_counter}.png"
                media_counter += 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types(len(slides), list(media_entries.values())))
        z.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        z.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(slides)))
        for path, xml in static_parts(now, len(slides)).items():
            z.writestr(path, xml)
        for img_path, media_name in media_entries.items():
            z.write(img_path, f"ppt/media/{media_name}")
        for i, slide in enumerate(slides, start=1):
            z.writestr(f"ppt/slides/slide{i}.xml", slide)
            targets = []
            for img in slide_images[i - 1]:
                if img in media_entries:
                    targets.append(media_entries[img])
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", slide_rels(targets))

    print(OUT)


if __name__ == "__main__":
    create_pptx()



