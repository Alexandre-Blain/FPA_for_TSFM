# Prompt 2 benchmark and implementation report

The subsequent authorized multi-series task is now complete; its
[current report](LOCAL_PILOT_REPORT.md) governs scientific review. Planning
recommendations below describe the historical Prompt 2 handoff.

**Linked correction, 2026-11-20:** the frozen original evidence is unchanged.
Its `target_N20` field was overwritten during link parsing in the finalizer;
the [addendum](FPA_PROMPT02_EVIDENCE_ADDENDUM.json) restores the structured
information from the intact raw summary and verifies all 25 archived N20
research-module hashes. The exact intermediate N20 execution driver remains
unarchived. This correction adds no model draws and changes no trajectories.

**Observed 2026-11-20.** The authorized single-context correctness/performance
prototype is complete. The complete offline suite passed **250 tests in 41.26 s**.
Model subprocesses used **205.829 s of the approved 1,800 s**. Implementation/tests
were bounded by four hours from **2026-11-20T15:37:06Z**. No further stage ran.

This report supersedes the November 19 audit's implementation inventory, while
preserving that audit as historical evidence. Scientific hypotheses and the
candidate population design remain subject to review.

## Scope and reproducibility

- Branch **main**, existing HEAD **687c34f5f144476ea530c4210d3ed294c3b543e9**.
  All changes are unstaged; **a new commit SHA does not exist**. No Git writes.
- Model `amazon/chronos-t5-mini`, pinned cached revision
  `bd6a4fde8403b8469acd0abd52852b29dbe61c7b`; CPU float32, eager attention,
  one intra-op/inter-op thread, eval/no-grad. No downloads or installations.
- Python 3.12.12, Torch 2.11.0, Transformers 5.12.1, NumPy 2.4.4.
  No Chronos package was installed; existing plain modules/bootstrap are used.
- Exactly one already studied original series: M4 Daily `T000001`, first 512
  values of the existing train export. Context hash
  `18998a44bd1ed2d0330f5dfb13487b641a919e5d48eab192c52cdb6d14b12380`.
  Context IQR 96.199951171875. H32; no future values used for selection/scale.
  The encoder receives 513 tokens including EOS.
- [Dated configuration](../../configs/chronos_microbenchmark/prompt02.json).
  Its archived `micro_samples_per_group=2` describes the initial cell.
  `--n20-validation` added a separately identified N20 engineering cell;
  `campaign_samples_per_group_not_run=20` does not mean a campaign ran.
  The expired invocation is not standing authorization to repeat inference.
- Ignored output root: `result/prompt02_micro_20261120T153706Z/`. No historical
  run or dataset was overwritten. Stage A M4 H64/N50 seed2718 remains unrun.

The model has four encoder and four decoder layers, eight heads, d_model 384,
vocabulary 4096. The frozen greedy path is token 2188 at all 32 positions.
This simple context and three selected tokens per position make the timing
particularly limited as a predictor of other datasets or cap 8 behavior.

## Implemented operations and scientific definitions

The opt-in path is `scripts/runs/run_chronos_microbenchmark.py`; existing
historical scan/pilot launchers keep their scientific definitions.

`chronos_exploratory.py` retains the original valid-token mask and top50
kth-threshold ties. Thus q50 support can exceed 50 in a tie. It keeps p_sel
separate from q50. Selection reserves greedy first, then descending q50
probability with ascending token-ID ties, stopping at0.90 mass or 8 total
tokens. A positive residual is sampled conditional on the complementary
q50 support for the first token; subsequent tokens use ordinary q50.
Selected weights plus residual equal 1.0. This convention is explicitly
recorded for micro-validation; it does not freeze a population design.

Generation reuses encoder outputs, builds decoder states conditioned on
**every generated prefix token**, forks mutable self-attention KV caches,
and batches paths. Shared cross-attention caches are reused only when already
initialized and safe; repeated batches receive independent mutable storage.
Named role/position/token identities produce deterministic independent RNG
streams. Batched multinomial RNG need not be bitwise equivalent to sequential
draws; the required check is conditional-law parity, including support.

The collector persists complete H32 tokens/values, context, greedy future,
prefix/forced-token IDs, q50/p_sel/residual metadata, seeds, timings,
shape/dtype/content hashes and provenance. Independent same-token null
ensembles are distinct from reference ensembles.

Existing exact empirical marginal W1 and RMS-ground multivariate Energy
V-statistic are used, including diagonals and **no final square root**.
The forced coordinate is excluded. Both full remaining strict suffix
(length31..22 for b0..9) and the first22 strict post-fork coordinates are
exported; signed direct jump J is separate. No historical metric changed.

Fixed outcomes use absolute deviation from the frozen full greedy future:
terminal coordinate31 and mean absolute deviation at coordinates24..31,
each divided by the **context** IQR; thresholds0.05,0.10,0.25,0.50,1.00.
An invalid IQR fails rather than falling back to a different scale.
For each window, P0..9 are q50-weighted selected-plus-residual estimates;
P10 reuses the b9 greedy-forced reference; P11..15 use direct N60.
Additional independent N60 draws at P0,P9,P10 expose estimator differences.
These are outcome-law inputs for future CPD, not a BEAST/change-point fit.

## Offline validation and real-model parity

The [complete test log](FPA_PROMPT02_TESTS.txt) records
`.venv/Scripts/python.exe -m pytest`: **250 passed in 41.26 s**, exit0.
Tests block sockets and load no pretrained model weights. Tiny random T5
fixtures test real cache mechanics without claiming forecasting performance.

After a final source-order-only handout change, the focused handout suite
also passed **4 tests in 2.45s**; no additional model work was performed.

Coverage includes forced-token indexing and strict suffix lengths, q50 ties/
cap/coverage/residual mass, cache isolation and full-prefix conditioning,
hand-calculated/known distance cases, complete outcome reconstruction and
the theoretical conditioning identity P(t,greedy)=P(t+1). A synthetic known
Bernoulli mixture checks repeated independent mixture/direct means and
conditional variance; separate finite-N estimates are not required to match
bitwise. Persistence and resource tests are described below.

Real comparisons use logits **atol1e-5, rtol1e-4**, q50 **atol1e-6, rtol1e-4**,
and exact equality of positive-probability support:

| Comparison | Checks | Maximum absolute logit error | Result |
| --- | ---: | ---: | --- |
| Initial reference/cache/batch/replay | 38 | 7.6294e-6 | Passed |
| N20 pre-sampling full greedy-prefix gate | 32 | Not separately aggregated | Passed |
| N2 saved sampled prefixes | 256 | 9.5367e-6 | Passed |
| N20 saved sampled prefixes | 256 | 1.1444e-5 | Passed |

Initial maximum q50 absolute error was1.1921e-6. Combined absolute/relative
tolerances explain why an absolute maximum can exceed the absolute tolerance.
Attention-enabled versus ordinary teacher-forced replay matched logits/q50
exactly in the three actual-path capture profiles. This freezes eager CPU
behavior only. No SDPA, GPU, mixed-precision or cross-backend parity was tested.

## Measured generation cost and sample accounting

One-pass timings in seconds, same context, warm prefix reuse where applicable:

| Variant | Paths | Wall seconds |
| --- | ---: | ---: |
| Reference, no encoder/KV reuse, b0 | 2 | 11.557870 |
| Encoder reuse only, b0 | 2 | 1.983367 |
| Encoder and KV reuse, b0 | 2 | 0.314132 |
| Cached batch1 / batch2 / batch4 / batch8 | 8 each | 1.543725 / 1.113851 / 0.746223 / 0.531549 |
| Cached reference, batch8, b0 | 20 | 1.355609 |
| Cached residual, batch8, b0 | 20 | 1.313465 |

Initial model loading took4.972s; the first encoder call0.316s.
The N2 cached/reference ratio is about 36.8x; it excludes shared setup and
is not an end-to-end campaign speedup. Timings were not replicated or
randomized; reused seeds in these profiles do not create independent evidence.
No baseline N20 full-window reference run was needed or performed.

| Cell | Dense role ensembles / paths | Direct P11..15 | Overlap P0,9,10 | Total ensembles / paths | Collection wall |
| --- | --- | --- | --- | --- | ---: |
| N2 micro | 50 /100 | 5 /300 | 3 /180 | 58 /580 | 36.795528s |
| Target N20 | 50 /1,000 | 5 /300 | 3 /180 | 58 /1,480 | 78.922412s |

Each dense position has reference, two alternatives, independent null and
residual. All ten selected three tokens with q50 mass0.981084..0.990010.
Thus 2,060 collection paths were persisted, plus 78 executed timing path slots.
N2 and N20 use separate experiment identities and streams; N20 is not nested
reuse of N2. Capture/replay created **zero new stochastic paths**.

N20 generation alone: reference10.472s, alternatives22.210s, null10.576s,
residual10.896s =54.154s dense; direct11.612s; overlap9.156s.
The remaining collection wall time includes metrics and durable publication.
Dense/direct/overlap roles are not all independent outcome estimates:
P10 reuses a reference ensemble.

## Exhaustive white-box measurement and storage

Initial profiles used two timing paths with a common query grid. Additional
resource replays used actual persisted b0/b9 reference and first-alternative
paths, first two per role/position: **eight named paths per cell**. Their IDs
and path indices are recorded in `resource_replay.json` and
`n20_resource_replay.json`. No cherry-picked outcome was used to choose them.

All encoder hidden outputs 0..4 (embedding plus4 layers), encoder attentions
0..3/all 8 heads, decoder hidden outputs 0..4, decoder self/cross attentions
0..3/all 8 heads, logits, tokens and values were captured. The initial shared
object also preserves embeddings/bin mapping and tokenizer inputs. Before
fork = query b, which predicts token b without consuming it; after fork =
query b+1, which consumes the actual forced token. Full causal key axes,
including masked zeros, are retained with shapes/dtypes/alignments.

Actual N20 eight-path profile costs:

| Profile | Raw decoder/logit/token/value bytes | Wall incl. serialization |
| --- | ---: | ---: |
| Minimal (all-step logits/tokens/values) | 4,197,376 | 0.612771s |
| Exhaustive before/after forks | 1,504,256 | 2.781540s |
| Exhaustive all 32 queries | 24,022,016 | 2.058151s |

Fork attentions have shape[8,8,2,32], cross-attentions[8,8,2,513] per layer.
All-step versions use32 queries. The initial shared encoder/static payload
is43,973,105 raw bytes. Encoder arrays are persisted once per capture set,
not once per path; capture replay currently recomputes the encoder to
request states and is not a streaming optimized exporter.

Profile times are single passes; the fork profile includes first shared
encoder serialization and is not a fair isolated comparison with the later
warm all-step profile. Compressed NPZ size and total output sizes are in
[evidence](FPA_PROMPT02_EVIDENCE.json); compression is not guaranteed elsewhere.

Full all-step payload is **3,002,752 raw bytes/path**, about 2.864MiB.
Only the named paths have exhaustive capture; other stored samples explicitly
omit hidden/attention/logit arrays and retain deterministic replay inputs.
This bounded profile scope was authorized by the micro task. A full-campaign
retention policy remains a scientific/resource decision. No layers/heads were
silently discarded within an exhaustive profile.

## Publication, crash/restart and Windows behavior

New immutable ensemble objects validate tokens/values, shapes/dtypes/payload
checksums, flush/fsync files, then publish a finalized directory. An ensemble
is invisible until complete. Tests simulate interruption after three complete
objects, resume without regenerating them, and finish all roles/outcome laws.
Complete pending objects can be explicitly recovered; malformed/checksum-bad
objects are rejected. Work interrupted inside an ensemble remains uncommitted;
it is not resumed mid-token. OS power-loss durability is not established.

Parent fork manifests bind q50 weights and child manifest hashes, and publish
only when reference/alternatives/residual/null all exist. Pure snapshot readers
freeze IDs/digests, ignore pending objects and perform no mkdir, recovery,
CSV writes or RNG restoration. Offline tests verify an incomplete fork is
absent and ten complete forks appear on resume.

Parent-fork publication was added **after** real collection. Existing saved
fork metadata and validated immutable child objects were used to publish
the 20 parent manifests offline; no sampling/child artifacts were rewritten.
Collection provenance refers to archived source versions, not the later
bookkeeping addition. Current file hashes are separately recorded.

Legacy CSV atomic replacement now retries only bounded Windows errors5/32/33.
After persistent failure, the old target survives and a complete flushed
temporary file is retained with its location in the exception note.
Tests cover transient success and persistent preservation; incomplete writes
are cleaned. This handles the observed failure class; it does not prove
antivirus/Excel/permissions caused the earlier WinError5.

The first supervisor watched the venv redirector, not its spawned real Python.
Its reported 4,395,008-byte peak is **invalid**, and its process-tree containment
was not proven. That stage finished normally in 85.172s. We corrected supervision
before subsequent model stages: create suspended, assign a native Windows Job
Object, then resume; enforce 2 GiB committed-memory/process-tree limits and
terminate the whole job at deadline. An offline 64 MiB child-allocation test
verifies descendant accounting and termination.

| Model stage | Subprocess wall seconds | Valid native peak committed bytes |
| --- | ---: | ---: |
| Initial N2 collection | 85.172 | Unmeasured (redirector-only) |
| N2 saved-path replay | 15.438 | 732,221,440 |
| N20 collection | 87.672 | 783,323,136 |
| N20 saved-path replay | 17.547 | 732,393,472 |
| Total | **205.829** | **747.04MiB max among valid stages** |

The shared budget includes subprocess startup/load/parity/replay. Corrected
runs enforced a 512 MiB output ceiling and 512 MiB system-free floor, with 1 GiB
free required before loading. No stop/failure occurred. The per-stage history
was consolidated from observed supervisor tool/console outputs afterward;
it is labeled as an audit, not represented as original per-stage log files.
The mutable ledger's last-stage peak is not the maximum across all stages.

## Planning grid and scientific limitations

The [proposed grid](../archive/FPA_PROPOSED_GRID.json) is **not frozen, not executable
and not authorized**: six distinct original-series windows, one per series,
two per proposed M4/ERCOT/Exchange Rate dataset: one representative and one
context-diversity stratum. Selection rules, seeds, eligible pools, IDs,
forecast origins, hashes, invalid-IQR exclusions and leakage checks must be
frozen before inference. The quotas are feasibility choices, not power
calculations or representative prevalence estimates.

Conditional cost extrapolation from the measured cell:

| N20 capture scenario | Paths/window incl. overlap | Raw all-step payload/window | Planning wall/window with 2x factor | Six windows |
| --- | ---: | ---: | ---: | ---: |
| Observed 3 selected | 1,480 | 4.18GiB | 15.49min | 92.94min |
| Cap 8 + residual | 2,480 | 6.98GiB | 25.87min | 155.22min |

The formulas include observed sampling/publication, linear eight-path replay
cost, 5s load and a 2x planning factor. They exclude metadata/extra capture
profiles/filesystem overhead, and assume one shared encoder per window.
Six windows imply about25..42GiB raw tensors before those extras.
This exceeds the completed task's model/storage scope and must not be launched.
The 2x factor is not a statistical upper bound; different context supports,
residual fragmentation, serialization and cache growth can be worse.
Measured747MiB is not a bound for a retained multi-window prefix cache.
Streaming replay batches and cache eviction are prerequisites.

Negative/uncertain findings remain explicit. Mixture versus direct event
probability gaps reach 0.2360 at P0,0.1419 at P9 and 0.1000 at P10 in target N20.
One finite realization does not calibrate these estimates; conditional
plug-in MC SE can be zero for unobserved events. P10 is correlated with its
source branch, and the P10/P11 method boundary changes variance. No formal
CPD reliability, scientific effect, added-information result, cross-series
generalization or causal attention explanation is established here.
Historical H64 Phase2/Phase3 findings remain separate and unchanged.

**Single next recommendation:** after skeptical ChatGPT review, authorize
only 30 minutes of **data-only** six-series selection-manifest/QC work with
zero model draws. Falsifiers: future leakage, invalid scale, duplicate
source series, missing identity/hash. Keep rejected cells/exclusions.
A later campaign needs reviewed estimands, frozen IDs, capture architecture,
runtime/storage limits and separate researcher authorization.

## Changed paths, preservation and researcher-only Git handoff

Current evidence contains exact `git status --short`, tracked diffstat,
each changed/new path with reason, full current source hashes, all artifact
hashes and preservation checks. New untracked files do not appear in ordinary
`git diff --stat`. No files were staged or deleted.

- Core: `chronos_io.py` adds optional revision/offline/backend controls;
  new `chronos_exploratory.py` implements q50/cache/replay.
- Metrics/pipeline: new `chronos_outcomes.py` and
  `chronos_exploratory_window.py` implement fixed outcomes and bounded collection.
- Runtime: `results_io.py` handles Windows replacement; new
  `ensemble_store.py` and `windows_job.py` implement persistence/supervision.
- Scripts/config: new microbenchmark driver/config and handout refresher.
- Tests: new exploratory/loading/outcome/supervisor/CSV and
  ensemble/window/job/handout contracts.
- Docs: living status/handoff/gates/workflow/protocol annotations and navigation
  updated; decisions appended. Benchmark/evidence/tests/planning grid added.
  Prompt0 marked superseded, Prompt2 records this dated invocation.
  AGENTS now records the requested handout lifecycle. Prompt1's canonical
  files and prior reports remain untracked pending researcher review.

Final preservation checks compare 114 protected historical content hashes,
797 preexisting data/result file size+mtime records, original source ZIP,
researcher uv.lock, Git index, branch and HEAD. The 26 exact collection
source files are archived under `source_at_collection/` and hash-validated;
the original pre-correction driver was reconstructed from recorded edits and
verified against its already saved SHA. No historical statistics were rerun.
See machine-readable results in current evidence.

The26-file archive is the **initial** collection source snapshot. N20 pins
the same25 research-module hashes, but its intermediate supervisor/driver
version was not independently frozen in its summary. The old combined source
digest therefore identifies the sampling-source lineage, not the exact N20
execution driver. Final source hashes are recorded separately. This provenance
gap must be closed before a campaign; it does not change the persisted paths.

The generated `docs/chatgpt-handout/` and ZIP replace only validated managed
copies. Unexpected/manual changes cause refusal to delete. Root README source
copies live under `repository/` to avoid collision with the generated index.
Obsolete instructions/navigation were corrected or labeled; canonical historic
reports/plans/negative evidence were retained.

**Manual commands below are suggestions for the researcher, never executed
by Codex.** Review each diff/new file first; do not blindly stage uv.lock.
Exclude source ZIP, data/, result/, .venv/, handout folder/ZIP and temporary
files. uv.lock is unchanged from the researcher's setup and should be considered
separately. The following names are the recommended selective staging scope:

```powershell
git status --short
git diff -- .gitignore AGENTS.md README_CHRONOS.md docs tests code
git add -- .gitignore AGENTS.md README_CHRONOS.md docs/README.md docs/PROJECT_STRUCTURE.md docs/recherche/README.md tests/README.md
git add -- code/chronos_fpa/core/chronos_io.py code/chronos_fpa/core/chronos_exploratory.py code/chronos_fpa/metrics/chronos_outcomes.py code/chronos_fpa/pipeline/chronos_exploratory_window.py
git add -- code/chronos_fpa/runtime/results_io.py code/chronos_fpa/runtime/ensemble_store.py code/chronos_fpa/runtime/windows_job.py
git add -- scripts/runs/run_chronos_microbenchmark.py scripts/maintenance/prepare_chatgpt_handout.py configs/chronos_microbenchmark/prompt02.json
git add -- tests/chronos_fpa/unit/test_exploratory.py tests/chronos_fpa/unit/test_local_model_loading.py tests/chronos_fpa/unit/test_microbenchmark_supervisor.py tests/chronos_fpa/unit/test_outcome_calibration.py tests/chronos_fpa/unit/test_results_io.py
git add -- tests/chronos_fpa/integration/test_ensemble_store.py tests/chronos_fpa/integration/test_exploratory_window.py tests/chronos_fpa/integration/test_windows_job.py tests/chronos_fpa/integration/test_chatgpt_handout.py
git add -- docs/research codex-prompts project-chatgpt
git diff --cached --stat
git diff --cached
git commit -m "feat: validate bounded Chronos FPA prototype and research handoff"
git push
```

After the researcher commits/pushes, supply the new SHA to ChatGPT.
Before that, use the refreshed `docs/chatgpt-handout/CHATGPT_HANDOUT.md`
or `docs/chatgpt-handout.zip` as the local snapshot.
