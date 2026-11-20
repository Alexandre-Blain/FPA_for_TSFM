# Research Maintenance Report

## Scope

The research inventory is read-only. Existing `result/`, `data/` and
`presentations/` are not edited, repaired, moved or regenerated. New inventory
documents are written under `docs/maintenance/`.

## Cleanup Delivered

- Research code remains plain modules, not an installable package. Functional
  folders separate decoding/tokenization, data/windowing, mathematics, runtime,
  pipeline, analysis and plotting; `bootstrap.py` centralizes their import paths.
- Shared branch components, score weights and normalized-score formulas replace
  duplicate implementations. Local CSV readers preserve text identifiers and
  reject both short and long malformed records instead of dropping observations.
- New runs publish validated steps/summary/RNG records atomically per completed
  group. CSV exports are reconstructible; checksums detect corruption. Resume
  restores saved settings and random state after model loading, rejects changed
  scientific settings, preserves initial configs and freezes refinement targets.
- Parent scan resumes the original automatic refinement instead of creating a
  duplicate run. Resolved errors stay logged without blocking completion.
- Analyses use an explicit common normalization, default context IQR. Scenario
  thresholds and their FPA score must share that choice. Invalid scales and
  non-unique extrema timings remain undefined, with counts/exclusions recorded.
- Uncertainty studies expose branch and branch-point correlations separately.
  Dimensional comparison metrics follow the selected score scale; percentile
  indices are frozen before base filtering. These are descriptive conventions,
  not claims of independent samples or calibrated uncertainty.
- Upstream tests were moved intact out of the default Chronos suite. Unit,
  integration and regression tests use independent numerical examples, small
  frozen cases, toy models and temporary directories. No pretrained weights or
  network are used. The obsolete root test-package marker was removed.
- The practical Chronos guide was shortened substantially, with parameter
  details kept in the config READMEs. Active docs, commands and module paths
  were updated; the refinement default now points to the clean reference scan.
- No experiment, historical archive, presentation, data export, or historical
  analysis was deleted. Only regenerable Python caches are eligible for purge.
  The attempted source/test cache purge was rejected by the execution tool's
  deletion policy; those caches were left in place and are ignored by Git.
  No alternative deletion mechanism was used.

## Behavior Changes And Boundaries

Score equations/coefficients are unchanged (`chronos_fpa_context_iqr_v1`).
New metric conventions are `chronos_fpa_metrics_v2_explicit_scale`; analysis
conventions are `2.0-explicit-scale`, and atomic-store schema is version 2.
Base-quality alerts now use greedy MAE / context IQR, not historical window_scale.
Law-peak and scenario-peak/trough timings are undefined for exact ties. Default
score selection no longer falls back silently to a different normalization.

Historical CSV-only runs are deliberately not migrated or resumed in place.
They remain evidence and can be audited with explicit recovery, or used as the
source of a separate new refinement when the chosen score is available.
Scenario and probability-threshold analyses currently support single-token
branches; bundle decoding, scoring, storage and general plotting remain supported.

The checkpoint tests simulate interruption and verify stochastic continuation
equivalence on CPU. They do not certify physical disk durability under every
power-loss/filesystem failure or numerical equivalence across different hardware.

## Scientific Limits

- A partial run may contain useful observations. Incomplete does not mean useless.
- Coverage, export integrity and completion are independent assessments. A
  checkpoint claiming completion is evidence, not a substitute for paired tables.
- Overall labels are `completed`, `partial`, `inconsistent`, `indeterminate`.
  Export integrity uses `consistent`, `inconsistent`, `indeterminate`.
- Current data identifiers and window bounds do not establish the provenance of
  historical source data, predictive validity, causality or reproducibility.
- Recorded input defaults are not proof of the effective command-line settings.
  Missing effective settings leave completion indeterminate when needed.
- Historical figures have a **potential** `series_id` numeric-conversion risk.
  Verify individual figures against source identifiers and generation provenance;
  there is no blanket claim that historical figures are incorrect.
- No pretrained inference, existing-analysis regeneration or historical figure
  regeneration was performed. Numerical findings were reproduced read-only for
  regression checks, not replaced by newly generated experimental outputs.
- `branch_groups/` is pruned during run discovery and table validation. A store's
  committed records are not certified by this export-only inventory. Optional
  preservation hashes still cover all files there.

## Audit And Preservation

Run from the repository root using Python 3.10 or later:

```powershell
.\.venv\Scripts\python.exe scripts/maintenance/audit_research_runs.py --snapshot --benchmark-folder data/raw/chronos_benchmark
```

The explicit benchmark-folder override compares historical references with the
current local export; it is recorded in every run's evidence. Without it, only
the recorded folder is used, with unavailable data reported as indeterminate.
No identifiers or data validity are inferred from directory names.

Outputs default to a new timestamped directory under `docs/maintenance/`:

- `report.md`: readable inventory with separate status columns and caveats.
- `audit.json`: structured evidence, window/branch differences, rejected CSV
  counts and physical ending line numbers. Smaller CSVs use the shared strict
  `research_schema.read_csv(..., recover=True)` audit view only; step CSVs use
  strict streaming `csv` validation, retaining branch/step bitmaps instead of
  loading full tables. Rejected source records are never edited.
- `inventory_before.json` and `.csv`, `inventory_after.json` and `.csv`:
  optional complete `result/` and `data/` inventory with paths, byte sizes,
  UTC mtime, mtime nanoseconds and chunked SHA-256. The audit checks preservation
  across its own execution. Files changed by another process are reported, not
  silently accepted. Directory links are not traversed.

After code cleanup, verify the saved **JSON** baseline (which also retains
snapshot errors) and append the resulting report location here:

```powershell
.\.venv\Scripts\python.exe scripts/maintenance/audit_research_runs.py --verify-manifest docs/maintenance/<audit-directory>/inventory_before.json --benchmark-folder data/raw/chronos_benchmark
```

A preservation mismatch exits with code 2. Research anomalies are report
findings, not command failures. No hash verification proves scientific validity.

## Evidence

- Initial [audit report](audit_20261116T130047_219742Z/report.md) and
  [structured inventory](audit_20261116T130047_219742Z/audit.json): 17 runs;
  15 completed, 1 partial, 1 inconsistent. These labels describe the inspected
  scope, not scientific usefulness.
- [Before JSON manifest](audit_20261116T130047_219742Z/inventory_before.json),
  [before CSV manifest](audit_20261116T130047_219742Z/inventory_before.csv),
  [after JSON manifest](audit_20261116T130047_219742Z/inventory_after.json),
  [after CSV manifest](audit_20261116T130047_219742Z/inventory_after.csv):
  680 files, including 672 result files and 8 data files. SHA-256, size and
  mtime preservation passed across the audit, with no additions or removals.
- `refinement_faster_global_20260728_125930`: 45 ragged summary records at
  physical lines 1472-1516 were reported without editing them; 45 step branches
  lack accepted summary counterparts. Six observed windows are outside the
  selected targets. Integrity is inconsistent, while completion is partial.
- Post-cleanup [verification report](audit_20261116T131315_989918Z/report.md) and
  [machine-readable evidence](audit_20261116T131315_989918Z/audit.json) confirm all
  680 result/data files match the initial manifest: content, size and mtimes.
- Final complete offline suite: **160 tests passed**. Command:
  `python -m pytest -q`, with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` for an isolated
  run. Normal plugin discovery previously passed too; the installed third-party
  anyio pytest plugin emits a deprecation warning unrelated to FPA.
- CLI scan/refinement config+help checks and compilation of research code,
  scripts and tests passed without model loading.
- Reintroduced the identifier-conversion bug in memory: both targeted text-ID
  regressions failed as expected. Reintroduced the erroneous raw-score/scale
  normalization in memory: the independent 2.45-versus-2.275 oracle failed as
  expected. No production source was edited for these mutation checks.
- All eight normalized score families reproduce the original expression
  **bit-for-bit on the 1,260 reference rows**. Compared with serialized CSVs,
  maximum absolute roundoff is 7.383e-15 for the primary IQR score, 1.365e-12
  across all normalized variants, and 1.137e-13 for the raw score.
- Probability-cutoff coverage is unchanged: alternatives 1008/951/793/621,
  branch points 252/252/237/231, windows 63/63/61/58 for cutoffs
  0/.001/.01/.05. Corresponding entropy/FPA Spearman coefficients reproduce
  -0.182065/-0.160703/-0.086176/-0.092232.
- Historical figure review: not performed; potential risk recorded only.

## Validation Gates

- [x] Focused audit regression results included in the full offline suite.
- [x] Initial result/data SHA-256 preservation manifests recorded.
- [x] Final test commands, outcomes and exact totals appended.
- [x] Saved baseline verified after code cleanup without result/data changes.
- [x] Scientific limitations and unresolved evidence gaps retained.
