# FPA_for_TSFM

Forking Paths Analysis (FPA) for time-series foundation models. The current
research workflow studies token-level branching in original Chronos-T5 models:
force an alternative forecast token, sample continuations, and measure how the
forecast distribution changes.

FPA measures sensitivity to those interventions. It does not directly measure
forecast accuracy or establish a calibrated uncertainty estimate.

## Setup

Use Python 3.11 or newer. From the repository root, with `uv` installed:

```powershell
uv sync --group dev
.\.venv\Scripts\python.exe -m pytest
```

Alternatively, create a virtual environment and install
`requirements-dev.txt` with pip. Dependencies record the versions used in the
existing local research environment. The code uses plain module folders;
there is no research package to install in editable mode.

## Run an experiment

Download benchmark data once:

```powershell
.\.venv\Scripts\python.exe scripts\data\download_chronos_benchmark_datasets.py `
  --output-dir data\raw\chronos_benchmark
```

Then run a small scan:

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_benchmark_scan.py `
  --config configs\chronos_benchmark_scan\smoke.json
```

Inference downloads the selected model on first use. The tests run offline and
use synthetic data and small model doubles.

## Project layout

- `code/chronos_fpa/`: decoding, metrics, pipelines, checkpoints and analysis.
- `scripts/`: experiment launchers, dataset utilities, plots and presentations.
- `configs/`: scan, refinement and controlled-pilot configurations.
- `tests/chronos_fpa/`: offline unit, regression and integration tests.
- `docs/`: mathematical definitions, research findings and historical audits.
- `data/raw/`, `result/`, `presentations/`: local artifacts excluded from Git.

Start with the [workflow guide](README_CHRONOS.md),
[project structure](docs/PROJECT_STRUCTURE.md),
[research notes](docs/recherche/README.md) and [test guide](tests/README.md).

## Repository history

This project began in a TimesFM fork. The independent repository contains the
current Chronos workflow; historical reports may still refer to the earlier
TimesFM experiments. The original workspace remains the archive for that code.
