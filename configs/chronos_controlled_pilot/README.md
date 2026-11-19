# Controlled Phase 2 pilot

This is the approved small pilot, not Phase 3 or a benchmark scan. One cached
Chronos mini model runs sequentially on CPU, offline, with one Torch thread.

The reduced seven-group pilot is now complete. See
[the final report](../../docs/CHRONOS_PHASE2.md) for findings, limitations and
the unexecuted Phase 3 proposal. Its final outputs are in `analysis_half/`;
the original one-group `analysis/` snapshot is preserved.

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_controlled_pilot.py
```

Resume with the identical config and original output directory:

```powershell
.\.venv\Scripts\python.exe scripts\runs\run_chronos_controlled_pilot.py --resume-from result\phase2_controlled_pilot_TIMESTAMP
```

`phase2.json` freezes exact series/windows/positions, candidate counts, model
revision, sampling policy, N, seeds, and a four-hour cumulative budget. The first
complete group determines an approximate work-normalized timing estimate; a 1.5
safety factor is used before further groups. No candidate is selected by its new
score. The exchange-rate currency_5 case is a separately labeled stress example.

`context_len` and `horizon` are actual numeric time steps. `top_k` in each case is
the number of candidate tokens including the forced greedy reference, NOT the
continuation truncation `sample_top_k`. Each point additionally samples an
independent same-token control. `nested_sample_counts` and
`probability_thresholds` are offline analyses of the saved ensembles, not more
inference. Twenty paths are the first twenty of fifty, not an independent repeat.

Outputs: a frozen config, context-hashed selection, timing/status progress, and
per-seed atomic `branch_groups/` plus numeric `trajectories/` NPZ/manifests.
Interrupted committed groups are preserved. A changed config/context/model
revision is rejected on resume. CSV exports are rebuilt from validated groups.
The budget is checked between groups, not a forced process kill mid-write.

### Windows checkpoint publication errors

Directory publication retries briefly on Windows access/sharing/lock errors.
A persistent failure preserves the pending directory. If it contains a final
`manifest.json`, ordinary resume stops instead of regenerating that group.
After stopping the worker, explicitly validate and recover the indicated group:

```powershell
.\.venv\Scripts\python.exe -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path('code/chronos_fpa').resolve())); import bootstrap; from checkpoint_store import GroupStore; seed=Path('result/PHASE2_RUN/seed_2718'); GroupStore(seed).recover_pending_group(seed/'branch_groups/.pending-NAME')"
```

Use the exact seed directory and pending name from the error. Recovery validates
checksums, tables, trajectory links, schema and commit order before publication;
it performs no inference. Corrupt or incomplete records are rejected, not repaired.
Then use the normal `--resume-from` command. Do not delete pending research data.

## Reduced seven-group execution

The user subsequently requested half the design for workflow validation.
`half_execution.json` selects exactly seven groups, **including the one already
completed**, without changing model, context, horizon, samples or decoding.
It keeps six ordinary points (three series, b=0/16) at seed 1729 and repeats
ERCOT/EAST b=0 at seed 2718. That repeat runs first on resume. Rare-token stress
cases and other second-seed repeats are deferred, not failed or silently missing.
Total: 1,400 paths and 78,600 suffix coordinates. At amendment approval, 1,200
paths remained to generate. The initial additional estimate was about four hours at the first-group
rate, with substantial hardware/load uncertainty. The operational ceiling is
eight hours cumulative for the reduced run, not an instruction to run longer.

```powershell
.\.venv\Scripts\python.exe -u scripts\runs\run_chronos_controlled_pilot.py `
  --resume-from result\phase2_controlled_pilot_20261116_195533 `
  --execution-plan configs\chronos_controlled_pilot\half_execution.json
```

The original `config.json` stays immutable. The explicit amendment is saved as
`execution_plan.json`; the initial progress snapshot is preserved as
`progress_before_execution_plan.json`. A normal resume automatically reuses
this saved selection and budget, so omitting `--execution-plan` cannot restart
the original fourteen-group design. Completed groups are validated and skipped.
Scientific overrides, duplicate/unknown groups, excluding committed groups,
or changing an already saved amendment are rejected.

After all selected groups complete, offline analysis runs automatically. The
original `analysis/` snapshot is preserved; reduced-run outputs go to
`analysis_half/`. `analysis_status.json` records success/failure separately from
inference completion. Logs capture background execution; `progress.json`
contains the worker PID, current group, selected total, elapsed time and cap.
No Phase 3 starts. Only the first point is replicated, so this reduced pilot
validates execution and offers exploratory comparisons, not general conclusions.

## Offline analysis

```powershell
.\.venv\Scripts\python.exe scripts\viz\analyze_chronos_controlled_pilot.py result\phase2_controlled_pilot_TIMESTAMP
```

The analyzer validates saved array hashes and checks that recomputed N=50
distances match committed summary metrics. It also supports a partial pilot:
missing groups/seeds are not reconstructed or replaced. These files are new
analyses inside this pilot only; no historical outputs are regenerated.

| File in `analysis/` | Contents |
| --- | --- |
| `branch_effects.csv` | Raw/IQR W1, ED, direct jump, same-token controls, probability, entropy, N and exact IDs. |
| `w1_profiles.csv` | Strictly post-fork W1 and same-token W1 at every horizon. |
| `fork_points.csv` | One row per actually available point/seed; not one per alternative. |
| `probability_coverage.csv` | Retained unique alternatives and selection-probability mass at each cutoff, by stratum/dataset. |
| `nested_n_comparison.csv` | Matched N=20/50 estimates from the same saved paths. |
| `seed_stability.csv` | Available repeated-seed estimates; absent seeds stay absent. |
| `descriptive_correlations.csv` | Exploratory pooled/within-series Pearson and Spearman; constant variables are undefined; no IID p-values. |
| `morphology_candidates.csv` | Deterministic role-based selection and figure provenance, not validated motif labels. |
| `analysis_protocol.json` | Observed/planned coverage, conventions, selection rules and limitations. |

W1 averages exact empirical marginal distances over `b+1,...,H-1`. ED is the
trajectory Energy V-statistic using RMS Euclidean distance, without a square
root. Both have original-series units; dividing by historical context IQR makes
them dimensionless. Their numerical magnitudes are not interchangeable.
`*_excess_iqr` is a signed **diagnostic difference** from one same-token control,
not a new distance or bias correction. `*_over_null` is undefined if that control
is zero; exceeding one is not a significance test.

The first-47 columns restrict every suffix to its first 47 downstream steps;
this does not make different conditioning prefixes identical. Legacy composite
columns are retained only on N=50 rows, where they were actually computed.
Per-path endpoint descriptors count `Y[H-1] - Y[b+1] > 0`; they do not identify
trends, peaks, plateaus or establish a change in event probability.

Figures show effects against same-token controls, nested-N comparisons and a
small gallery with **both** ensembles. Faint lines use the first 20 paths;
medians and pointwise q10-q90 bands use all 50. Bands are not simultaneous path
intervals. The gallery selects relatively strong, medium, near-control and
stress examples where available; these labels do not establish significance.

Spearman correlations use Pearson on average ranks, including ties, without a
SciPy dependency. A completed pilot can rerun the analyzer without any model
inference; the normal pilot resume command also retries analysis and updates
`analysis_status.json`.
