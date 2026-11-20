# Technical implementation gates: correctness first, then throughput

**Current evidence:** the [completed six-series pilot](LOCAL_PILOT_REPORT.md)
extends validation to ten isolated window/seed cells, real cap8/residual cases,
conditional uncertainty and batched replay. Exact scope, 264 offline tests,
2924 real parity checks and remaining limitations belong in that report.
The sections below define technical contracts, not authorization for another run.

**Observed update - 2026-11-20:** bounded Prompt2 exercised gates 0..4 on one
cached context, including target N20, full-prefix/cache parity, residual
mixtures, exhaustive replay on named paths, interrupted-ensemble resume and
complete-only fork snapshots. The [benchmark report](BENCHMARK_REPORT.md)
records exact coverage and untested cases. The full offline suite passed 250.
The [November 19 audit](../archive/FPA_IMPLEMENTATION_AUDIT.md) is historical evidence;
its capability inventory is superseded by the current report.
Legacy GroupStore.recover() still writes exports; use the new pure snapshot
reader for prototype analysis. Full-capture streaming/cache eviction, formal
CPD reliability, cross-domain bounds and gates 5/6 remain open. The former
Phase-0 proposal is superseded. No long run follows from this document.

**Status:** candidate specification. This file is intended for Codex to convert into tests/benchmarks. No long run may start by virtue of this document.

## Gate 0 - Inventory and consistency (read-only)

Identify current code entry points, current `AGENTS.md`, config loading, old research-plan copies, model revision/precision, tokenizer, candidate q/p definitions, checkpoint infrastructure and existing raw trajectories. Audit platform hardware (GPU availability, CPU cores, memory, disk space), repo dirty state, installed Torch/Transformers/Chronos versions, and actual old path latency. No code changes or inference during a read-only audit. Resolve any discrepancies with current reports.

## Gate 1 - Measurement equivalence and tests

Minimum correctness tests:

- Fixed context and greedy path across H32/H64 where architecture guarantees common prefixes; assert indexing (0..9) and strict post-fork suffix lengths 31..22.
- Same valid-token mask/top-k tie handling, temperature, top-p, p_sel and q50 normalization as original; confirm greedy candidate in top-8; residual exactly remaining q50 mass.
- Residual sampler: first token is drawn from q50 conditional on not chosen; next steps use unconditioned q50; integrate to a full mixture, not duplicated reference.
- Compare per-step logits and q50 probabilities for reference decoder vs optimized encoder-reuse / decoder cache / batch, with documented dtype/backend tolerances; verify same conditional law. Random generators may diverge in exact sampled tokens after batching, which is not automatically a failure of distributional parity.
- Compare W1 with independent ground-truth numerical computations for equal/unequal sizes; Energy Distance V-statistic including diagonals, no final sqrt; direct jump separate. Same-token independent controls nonzero generally, and zero-equivalence test with exactly duplicated samples.
- Check event predicates for Y31/last eight reconstruct path including forced token; check invariant same outcome at every t; test fixed22 metrics across b0..9.
- Confirm `P_{t,g_t} = P_{t+1}` as **theoretical identity** by matching conditioning and policy, not by requiring distinct finite-N realizations to match bitwise.
- Synthetic mixtures with known outcome distribution: weighted branch+residual CPD reconstruction vs direct draws, compare mean/variance across repeated trials; protect method boundary t9/10/11.
- Full offline test suite and code QA; audit `torch.no_grad()`, `eval()`, potential data leakage, tensor device/dtype.

## Gate 2 - White-box exhaustive prototype

Try to capture on a few **real but bounded** contexts:

- Encoder hidden states **all layers**; encoder self-attentions by head/layer.
- Decoder hidden states **all layers** for greedy prefix and forced-token branches; decoder self-attentions; cross-attentions.
- Logits for each relevant step, full token sequences and decoded numeric values, p_sel and q50 support/probabilities, token embedding/bin mapping, branch metadata, timing.
- Branch before/after representations as distinct named objects; ensure a before-fork decoder state doesn't include the forced token.
- Capture once per shared encoder/context, once per shared prefix/state when deterministically identical, and reuse/replay rather than writing duplicates. Do not mistake **encoder static** for **decoder prefix static**.
- Test output-attention mode against caching/fast attention paths on installed T5 implementation, memory peaks, latency, payload MB per window, compression/float dtype, disk bandwidth.
- Keep an option for **deterministic replay** of recorded token paths to extract activations later. Verify replay equivalence, revision and deterministic eval; replay is not a new stochastic rollout but does consume compute.
- Store tensor names, shape `(n_layers,n_heads,query_len,key_len)` as applicable, token alignment, dtype, numerical metadata, retention policy and checksum. Be wary of multi-GB uncompressed stores.

Benchmark profiles: minimal, exhaustive-forks, exhaustive-all-steps. Default ambition = exhaustive. **Only reduce after measured bottleneck** and explicit documented decision; do not silently drop layers or heads.

## Gate 3 - Throughput improvements, in order

1. **Encoder reuse:** encode X once per original window, reuse encoder_outputs across all positions/branches; verify previous generated tokens still condition the decoder.
2. **Decoder prefix KV-cache:** build prefix along greedy path once (per window), correctly copy/reorder cached keys/values before branching; validate sequential semantics and all attention masks.
3. **Forced-token prefix reuse:** initialize N20 rollouts from shared `prefix+forced_token` state; no redundant encoder or token pass. Avoid mutable-cache aliasing between branched streams.
4. **Batching:** benchmark batch sizes 1,2,4,8,16 or hardware-appropriate sweep, including output_attentions and CPU/GPU differences; compare true end-to-end cost and RAM/VRAM.
5. **Compute adaptation:** exploit variable number K<=8, skip zero residual, avoid full logits/attention output at redundant repeated steps, compute offline metrics only once per committed group.
6. **Statistical pooling/stratification:** exploratory efficiency method, not assumed unbiased; benchmark against dense reference with held-out positions and series and unknown impact on CPD.

Do **not** optimize solely for generated-token count: measure wall-clock, memory, disk, and scientific precision. The old CPU float32 single-thread timing is a historical observation, not a guaranteed speed benchmark.

## Gate 4 - Data architecture and persistence

Every **committed** sample/group needs a validated schema with stable IDs:

- `experiment_id`, `grid_revision`, `dataset_id`, `series_id`, `window_id`, `forecast_origin`, `context_hash`, `context_scale`, `model_revision`, tokenizer and environment hash, `git_commit`, policy parameters and hardware.
- `b`, prefix token IDs and greedy path IDs, actual candidate IDs, rank, `q50`, `p_sel`, q50 selected coverage and residual r, role (`greedy/alt/residual/null/direct_cpd`), seed/RNG stream, N and outcome-path coordinate conventions.
- Full numeric continuation **and** full generated token path or reconstructable prefix+suffix, terminal and last8 event inputs, optional hidden/attention arrays with manifest of **captured vs omitted** tensor fields.
- Raw logits or enough exact raw logits to reconstruct p_sel/q50 where desired; store precision/shape explicitly.
- File checksums, completion marker, sample count and verified retrieval path, CPU/GPU runtime, peak memory, disk footprint and failures.

**Atomicity:** write temp objects, validate shapes/checksums, fsync where appropriate, publish manifest/committed marker only after data is durable. Failed partial groups must not be counted. Resume idempotently by stable task ID; do not duplicate or silently re-generate a committed branch; preserve failed attempt log and seed state. Prefer fine granularity (per token/ensemble) after verifying replay/resume; do not require restarting 4-hour group after a crash.

## Gate 5 - Long campaign and online analysis

- Generate from a frozen, versioned grid of representative/diverse windows and Stage A cell if separately approved. Log all deviations and early stops.
- Analysis jobs **read only committed objects**, cannot mutate inference artifacts, and can run concurrently if throughput effect is low; otherwise schedule CPU-light analysis pauses. Analysis results cite the immutable data revision.
- Operational dashboard: completed/total original series, windows, dense positions, branch alternatives, trajectories; q50 coverage distribution; rejected tasks; runtime, ETA from measured batches **internally**; disk/memory; null diagnostics and severe anomalies.
- Scientific interim report: per-dataset/sample-stratum outcomes, uncertainty, selected case artifacts, and risk of treating windows from one original series as independent; raw previews never unlock automatic hypothesis-driven reruns unless explicitly designed and logged.
- Stable progress can be shared with ChatGPT using `FPA_HANDOFF.md`; ChatGPT never assumes live access to local files.

## Gate 6 - Go/no-go before major inference

Deliver a benchmark report with: exact repo hash and methods, parity and test results, residual-mixture and CPD sanity checks, white-box storage/time costs, real runtime per H32/b 0..9 group and direct N60 CPD group, projected windows/series under user budget, worst-case RAM/disk, checkpoint crash/recovery test and recommended grid with scientific trade-offs. **Request explicit user authorization for actual hours and frozen grid.**
