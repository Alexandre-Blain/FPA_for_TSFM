# FPA handoff - bounded Prompt 2 validation

**Observed: 2026-11-20.** Branch `main`; pre-user-commit HEAD
`687c34f5f144476ea530c4210d3ed294c3b543e9`.
**No new commit SHA exists.** Worktree changes are unstaged; `uv.lock` is
the researcher's separate, unchanged environment artifact. Exact status,
paths/reasons and selective manual Git commands are in the
[benchmark report](BENCHMARK_REPORT.md) and [evidence](FPA_PROMPT02_EVIDENCE.json).

**Authorized scope:** Prompt2, four hours implementation/tests, at most
30 minutes of model work. One cached M4/T000001 C512 context, original
Chronos-T5-mini, H32, CPU float32/eager/one thread; no downloads, installations,
cloud/GPU, full campaign or Stage A. Start `2026-11-20T15:37:06Z`.
Model subprocess wall time totaled **205.829 s**, including load/replay.
Correct native process-tree committed-memory peak: **747.04 MiB** under 2 GiB.
The initial redirector-only memory measurement was invalid; corrected
supervision and its limitation are documented. Output ceiling was 512 MiB.

**Observed implementation:** q50 cumulative coverage/cap 8, conditional residual,
independent null, full token/value paths, encoder reuse, decoder prefix KV
cache with isolation, batching, signed J and fixed22/full W1/ED. Fixed
terminal/last8 events are estimated at P0..15 using q50 mixtures, P10 reuse,
and direct N60 P11..15. Formal BEAST/change-point fitting was not implemented.
Immutable ensemble objects and completed parent-fork manifests support
committed-only read snapshots; interrupted-ensemble resume is tested.
Persistent Windows CSV replacement failures retain complete pending output.

**Observed real checks:** initial N2 cell: 58 ensembles/580 paths/36.796 s;
target N20 cell: 58 ensembles/1,480 paths/**78.922 s**. Same original context,
separate experiment identities/streams. Another 78 executed timing slots
reuse seeds and are not independent replications. Cached N2 b0 decoding was
0.314 s versus 11.558 s reference, about 36.8x in one warm timing comparison;
this is not an end-to-end campaign speedup. Three tokens covered
0.98108..0.99001 q50 mass at all ten dense positions.

**Observed white-box checks:** eight named saved reference/alternative paths
per cell at actual b0/b9, all layers/heads, before/after forced tokens and
all 32 queries. Other samples explicitly omit replayable activation arrays.
Full all-step decoder/logit payload is **3,002,752 raw bytes/path** plus
shared encoder data. Cached versus full-prefix and attention replay passed
declared atol/rtol and exact support checks. No GPU/fast-kernel claim follows.

**Observed tests:** **250 passed in 41.26 s**, offline; the later handout
ordering check passed **4 tests in 2.45 s**. Covers mathematical identities, known-mixture calibration,
cache isolation, crash/resume, checksum rejection, complete-only analysis,
Windows child-process accounting/termination and canonical-doc preservation.
Source archives preserve all 26 exact collection versions. Final historical
content/inventory and Git-index checks are in current evidence. Older
integration reports remain dated evidence, not current implementation status.

**Artifacts:** ignored `result/prompt02_micro_20261120T153706Z/` contains
summaries, complete token/value ensembles, q50 metadata, outcome laws,
snapshots, parity, named captures, supervision audit and original source
copies. The [report](BENCHMARK_REPORT.md), [evidence](FPA_PROMPT02_EVIDENCE.json),
[test log](FPA_PROMPT02_TESTS.txt) and
[proposed grid](FPA_PROPOSED_GRID.json) are the reviewable deliverables.

**Scientific limits:** one previously studied context with a flat greedy path;
no population inference, no formal CPD validation, no added-information
claim beyond probability/entropy/J. Real mixture/direct overlap discrepancies
reach 0.236; conditional plug-in SEs are not CIs. Full-capture streaming/cache
eviction and new-domain resource bounds remain open. StageA H64/N50 seed2718
and the multi-series H32 campaign remain unexecuted.

**Single next suggestion:** after skeptical ChatGPT review, approve a
30-minute **data-only** task to freeze/QC six original-series windows
(two per three reviewed datasets, representative and diversity strata).
No model draws. Stop on invalid scale, missing identity/hash, future leakage
or accidental duplicate series; retain exclusions. A campaign still needs
a frozen grid, capture architecture, hours/storage and separate approval.

**Upload:** `docs/chatgpt-handout/CHATGPT_HANDOUT.md` or
`docs/chatgpt-handout.zip`. The refresher replaces only validated generated
copies between prompts. Historical plans/reports remain canonical.
Only the researcher stages, commits and pushes.
