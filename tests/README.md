# Test Layout

`pytest.ini` limits default discovery to `tests/chronos_fpa`, the offline tests
for the active Chronos research workflow.

- `chronos_fpa/unit/`: deterministic mathematical, windowing, decoding, and
  analysis checks. Probability-threshold tests retain their original assertions.
- `chronos_fpa/regression/`: identifier preservation and grouped plotting bugs,
  checked through data and actual Matplotlib artist coordinates, not screenshots.
- `chronos_fpa/integration/`: local checkpoint and pipeline contracts, using fake
  decoding rather than pretrained models.
- `chronos_fpa/fixtures/`: small checked-in reference cases maintained alongside
  the corresponding tests; generated benchmark outputs are not test inputs.

## Run

From the repository root, using the development environment:

```powershell
uv pip install --python .venv/Scripts/python.exe pytest
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m pytest tests/chronos_fpa/unit
.venv/Scripts/python.exe -m pytest tests/chronos_fpa/regression
```

On other platforms use the environment's `python -m pytest` equivalent.

## Design Rationale

Application tests import plain modules, not newly introduced Python packages.
`chronos_fpa/conftest.py` imports `code/chronos_fpa/bootstrap.py`, which configures
`core`, `data`, `metrics`, `runtime`, `pipeline`, `analysis`, and `visualization`.
It also adds `scripts/viz` and `scripts/runs` for script-level contracts. No
editable install, `src` path change, or production import shim is needed.

The conftest sets Hugging Face offline flags before test-module imports, uses the
headless Agg backend, and automatically rejects socket connections in tests.
No model weights, inference service, network, or external dataset is required.
Small fake models exercise decoder control flow only, not forecast quality.
The session limits Torch CPU operations to one thread for small test doubles and
restores the previous thread count on teardown.

Formula tests use hand-calculated arrays and literal expected results. In
particular, normalized composite scores divide dimensional shifts by their
scale while leaving dimensionless amplification and shape terms unchanged;
dividing the already-combined raw score is intentionally a different diagnostic.
Window tests pin exact-fit and adaptive boundaries. Plot regressions preserve
text identifiers (including numeric-looking strings) and inspect per-dataset
coordinates so accidental grouping or index alignment errors cannot pass merely
because a PNG was written. Floating-point assertions use explicit approximate
comparisons; undefined ratios remain NaN rather than receiving invented zeros.
Peak timing requires a unique absolute maximum: exact ties, including flat laws,
have NaN timing coordinates and `peak_timing_ambiguous=True`. Ties do not change
scalar shift magnitudes or forking scores; nearly equal but distinct peaks remain
uniquely timed.

## API Contracts

Paper 1 adds `unit/test_distances.py` and decoder/pipeline tests: exact empirical
W1 (including unequal sample sizes), RMS-ground Energy V-statistic, independent
same-token streams, strict post-fork slicing, last-token/invalid-IQR cases,
NPZ round-trips and archive integrity, resume equivalence and JSON options.
These tests remain offline and use synthetic models, not cached weights.

The controlled-pilot tests additionally freeze the approved 14-group/3,000-path
budget, exact source-window selection and preservation of textual IDs. Offline
pilot-analysis checks use independently known constant-shift W1/ED values,
zero-control handling, first-20-within-50 slicing, and duplicate-free example
selection even for a partial run. They never launch the pretrained pilot.
Reduced-execution tests reject scientific overrides/unknown or duplicate groups,
freeze the seven-group scope, and exercise interruption -> reduced resume ->
analysis. They verify that the completed ensemble is not regenerated, the base
config and initial analysis remain unchanged, and subsequent resumes reuse the
saved subset without loading a model when already complete.

Phase 3 Deliverable A adds `unit/test_phase3_controls.py`: whole-path permutation
statistics checked against hand-calculated and existing W1/ED answers, plus-one
p-values with ties, Holm adjustment, paired-reference subsampling, signed
alternative/temporal contrasts, OLS/endpoint descriptors, Wilson boundaries and
multi-fork file processing without changing its sources. These are offline
statistical checks, not pretrained inference or an automatic morphology detector.

- `chronos_analysis`: `analyze_chronos_token_branches`,
  `analyze_chronos_named_branches`, `summarize_chronos_branches`, and
  `summarize_chronos_named_branches` retain their existing dictionary/DataFrame APIs.
- `chronos_data`: `SeriesRecord`, `WindowRecord`, and `iter_sliding_windows` retain
  the signatures extracted from `chronos_benchmark_scan`.
- `chronos_scales`: `compute_base_forecast_quality`,
  `_attach_normalized_branch_scores`, `_attach_temporal_forking_scores`, and
  `resolve_score_column` retain the extracted signatures. Score selection defaults
  to context IQR and rejects missing or entirely undefined defaults; other scales
  require explicit selection. Tests address helpers at their new module boundary,
  not through the pipeline.
- `chronos_scan_visualization`: `_prepare_summary_df` must preserve identity
  columns while coercing metric columns. Grouped plots must retain each window's
  series identity and pair coordinates from the same rows.

Regression tests assert the desired behavior without xfail markers. A failure
should be reported to the production owner, not hidden by changing the oracle
or making unrelated production edits from this test-only task.
