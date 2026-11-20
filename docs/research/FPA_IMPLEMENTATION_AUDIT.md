# Implementation and checkpoint audit — 2026-11-19

**Observed** means inspected code or validated local artifacts, not new model
execution. **Suggested** means an unimplemented design or test.
**Hypothesis** means a scientific interpretation awaiting evidence.
See the [integration report](FPA_INTEGRATION_REPORT.md) and
[machine-readable evidence](FPA_INTEGRATION_EVIDENCE.json).

## Evidence and limits

**Observed:** branch `main`, starting HEAD
`687c34f5f144476ea530c4210d3ed294c3b543e9`. The initial worktree was clean.
Read the existing entry-point guides, all supplied proposal documents,
[Phase 1](../CHRONOS_PHASE1.md), [Phase 2](../CHRONOS_PHASE2.md),
[Phase 3](../CHRONOS_PHASE3_DESIGN.md), and the
[historical plan](<../future works/FPA_CHRONOS_RESEARCH_PLAN (1).md>).
No historical report, executable source, configuration, dataset or run was edited.

**Observed:** a standard-library check validated seven Phase 2 group table/RNG
checksums and row counts, seven NPZ archives, and 49 array shape/dtype/payload
checksums. These contain 1,400 paths, 78,600 strict-suffix coordinates and 78,497
compressed NPZ bytes. Eighteen input hashes recorded in the Phase 3 protocol
match this checkout's Phase 2 files. Its analyzer and distance-source hashes
also match. These are integrity checks, not recomputed W1/ED or statistical tests.

**Observed:** Phase 2 uses C512/H64/N50, three original series, six distinct
fork points and seven point/seed groups. The saved reduced execution plan,
not the original fourteen-group proposal, defines completion. Stage A's
M4/T000001 b0 seed2718 group is absent from that completed plan and artifact
inventory. Phase 3's protocol explicitly says offline analysis only; its old
absolute `source_run` points to the former workspace. Relative input hashes
resolve here without changing that historical protocol.

**Observed (source reports):** M4's selected asymmetry, ERCOT's selected temporal
localization, near-null alternatives, unstable rankings and entropy confounding
remain exploratory findings. Their statistics were read, not regenerated.
**Hypothesis:** generality beyond those selected cases remains unestablished.

## Feasibility and missing implementation

| Area | Observed code behavior | Suggested gate before collection |
| --- | --- | --- |
| C512/H32, b0..9, N20 | Decoder accepts positive H/N; pipeline takes window H and supplied branch positions. Existing pilot config is H64/N50; scan smoke is H64/N5. Invalid branch positions are silently skipped by `scan_window`. | Freeze a new grid; reject missing/invalid positions; assert ten groups and strict suffix lengths 31..22 without touching old configs. |
| Candidate probabilities | `top_k_tokens_at_step` selects fixed K under untruncated valid-token softmax `p_sel`; separately returns sampling-policy probabilities when trajectory RNG is enabled. | Test q50-ranked cumulative coverage >=.90 or cap8, greedy membership, ties and residual coverage. No current 90% rule exists. |
| Effective q50 | `_sampling_logits` masks special tokens, applies temperature and a kth-logit threshold. All ties survive, so support can exceed 50. There is no top-p truncation. | Preserve that law, finite-mask behavior and ties; store complete support and both p_sel/q50. Do not silently replace threshold ties with exactly 50 IDs. |
| Residual and null | Independent same-token null and per-token/role SHA256 RNG streams exist. No residual conditional-first-token sampler exists. | Verify residual first-token support excludes selected IDs, mass sums to one, later draws use ordinary q50, and streams are distinct. |
| W1/ED and J | Exact empirical W1, unequal-size handling, RMS-ground Energy V-statistic, b+1 slicing, full-suffix outputs and invalid-IQR NaNs exist. Current direct jump is absolute. | Add separately named signed J and fixed22/full outputs; test known arrays and b9/H32 boundary. Preserve existing formulas and IQR <=1e-12 behavior pending an explicit alternative. |
| P0..15 CPD | No weighted outcome-mixture/direct-CPD driver or CPD inference implementation found. Low-level decoding can force a greedy prefix, which alone does not implement CPD. | Synthetic weighted-law tests; reconstruct the same Y31/last8 outcomes for every t; P10 reuse identity; direct P11..15 N60; overlap/variance calibration across estimator boundaries. |
| Conditioning/caching | Every `_next_token_logits` call passes the context and complete accumulated decoder prefix with `use_cache=False`. Forced tokens are appended before later logits. Encoder work repeats; the greedy path is rebuilt per fork. Samples are already batched within an ensemble. | Benchmark encoder reuse, immutable/copy-safe prefix KV states and batch sizes against reference per-step logits/q50; ensure every previous generated token conditions later steps. |
| White-box/replay | No output-hidden-state/attention capture. Branch token paths exist in memory; NPZ stores numeric suffixes, context and greedy prefix only. Null tokens and full greedy future are not persisted. | Persist full aligned token paths and frozen greedy outcomes; benchmark every layer/head, logits and encoder/decoder/cross-attention, plus deterministic replay parity. Numeric suffixes alone do not establish token replay. |
| Model/device | Raw loader calls `from_pretrained(model_id)` without a revision/local-only argument, chooses device and calls `eval()`. Pilot forces CPU and checks revision after loading. Decoding has `no_grad`. | Enforce offline, pinned loading before any future model operation; record dtype/backend and measured CPU/GPU behavior. A config revision is not a pre-load pin. |

Sources: [decoder](../../code/chronos_fpa/core/chronos_decoding.py),
[loader](../../code/chronos_fpa/core/chronos_io.py),
[distances](../../code/chronos_fpa/metrics/chronos_distances.py),
[pipeline](../../code/chronos_fpa/pipeline/chronos_benchmark_scan.py),
[archive writer](../../code/chronos_fpa/runtime/trajectory_export.py),
[pilot runner](../../scripts/runs/run_chronos_controlled_pilot.py).

## Existing persistence guarantees

**Observed:** `GroupStore.commit()` validates a whole window/mode/fork group,
checks linked trajectory archives, writes steps/summary/RNG and their manifest
into a sibling `.pending-*` directory, then publishes by rename. File writers
flush/fsync; publication retries transient Windows locks and refuses replacement.
Global CSV exports follow publication and are reconstructible. Archive publication
precedes group publication and uses its own temporary directory.

**Observed:** recovery validates hashes, identities, row counts, sequences and
schemas. A pending group with a final manifest blocks ordinary resume and needs
explicit validated recovery. Incomplete pending data are preserved and excluded.
An archive published without its group is not automatically a completed group.
There is no durable per-token, per-ensemble or mid-generation checkpoint.
Retry may repeat an entire fork even when an orphan archive already exists.

**Observed:** `GroupStore.__init__` can create a directory; `recover()` rewrites
global CSVs. Neither is an appropriate concurrent read-only entry point. Existing
analyzers read global CSVs, which may be appended while inference runs; some also
write derived outputs beneath the input run. No writer lock or immutable reader
snapshot contract was found. File fsync plus rename does not establish a tested
power-loss durability guarantee for parent-directory metadata.

**Observed during this task:** the full offline suite produced 223 passes and
one resume-test failure in 80.46 s. Replacing a recovered global steps CSV at
`results_io.py:83` raised Windows `PermissionError`/WinError 5. A single targeted
repeat passed in 9.60 s. This is consistent with a transient access-denial
problem, but its cause was not established. Unlike directory publication,
single-file `_atomic_write` replacement has no retry. The full suite is not
green; no persistence source or test was changed. Existing group durability does
not imply that reconstructing every CSV export will always succeed.

Sources: [group store](../../code/chronos_fpa/runtime/checkpoint_store.py),
[atomic writes](../../code/chronos_fpa/runtime/results_io.py).

## Suggested safe extension, not implemented

1. Freeze a grid manifest with stable task IDs derived from grid revision,
   context/model/policy hashes, b, token or residual/direct role and RNG stream.
   Use one writer. Keep historical schemas readable and immutable.
2. Publish one complete ensemble at a time as a validated, checksummed immutable
   object. Record full tokens/values, RNG identity/state, selected/residual masses,
   shapes, captured/omitted tensors, timings and attempt ID. Use sibling temporary
   files and flush/fsync before final publication. Test the actual Windows
   filesystem; describe process-crash and power-loss guarantees separately.
3. Publish a parent fork manifest only when required reference, alternatives,
   residual and null objects validate. On restart reuse finalized ensemble IDs;
   retain failed attempts. Do not count incomplete parents as completed forks.
4. A new reader only enumerates finalized names, fixes a manifest/hash cutoff,
   validates immutable objects and records that snapshot digest. It never calls
   `recover()`, follows mutable exports, or writes into source objects. Write
   analyses to a separate destination tied to the snapshot; newly arriving groups
   enter only a later snapshot. A finalized checkpoint is not a Git commit.
5. Interrupt synthetic writes before/after each publication boundary; test
   corrupt/missing objects, duplicate IDs, Windows lock denial, resume idempotence
   and a reader during publication. Verify no silent recomputation or source edits.

## Suggested cost/quality checklist

- Measure encoder/decoder calls, elapsed seconds per ensemble/window, load time,
  RAM/VRAM peaks, bytes per captured tensor, compression time and disk throughput.
- Separate minimal/exhaustive-fork/exhaustive-all-step capture; exhaustiveness
  changes only after a measured bottleneck and explicit researcher decision.
- Verify logits/q50 parity before speed claims; include full-prefix conditioning,
  forced-token alignment, cache aliasing and deterministic replay checks.
- Preserve raw/full-suffix and fixed22 metrics, independent nulls and residual
  mass; use original-series units and label representative/diversity strata.
- Quantify N20 mixture, P10 reuse and N60 direct estimator variance; repeated
  finite-pool resampling is not independent generation or a population interval.
- Price metadata/checksum overhead and worst lost work against smaller checkpoint
  granularity. Recheck analysis overhead while reading immutable snapshots.

**Observed environment, 15:05:45 UTC:** Intel Core Ultra 7 265U, 12 physical/14
logical cores, 15.46 GiB visible RAM, approximately 1.36 GiB free, Intel Graphics,
approximately 300.5 GiB free on C:. These are a transient inventory, not a GPU
benchmark. Initially no repository `.venv` existed, and the available Python
3.12.12 had none of the development dependencies. During this task the researcher
installed `.venv` and asked Codex to continue. Its metadata now reports NumPy
2.4.4, pandas 3.0.2, Torch 2.11.0, Transformers 5.12.1 and pytest 9.2.0. No
installations were performed by Codex. The existing offline suite was then run;
its exact result and elapsed time are recorded in the integration report/status.
The researcher's new `uv.lock` is preserved, outside the recommended docs commit.
Historical CPU timings remain report facts, not performance checks repeated
today. Future performance work still requires explicit approval and a fresh
resource check.

**Suggested next bounded task:** the
[Phase-0 proposal](../../codex-prompts/PROMPT_00_BOUNDED_BENCHMARK.md), after
skeptical scientific review and explicit authorization. No major feature is
implemented by this audit.
