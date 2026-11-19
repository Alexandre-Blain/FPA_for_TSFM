from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CHRONOS_CODE = ROOT / "code" / "chronos_fpa"
for path in (CHRONOS_CODE, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import bootstrap

from chronos_plotting import plot_chronos_all_outputs


def main():
    parser = argparse.ArgumentParser(description="Generate PNG figures from Chronos token-bin FPA CSV outputs.")
    parser.add_argument("run_dir", help="Directory containing chronos_predictions.csv and branch CSV outputs.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    predictions_df = pd.read_csv(run_dir / "chronos_predictions.csv")
    step_df = pd.read_csv(run_dir / "chronos_token_branch_steps.csv")
    summary_df = pd.read_csv(run_dir / "chronos_token_branch_summary.csv")
    alternatives_df = pd.read_csv(run_dir / "chronos_token_alternatives.csv")

    paths = plot_chronos_all_outputs(
        run_dir=run_dir,
        predictions_df=predictions_df,
        step_df=step_df,
        summary_df=summary_df,
        alternatives_df=alternatives_df,
    )

    print("Saved figures:")
    for path in paths:
        print(f"- {path}")


if __name__ == "__main__":
    main()



