# Proposed Phase 0 — bounded correctness and capture preflight

**Superseded proposal, 2026-11-20:** the researcher selected Prompt 2 directly
and supplied its resource limits. Keep this earlier proposal as provenance;
use the current decisions/status and Prompt-2 invocation instead of executing it.

**Suggested task; NOT AUTHORIZED and NOT RUN.** This is a technical preflight,
not a restart of the historical research phases. Use only after ChatGPT reviews
the integration report and the researcher explicitly approves this exact scope.

Approval reference: `[RESEARCHER MESSAGE / ID — REQUIRED]`

Read root `AGENTS.md`, `docs/research/FPA_STATUS.md`,
`docs/research/FPA_PROTOCOL_EXPLORATORY.md`,
`docs/research/FPA_IMPLEMENTATION_AUDIT.md` and the decisions log. Git operations
remain read-only; the researcher alone stages, commits and pushes.

## Proposed limits

- Total task ceiling: **30 minutes elapsed**, including checks and reporting.
  Stop and report partial results when the ceiling is reached.
- Real-model subprocess: **180 seconds maximum including load/replay**, enforced
  by a parent deadline that can terminate an in-flight decode. Do not rely on
  the current pilot's between-group budget checks as a hard timeout.
- CPU float32, one Torch intra-op/inter-op thread, one model; no GPU switch.
  Recheck available RAM before loading and stop below 4 GiB free. Peak process
  memory ceiling: 4 GiB; new output ceiling: 256 MiB. Stop on allocation failure;
  do not page through a larger experiment.
- No installations, upgrades, network, model or dataset downloads. The researcher
  installed `.venv` during integration; verify it still exists and inspect the
  integration report's actual offline test failures before doing anything else.
  Stop after a static readiness report if the environment is unavailable or a
  blocking correctness failure remains. This template grants no setup/upgrade
  permission.
- One existing local context only: `m4_daily/T000001`, window/start 0/0, first
  512 observations, from
  `data/raw/chronos_benchmark/autogluon_chronos_datasets__m4_daily__train.jsonl`.
  Require float32 context SHA256
  `18998a44bd1ed2d0330f5dfb13487b641a919e5d48eab192c52cdb6d14b12380`.
  Pin cached model revision `bd6a4fde8403b8469acd0abd52852b29dbe61c7b`
  using local-only loading before model access; stop if absent/mismatched.
- Separate new scratch output under `result/phase0_micro_<UTC>/`; never run a
  historical runner with `--resume-from`. No Stage A seed2718 replication.

## Scientific question and competing explanation

**Hypothesis:** the existing decoder law can be reproduced with exhaustive
white-box capture/replay at tolerable cost. **Competing explanation:** attention
mode changes logits/kernels, or capture consumes the available memory/time.
The preflight cannot establish FPA's added scientific information or CPD validity.

## Work allowed after approval

1. Use existing pure offline tests if the approved environment is available.
   First investigate the recorded Windows CSV-replacement failure using synthetic
   temporary artifacts and the existing resume test. A single passing repeat
   does not establish robustness. Do not enter the model section until a
   separately approved fix has been validated or the researcher explicitly
   dispositions this remaining risk; no production fix is authorized here.
   Check H32 post-fork indexing at b0 and b9, known W1/ED examples, independent
   null streams, invalid IQR and actual top-k tie behavior. Synthetic mixture
   examples can verify normalization and the P(t,greedy)=P(t+1) conditioning
   identity. Report residual/CPD integration as missing if still absent.
2. Keep production modules/configurations unchanged. Use a disposable benchmark
   harness in the new output directory for reference decoding and capture hooks.
   Store the harness hash/source with its results. No production encoder-cache,
   KV-cache, residual sampler or CPD implementation in this task.
3. Under the hard model deadline, freeze one H32 greedy path; at b0 and b9 sample
   only reference, one plausible alternative and an independent same-token null,
   **N=2 for smoke mechanics only**. Cap stochastic suffix decisions at **512**;
   do not top up unfinished tasks. Preserve effective q50, masks and temperature1.
   This microbudget changes neither the candidate campaign's N20 nor its grid.
4. Record full token paths and numeric values. Replay the same paths once with
   all encoder/decoder hidden layers, all encoder/decoder/cross-attention heads
   and logits, deduplicating shared deterministic states. Compare reference and
   capture-mode logits/q50 at corresponding prefixes; confirm all previous
   generated tokens remain in conditioning. Do not silently omit tensors.
5. Measure load/decoding/replay time separately, capture bytes, peak memory and
   missing fields. Use synthetic crash points for pending/final publication and
   a read-only snapshot proposal; never mutate existing artifacts to simulate a
   failure. Full production checkpoint concurrency remains a later gate.

## Pass/fail and stop gates

- **Pass mechanics:** exact indexing and known-array answers, valid probability
  mass/support, distinct null streams, preserved tokens and complete capture
  manifest. Use float32 `atol=1e-5, rtol=1e-4` for per-step logits and
  `atol=1e-6, rtol=1e-4` for q50, checking support explicitly. These are proposed
  engineering tolerances; report maxima and argmax/support differences rather
  than treating a tolerance pass as proof of statistical equivalence.
- **Fail/stop:** prefix/token misalignment, policy/support drift, missing revision,
  altered source hashes, incomplete capture, deadline, memory/storage breach or
  unavailable environment. Preserve diagnostic outputs; no retries with changed
  precision, smaller context, fewer layers or a different policy.
- N2 effect/null distances are smoke outputs, not hypothesis tests. No positive
  FPA, morphology or CPD conclusion follows from passing this preflight.
- No throughput extrapolation from this single context is sufficient to approve
  a dense campaign. Residual-mixture, full fixed22 export, P0..15/N60, production
  caching and ensemble-level recovery gates remain open until implemented/tested
  under a separately bounded task.

Write `BENCHMARK_REPORT.md` inside the new scratch output with exact executed
scope, failures, parity arrays, hashes, elapsed/resources and missing gates.
Update status/handoff with observed facts only; append only actual researcher
decisions. Return the report for skeptical review and stop before another task.

NO NEW MODEL INFERENCE RUN; AWAITING SCIENTIFIC REVIEW / USER AUTHORIZATION
