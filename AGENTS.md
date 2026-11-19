# FPA_for_TSFM - Agent Entry Point

This is a research workspace for Forking Paths Analysis of time-series
foundation models. The active implementation uses original Chronos-T5 models.

Read `README.md`, `README_CHRONOS.md`, `docs/PROJECT_STRUCTURE.md` and
`tests/README.md` before changing the workflow.

## Layout

Research modules live in `code/chronos_fpa/`, organized by function. Scripts
import `bootstrap.py` to configure these plain module folders. Do not introduce
an installable research package just to resolve imports.

Experiments use JSON configurations in `configs/` and launchers in
`scripts/runs/`. Analysis and plotting utilities are in `scripts/viz/`.

## Validation

Install the development environment with `uv sync --group dev`, then run:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Tests are offline: no model downloads or inference runs are needed.

## Research artifacts

Preserve existing datasets, run outputs, checkpoints and historical reports.
Partial runs may contain useful evidence. Keep generated artifacts out of Git
and do not rewrite historical outputs as a side effect of source maintenance.

There is no TimesFM library or forecasting skill in the active repository.
Earlier TimesFM code is archived in the original workspace.
