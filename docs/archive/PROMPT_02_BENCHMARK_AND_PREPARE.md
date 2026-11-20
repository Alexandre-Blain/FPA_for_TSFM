# PROMPT 02 FOR CODEX - Bounded correctness/performance smoke tests (ONLY AFTER APPROVAL)

**Invocation authorized 2026-11-20:** researcher approved this task and chose
four hours for implementation/tests and at most thirty minutes of model work.
Use `configs/chronos_microbenchmark/prompt02.json` for the concrete local CPU,
single cached M4 context, memory/storage limits and no-download scope.
The historical template text below remains for future invocations; its earlier
unapproved status is superseded only for this specifically bounded task.

**Reusable template:** the scoped 2026-11-20 invocation is recorded above.
For a future invocation, the researcher must supply its runtime budget,
hardware/disk limits, approved changed files and micro-data contexts. Stop if
those fields are blank. A completed benchmark does not authorize a campaign.

Approval ID: `[RESEARCHER_APPROVAL_ID]`
Runtime cap wall-clock: `[MINUTES]`
Hardware and memory/disk ceiling: `[HARDWARE, RAM, DISK]`
Allowed microcontexts/series: `[EXACT CONTEXT IDS]`
Allowed installations or downloads: `[EXACT LIST or NONE]`

Researcher-only Git rule: do not run `git add`, `git commit`, `git push`, pull, checkout, merge, reset, stash or any other Git-writing operation. Leave all changes unstaged; provide the researcher a precise status/diff, safe staging-path suggestions and a proposed commit message.

Read project `AGENTS.md`, north star, actual status/decisions, current candidate protocol and technical gates. Implement only code necessary for a **micro** validation of: H32 strict postfork distances, true q50 candidate+residual policy, direct P11..15 outcome sampling, dense branch mixtures P0..10, encoder reuse, decoder caching/batching, exhaustive attention/hidden extraction, replay, atomic checkpoint/restart and committed-only analysis.

**Before any generation:** tests must validate forced-token indexing, q50 weights/residual mass 1.0, prefix conditioning, numerical expected W1/ED, and the P_{t,g}=P_{t+1} identity at the distribution level. Compare optimized vs reference decoder logits and q50 probabilities under frozen precision/backend. If parity fails, fall back rather than silently changing the estimand.

Profile minimal vs all-state/all-attention capture and caching/batching toggles at fixed microcontexts. Report actual size/time/memory for each variant, and identify if attention output changes kernels. Do not make any unapproved campaign grid decisions or launch Stage A. Create a **proposed** production grid with representative and diverse strata and target source-series counts calculated from measured throughput; no live campaign launch.

Persist all micro-provenance and outputs separately from future campaign. Produce `BENCHMARK_REPORT.md`, tests, measured parity, q50 invariants, peak memory/storage, checkpoint crash simulation, expected cost per dense window and direct CPD window, scientific risks, code diff and a bounded next proposal. Update status/decision/handoff (approved actual decisions only), then STOP at the researcher authorization gate.
