from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHRONOS_CODE = ROOT / "code" / "chronos_fpa"
for path in (CHRONOS_CODE, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import bootstrap

from chronos_uncertainty_alignment import analyze_run_uncertainty_alignment


def run() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Offline analysis of Chronos internal uncertainty metrics versus "
            "FPA branch sensitivity metrics."
        )
    )
    parser.add_argument(
        "run_dirs",
        nargs="+",
        help="One or more result folders containing chronos_scan_summary.csv.",
    )
    parser.add_argument(
        "--score-column",
        default="",
        help=(
            "FPA score column used as the main y-axis. Empty follows the "
            "standard fallback order, starting with context_iqr when present."
        ),
    )
    parser.add_argument(
        "--output-subdir",
        default="recherche/model_uncertainty_alignment",
        help="Subfolder written inside each run directory.",
    )
    parser.add_argument("--top-n", type=int, default=40)
    args = parser.parse_args()

    for run_dir in args.run_dirs:
        outputs = analyze_run_uncertainty_alignment(
            run_dir,
            score_col=args.score_column or None,
            output_subdir=args.output_subdir,
            top_n=args.top_n,
        )
        print(f"\nSaved uncertainty alignment analysis to: {outputs.output_dir}")
        print("CSV/JSON outputs:")
        for path in outputs.csv_paths:
            print(f"- {path}")
        print("Figures:")
        for path in outputs.figure_paths:
            print(f"- {path}")
        if outputs.warnings:
            print("Warnings:")
            for warning in outputs.warnings:
                print(f"- {warning}")


if __name__ == "__main__":
    run()
