# Paper 1: Strict-Suffix Distances And Numeric Ensembles

Active specifications: [research plan](<future works/FPA_CHRONOS_RESEARCH_PLAN (1).md>)
and [Phase 1 prompt](<future works/CODEX_PHASE_PROMPTS (1).md>).
Implementation stops at Phase 1. No benchmark scan or Phase 2 pilot is launched.

## Enable In A New Run

Add these keys to the existing scan or standalone refinement JSON `parameters`:

```json
{
  "branch_modes": "single",
  "trajectory_metrics": true,
  "save_trajectories": true,
  "sampling_seed": 123,
  "temperature": 1.0,
  "sample_top_k": 50
}
```

This snippet is not an approved experiment budget. CLI equivalents are
`--trajectory-metrics`, `--save-trajectories`, `--sampling-seed 123`.
Defaults are false, false and 0. Saving implies trajectory metrics, which always
add one independent same-token reference ensemble per fork. These options pass
to automatic refinement. Bundles are explicitly rejected in this mode.

Resume a new-format run with `--resume-from <run-folder>`. Feature options,
seeds and sampling settings cannot change during resume. Completed groups reuse
their archives; archive integrity is checked before commit/recovery. CSV-only
historical runs are not migrated, repaired or overwritten.

## Formulas And Units

Reference and alternative ensembles have shapes `[n,H]` and `[m,H]`, sharing
the greedy prefix before b. The reference forces the greedy token at b and
samples the remainder just like the alternatives.

- Direct jump: `J = abs(reference[0,b] - alternative[0,b])`.
- Strict suffixes: `A = reference[:,b+1:]`, `B = alternative[:,b+1:]`.
- Length: `L = H-b-1`, recorded on each summary row.
- For equal sample sizes, exact empirical marginal
  `W1_h = mean(abs(sort(A[:,h]) - sort(B[:,h])))`.
- Unequal sample sizes use the exact common empirical inverse-CDF grid.
- `w1_post = mean(W1_h)`.
- Ground distance: `rho(a,b) = norm(a-b,2)/sqrt(L)`.
- `ed_post = 2*mean_ij rho(A_i,B_j) - mean_ij rho(A_i,A_j)
  - mean_ij rho(B_i,B_j)`, including within-sample diagonal pairs.

ED is the Energy **V-statistic functional**, not its square root. Only small
negative floating-point roundoff is clamped to zero; a larger negative result
raises an error. W1 and ED use exactly the same samples. Both raw metrics have
the series' numeric unit. ED sees marginal and inter-horizon differences: it
is not a pure dependence-change measure. RMS scaling does not remove all
scientific differences between positions with different remaining horizons.

Normalized outputs divide raw W1, ED and J by the historical-context IQR.
Finite context observations and NumPy's linear quantiles define the IQR.
Nonfinite IQR or IQR <= `1e-12` makes normalized values NaN with an explicit
flag/reason; raw outputs remain available. No GT or alternate scale is used.

At b=H-1, J remains valid, suffix arrays have shape `[n,0]`, the W1 profile
is empty, and scalar downstream distances are NaN, not zero. Prefix equality
and constant forced coordinates are validated.

## CSV Additions And Null Control

Summary additions: `distance_version`, `post_fork_length`, `post_fork_defined`,
`distance_context_iqr`, `distance_context_iqr_valid`,
`distance_scale_invalid_reason`, `direct_token_jump`, `w1_post`, `ed_post`, and
their `_over_context_iqr` versions.

`same_token_null_w1_post` and `same_token_null_ed_post` (plus normalized
versions) compare the reference to a **second independent ensemble with the
same forced reference token**. One null is shared within each fork. It is a
noise-floor observation, not a significance threshold. The base row's ordinary
self-distance is zero and is NOT this independent null control.

Step additions: `w1_post_h`, `same_token_null_w1_post_h` and their
`_over_context_iqr` versions, aligned to absolute forecast_step. These are NaN
at and before b. Historical `law_shift_h` and composite formulas do not change.

`token_probability` keeps the existing selection softmax definition.
`token_sampling_probability` separately reports probability at the fork under
the temperature/top-k policy; a forced candidate may have zero policy support.
Top-k sampling retains ties at its logit threshold, and specials/EOS/PAD are
excluded. The conditional suffix law is this actual decoder policy, not an
assumed untruncated model law.

Device-local Torch generators use SHA256-derived seeds for root seed, window
identity/context hash, position and token/role. The null has a separate role.
Summary CSVs record stream IDs; manifests record derived seeds. Sampling does
not consume the global RNG. Candidate ordering and resume do not change a
stream. Hardware/Torch-version changes need not be bitwise reproducible.

## Raw Archive Schema

```text
<new-run>/trajectory_protocol.json
<new-run>/trajectories/<fork-id>/manifest.json
<new-run>/trajectories/<fork-id>/ensembles.npz
```

The run protocol records seed/policy/software/source provenance even when raw
saving is disabled. The optional pickle-free numeric archive contains:

```text
context                 [context_length] float32
greedy_prefix_tokens    [b]              int64
greedy_prefix_values    [b]              float32
token_<reference-id>    [N,L]            float32
token_<alternative-id>  [N,L]            float32  (each candidate)
same_token_null         [N,L]            float32
```

The reference is stored once. Coordinate b is excluded from suffix arrays;
its forced numeric values are recorded in metadata. `trajectory_manifest`
provides a run-relative CSV link. `load_fork_ensembles(path)` validates array
keys, shapes, dtypes and hashes. Atomic publication precedes the existing group
checkpoint; `.pending-*` directories are uncommitted. A conflicting published
archive is rejected, never silently overwritten.

Manifest contents: window/source/series IDs, stored context and hash, H/b/L,
candidate IDs/ranks/decoded values, p_sel and sampling probabilities, entropy
and candidate mass, IQR/invalid-scale flags, tokenizer scale/config, decoder
settings, model ID/revision when available, sample counts, RNG streams/seeds,
array paths/descriptions, software versions and source-code hashes. Git HEAD
alone does not identify untracked research code, so hashes are included.
Unavailable model revision is explicit null.

Old CSVs cannot reconstruct these samples or exact distances. With the feature
disabled, the legacy sampling path, score definitions and CSV schemas remain.
Enabling explicit RNG streams changes random realizations, not old formulas.
Existing graphics/rankings keep their historical default score. Dedicated
unit-aware W1/ED figures and morphology interpretation are not part of Phase 1;
old normalized-score figures are not automatically new-distance figures.

## Verification Performed

Verified: deterministic W1/ED examples, unequal sample counts, same marginals
with different path pairings, direct/post-fork separation, undefined empty
suffixes, invalid IQR, distinct reproducible RNG streams, archive round-trips,
corrupt/missing archive rejection, interruption/resume parity, JSON options
and automatic refinement propagation. All pretrained inference is excluded
from the default test suite.

Final offline suite: **191 passed**, no failures (one unrelated AnyIO/Pytest
deprecation warning). The pre-change suite contained 160 tests. A separate
parity check reproduced the previous decoder's exact sampled token IDs for
12 temperature/top-k combinations with a fixed global RNG seed, feature off.
The clean September summary SHA256 remains
`04a41da4b55ed353986796c1378ede65abe4d269e20a520ea2f344c75c75021e`.
The repository-wide `git diff --check` reports a pre-existing trailing blank
line in root `README.md` (not edited in Phase 1); it is not a test failure.

A separate cached-model CPU smoke used revision
`bd6a4fde8403b8469acd0abd52852b29dbe61c7b`, H=4, b=1, N=3, two candidates
plus one same-token control. Offline flags prevented downloading; no benchmark
data or result directory was used. Load time was 52.8 s; decoding plus metrics
0.67 s. It checks execution, not forecast quality or metric reliability.

For synthetic L=63 samples, median W1+ED calculation times over ten repetitions
were 1.24 ms (N=20), 5.20 ms (N=50), 11.13 ms (N=100), on the current host.
These are metric-only timings, not inference-speed or optimization claims.

## Proposed Phase 2 Pilot (Not Run)

Proposed: one original series from each domain (ERCOT, Exchange Rate, M4 Daily),
one full-context window per series, b=0 and b=16, reference plus ranks 2 and 3,
and one independent same-token ensemble. Choose windows from existing context,
likelihood and numeric-jump descriptors, not just old score maxima. Exclude
currency_5's extreme from the representative pool; label and separately budget
any improbable stress case.

Two root seeds and N=50 give 6 points x 4 ensembles x 2 seeds x 50 = 2,400
paths, or 132,000 strictly downstream values at H=64: 528,000 uncompressed
float32 bytes, plus contexts/metadata. Compare N=20 and N=50 with predefined
nested subsets of saved samples; subsets are not independent replications.
Defer N=100 unless reliability requires it. Two null realizations per point
do not constitute a calibrated null distribution or confirmatory study.

Compute: at most 132,000 sampled downstream token decisions, plus greedy
references/selection. The null adds one of four ensembles (33% more sampled
paths than three candidate ensembles). CPU wall-clock cost must be measured
on the chosen hardware; tiny smoke timing is not a reliable full-context
runtime estimate. Approve the concrete series/windows and budget before Phase 2.

## Changed Files

| File | Reason |
| --- | --- |
| `code/chronos_fpa/metrics/chronos_distances.py` | Exact W1, RMS-ground Energy V-statistic, direct/strict-suffix metrics and normalization. |
| `code/chronos_fpa/core/chronos_decoding.py` | Local RNG streams, independent same-token sampling and separate sampling-policy probabilities. |
| `code/chronos_fpa/runtime/trajectory_export.py` | Opt-in options, numeric NPZ archives, validated manifests and provenance. |
| `code/chronos_fpa/runtime/checkpoint_store.py` | Reject missing, altered or misidentified trajectory archives before commit/recovery. |
| `code/chronos_fpa/pipeline/chronos_benchmark_scan.py` | Attach new metrics and optional exports without replacing historical scores. |
| `scripts/runs/run_chronos_benchmark_scan.py` | JSON/CLI options, resume and automatic-refinement propagation. |
| `scripts/runs/run_chronos_targeted_refinement.py` | Same options for standalone refinement. |
| `tests/chronos_fpa/unit/test_distances.py` | Independent mathematical oracles and edge cases. |
| `tests/chronos_fpa/unit/test_decoding.py` | Independent reproducible RNG and probability definitions, forced-base inclusion. |
| `tests/chronos_fpa/integration/test_pipeline.py` | Serialization, integrity, interruption/retry, resume, JSON and refinement coverage. |
| `tests/README.md` | Describe added test coverage. |
| `README_CHRONOS.md` | Link to this practical guide. |
| `configs/chronos_benchmark_scan/README.md` | Explain three optional configuration keys. |
| `configs/chronos_targeted_refinement/README.md` | Explain the same keys for refinement. |
| `docs/CHRONOS_METRICS.md` | Distinguish new exact distances from historical metrics. |
| `docs/CHRONOS_PHASE1.md` | Formulas, schema, verification and bounded unexecuted pilot proposal. |
