# Project Structure

This repository is organized as a research workspace, not as a dedicated
installable Python package.

## Main Folders

```text
code/
  chronos_fpa/
    bootstrap.py       Import paths for plain modules, no installation.
    core/              Chronos tokenizer and autoregressive decoding.
    data/              Local series readers and sliding windows.
    metrics/           Mathematical definitions, shared score and scaling.
    pipeline/          Per-window branching orchestration.
    runtime/           Configuration, strict CSV contracts, atomic checkpoints.
    analysis/          Uncertainty and scenario studies.
    visualization/     Plotting and visual diagnostics.

scripts/
  data/                 Dataset download/export utilities.
  runs/                 Main experiment launchers.
  viz/                  Plotting utilities for existing runs.
  presentations/        PowerPoint generation scripts.
  maintenance/          Research audit and disposable ChatGPT handout refresh.

configs/
  chronos_local_pilot/     Frozen six-series / ten-cell pilot configuration.
  chronos_microbenchmark/  Dated opt-in single-context Prompt 2 configuration.
  chronos_benchmark_scan/
  chronos_targeted_refinement/

data/
  raw/
    chronos_benchmark/  Local Chronos benchmark exports.

result/                 Research outputs. Kept as-is for traceability.
docs/                   Metrics, math audit, figure guide, research notes.
presentations/          Generated decks and visual assets.
tests/chronos_fpa/       Offline unit, integration and regression tests.
```

## Current Chronos Commands

Main scan:

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_benchmark_scan.py `
  --config configs\chronos_benchmark_scan\default.json
```

Targeted refinement:

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_targeted_refinement.py `
  --config configs\chronos_targeted_refinement\default.json
```

Plot existing run:

```powershell
.\.venv\Scripts\python.exe scripts\viz\plot_chronos_benchmark_scan.py `
  result\RUN_NAME
```

Download Chronos benchmark exports:

```powershell
uv run --no-project --with datasets python scripts\data\download_chronos_benchmark_datasets.py `
  --output-dir data\raw\chronos_benchmark
```

## Bounded exploratory prototype

Prompt 2 adds `scripts/runs/run_chronos_microbenchmark.py`, with
`core/chronos_exploratory.py`, `metrics/chronos_outcomes.py`,
`pipeline/chronos_exploratory_window.py`, `runtime/ensemble_store.py`
and native `runtime/windows_job.py`. It is separate from historical launchers.
The [benchmark report](BENCHMARK_REPORT.md) records its dated resource
authorization and measured limits; the configuration is not permanent
permission to repeat inference. The [current handoff](../research/FPA_HANDOFF.md)
is mirrored into ignored `docs/chatgpt-handout/` at each completed prompt.

## Import Rule

The local multi-series pilot uses `scripts/runs/run_chronos_local_pilot.py`:
`data/chronos_pilot_selection.py` freezes context-only selection,
`pipeline/chronos_pilot_validation.py` checks immutable complete cells, and
`metrics/chronos_pilot_uncertainty.py` calculates conditional Monte Carlo
bounds and reuse covariance. Analysis is separate in
`scripts/viz/analyze_chronos_local_pilot.py`; it loads no forecasting model.
The subsequent offline scientific review uses
`scripts/viz/analyze_chronos_pilot_offline.py` and
`analysis/chronos_offline_precision.py`. It reads saved complete paths only and
writes into its own named pilot subdirectory; see the
[current analysis report](LOCAL_PILOT_OFFLINE_ANALYSIS.md).
The current authorization and completion state are in the
[handoff](../research/FPA_HANDOFF.md), not inferred from launcher availability.

Chronos scripts add `code/chronos_fpa` then import `bootstrap`, which configures
the functional module folders. No `__init__.py`, editable install or research
package is required. Tests use the same bootstrap. Earlier TimesFM code remains
in the original workspace, outside this independent repository.

## Historical Code References

Earlier research reports may name files directly under `code/chronos_fpa/`.
They now live under these functional subfolders (filenames stay recognizable):

| Historical modules | Current folder |
| --- | --- |
| chronos_decoding, chronos_io | core/ |
| chronos_analysis | metrics/ |
| chronos_benchmark_scan | pipeline/ |
| chronos_scan_visualization, chronos_plotting | visualization/ |
| chronos_uncertainty_alignment, chronos_scenario_sensitivity, chronos_analysis_helpers | analysis/ |
| results_io, run_config | runtime/ |

Window/data handling was extracted into `data/chronos_data.py`; scaling and
shared equations into `metrics/chronos_scales.py` and `metrics/chronos_score.py`.
The new `runtime/checkpoint_store.py` owns atomic group records. Historical
reports and archived source copies remain historical evidence, not descriptions
of the new checkpoint format.
