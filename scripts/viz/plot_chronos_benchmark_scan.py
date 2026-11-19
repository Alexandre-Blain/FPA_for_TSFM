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

from chronos_scan_visualization import plot_chronos_scan_outputs


def run():
    parser = argparse.ArgumentParser(
        description="Generate PNG figures from Chronos benchmark scan CSV outputs."
    )
    parser.add_argument("run_dir", help="Directory containing chronos_scan_*.csv files.")
    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument(
        "--score-column",
        default="",
        help=(
            "Score column used in figures. Default prefers "
            "context_iqr_scaled_progressive_token_bin_forking_score, then falls back."
        ),
    )
    args = parser.parse_args()

    paths = plot_chronos_scan_outputs(
        args.run_dir,
        top_n=args.top_n,
        score_col=args.score_column or None,
    )
    if not paths:
        print("No figures generated; scan CSVs may be empty or missing.")
        return

    print("Saved figures:")
    for path in paths:
        print(f"- {path}")


if __name__ == "__main__":
    run()



