# FPA / Chronos - verified research status

**Observed snapshot: 2026-11-20.** Branch `main`, current HEAD
`558846c82002c2cb6070fbfff9bed22f514424a3` (`smoke test`, created outside
Codex). Documentation follow-up changes remain unstaged; Codex made no Git
writes. **Prompt 2's bounded technical validation is complete.**
The full exploratory campaign and Stage A remain unexecuted.

**Documentation follow-up, 2026-11-20:** [the index](../README.md) now separates
current research, practical methods and historical reports. The handout
refresher includes referenced guides and rewrites combined-document links to
internal sections. See the [link/organization report](../maintenance/DOCUMENTATION_LINKS.md).
The Prompt2 evidence remains the frozen benchmark snapshot; no new inference
was needed for this follow-up.

Labels: **observed** = checked code/artifacts or attributed historical reports;
**suggested** = proposed work; **hypothesis** = unestablished scientific claim.

## Current milestone

The researcher authorized four hours for implementation/tests and at most
30 minutes of model work, on one existing M4/T000001 C512 context, CPU float32,
without downloads or installations. Model subprocesses used **205.829 seconds**
in total, including loading and deterministic replay. Corrected native Windows
process-tree measurements peaked at **783,323,136 committed bytes (747.04 MiB)**.
The first run's redirector-only memory reading is invalid and preserved as such.

The opt-in prototype now implements q50 cumulative selection (90% target,
cap 8 including greedy), conditional residual sampling, independent same-token
nulls, complete token/value paths, encoder reuse, prefix KV-cache, batching,
fixed22/full strict-suffix W1/ED and signed direct jump. It estimates fixed
per-window outcome laws P0..15, with branch mixtures P0..9, greedy-b9 reuse
P10 and direct N60 P11..15. Formal change-point inference is not implemented.

Two separate engineering cells on the **same original context** completed:

| Cell | Ensembles | Stored paths | Collection wall time |
| --- | ---: | ---: | ---: |
| Dense micro N2 + direct/overlap N60 | 58 | 580 | 36.796 s |
| Dense target N20 + direct/overlap N60 | 58 | 1,480 | 78.922 s |

These are 2,060 collection paths, plus 78 executed timing path slots with
reused seeds. They are not independent series or independent timing
replications. All ten positions selected three tokens; selected q50 mass was
0.98108..0.99001. This favorable single context is not representative of cap 8.

All-layer/all-head encoder and decoder capture was verified on **eight named
saved paths per cell**, before/after actual b0/b9 forks and at all 32 queries.
Other paths retain full tokens/values and explicit replayable activation
omissions. Full all-step decoder/logit payload is 3,002,752 raw bytes/path;
streaming capture and cache eviction still need engineering for a panel.

## Validation and persistence

**Observed:** the complete offline suite passed: **250 passed in 41.26 s**.
A later handout-order-only change passed **4 focused tests in 2.45 s**.
Tests cover q50/residual mass, cache isolation/conditioning, tiny random T5
parity, known-mixture calibration, exact distances, interrupted ensemble
resume, complete-only fork reads, Windows process-tree termination and
handout preservation. No pretrained weights are loaded by pytest.

Real cached/teacher-forced/attention replay comparisons passed explicit
atol/rtol tests and exact q50 support equality. A maximum absolute error alone
is not the acceptance criterion; see the [benchmark report](BENCHMARK_REPORT.md).

The legacy CSV writer now retries bounded Windows replacement errors and
preserves a complete pending file on persistent failure. The observed
historical WinError5 cause remains unproven. New immutable ensemble/fork
snapshots are read without exports, recovery, RNG restoration or writes.
The prototype resumes complete ensembles; interruption inside an ensemble
still loses that uncommitted ensemble. OS power-loss durability is not proven.

## Historical evidence and scientific limits

Phase2 remains seven finalized groups/1,400 paths across three original series,
C512/H64/N50. Phase3 Deliverable A remains offline controls. Their reports and
raw artifacts are preserved; no historical statistics were recalculated.
Stage A M4 H64/N50 seed2718 remains a separate unexecuted proposal.

Historical selected M4 asymmetry, ERCOT early localization, unstable rankings,
near-null effects and entropy confounding remain attributed source findings.
**Hypothesis:** added information beyond local probability/entropy/signed jump
has not been established across an independent population by this benchmark.
Attention capture supplies measurements, not a causal explanation.
Conditional Monte Carlo SEs are not population confidence intervals.
Real mixture/direct overlap gaps reach 0.236 in this one cell; CPD reliability
and the P10/P11 estimator boundary are not scientifically validated.

## Next gate and handout

Read the [benchmark report](BENCHMARK_REPORT.md),
[current evidence](FPA_PROMPT02_EVIDENCE.json) and [handoff](FPA_HANDOFF.md).
A [six-series planning grid](FPA_PROPOSED_GRID.json) is **suggested, not frozen
or authorized**. The single next recommendation is a separately approved,
30-minute **data-only** selection/QC task to freeze six original-series
windows without model draws, after scientific review.

`docs/chatgpt-handout/` and `docs/chatgpt-handout.zip` are disposable upload
snapshots, refreshed by `scripts/maintenance/prepare_chatgpt_handout.py`.
Canonical historical reports remain available; superseded proposals are
labeled. Only the researcher stages, commits and pushes.
