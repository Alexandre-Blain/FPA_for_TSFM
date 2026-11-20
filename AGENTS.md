# FPA_for_TSFM - Agent Entry Point

This is a research workspace for Forking Paths Analysis of time-series
foundation models. The active implementation uses original Chronos-T5 models.

Read `README.md`, `docs/reference/README_CHRONOS.md`, `docs/reference/PROJECT_STRUCTURE.md` and
`tests/README.md` before changing the workflow.

## Layout

Research modules live in `code/chronos_fpa/`, organized by function. Scripts
import `bootstrap.py` to configure these plain module folders. Do not introduce
an installable research package just to resolve imports.

Experiments use JSON configurations in `configs/` and launchers in
`scripts/runs/`. Analysis and plotting utilities are in `scripts/viz/`.

## Validation

Install the development environment with `uv sync --group dev`, then run:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Tests are offline: no model downloads or inference runs are needed.

## Research artifacts

Preserve existing datasets, run outputs, checkpoints and historical reports.
Partial runs may contain useful evidence. Keep generated artifacts out of Git
and do not rewrite historical outputs as a side effect of source maintenance.

There is no TimesFM library or forecasting skill in the active repository.
Earlier TimesFM code is archived in the original workspace.

## Current research workflow

Start with the single [documentation index](docs/README.md) and the
[workflow](docs/research/README_WORKFLOW_V2.md). Six active documents live in
docs/research/; methods and useful reports in docs/reference/; completed prompts,
superseded plans and old audits in docs/archive/. Archives are provenance,
never current execution instructions. The [current task](codex-prompts/CURRENT_TASK.md)
records the authorized pilot, presently paused by the researcher for maintenance.

## Before work

- For substantial tasks read, in order: `docs/research/FPA_NORTH_STAR.md`, `docs/research/FPA_STATUS.md`, `docs/research/FPA_DECISIONS.md`, then `docs/research/FPA_PROTOCOL_EXPLORATORY.md` and the relevant original reports/code. Do not reread entire archive for trivial tasks.
- The Git checkout plus run manifests/checksums/raw data are evidence. Research summaries are versioned interpretations. Never claim a proposed experiment ran based on its description.
- Core Paper 1 question: what does conditional forking of plausible autoregressive output tokens reveal about future **numerical trajectory distributions**, beyond local probability/entropy and direct numeric jump?
- C1 rigorous measurement; C2 cross-series and cross-position empirical characterization; C3 conditional-ensemble temporal interpretation. No specific positive outcome is assumed. CPD/white-box/sampling efficiency are exploratory additions to these pillars.

## Scientific guardrails

1. Distinguish generated-token intervention from perturbing historical input, and from UCR classifier attribution. UCR is no longer a required Paper 1 validation.
2. Keep the **greedy prefix and reference branch** distinct from **stochastically sampled continuations**. Correctly condition decoder on all previous tokens even when encoder outputs are cached.
3. Explicitly name the **effective top-50 sampling policy** `q50` (valid-token mask, temperature 1, top-p 1). Store untruncated `p_sel` separately, never mix probability measures when building CPD mixtures.
4. W1/ED must compare **strictly post-fork** numeric continuations, forced coordinate excluded; save direct numeric jump `J` separately. Analyze fixed 22-step and full remaining suffix; do not treat their averages as the same estimand.
5. For CPD use the **same fixed outcome per window**, probability mixtures at dense positions, directly sampled distributions at later positions, and uncertainty/estimator-boundary controls. CPD-on-W1-horizon profiles is a different object.
6. Keep source-series clusters, overlapping windows, Monte Carlo ensembles and within-path temporal dependence distinct. Resampling a finite sample does not create independent model draws. Do not claim confirmatory inference from selected cases.
7. Observe negative findings, contradictory results, near-null branches, strong controls; never cherry-pick successful examples, manipulate thresholds after seeing results without labeling it exploratory, or promote score ratios to statistical tests.
8. White-box attention is a measurement, not by itself causal explanation. Test replay, full capture and its effect on the decoder before drawing conclusions.
9. A dense reference at b=0..9 is for **later sparse-screening counterfactual evaluation**; do not replace the primary collection by sparse selected positions without user approval.

## Git ownership: researcher only (mandatory on every task)

- **Only the researcher operates Git's staging index, commits, and remote synchronization.** Codex must NEVER run `git add`, `git commit`, `git push`, `git pull`, `git merge`, `git rebase`, `git checkout`/`git switch`, `git stash`, `git reset`, `git clean`, create branches/tags or alter Git configuration. Do not call GitHub write actions to bypass this rule. No exceptions unless the researcher explicitly revises this standing rule in a new instruction.
- Codex MAY use **read-only Git inspection**: `git status`, `git diff`, `git diff --cached`, `git log`, `git show`, `git branch --show-current`, `git rev-parse`, and `git ls-files`; no staging or commit side effects. Codex edits the worktree and reports exactly what changed.
- At every handoff, supply (a) current branch and **pre-user-commit HEAD**, (b) `git status --short`, (c) changed/new/deleted paths with reason, (d) warnings about files to keep untracked, (e) suggested **selective** `git add` commands and a commit-message proposal, without executing them. Indicate clearly that any new commit SHA is unknown until the researcher commits.
- The researcher reviews diffs, chooses files to stage, runs `git add` / `git commit` / `git push`, and then shares the resulting commit SHA or asks ChatGPT to verify the pushed HEAD. Never suggest `git add -A` as a safe default; large raw datasets, outputs, checkpoints, ZIP staging bundles, credentials, and unpublished private material must be explicitly reviewed before tracking.
- An **atomic/completed run checkpoint** is a locally finalized data artifact or manifest; it does **not** imply a Git commit. Concurrent analysis reads finalized checkpoints, even when they have not been committed to Git.

## Scope / execution discipline

- Work only on the **bounded task explicitly approved in the current prompt**. Writing a protocol, discussing a 24h campaign, or adding this AGENTS file is not run authorization.
- No nontrivial inference, dataset download, dependency changes, cloud compute, training, fine-tuning, new models, or execution > specified ceiling without explicit user authorization.
- Never overwrite historical runs or scientific source content. Researcher-authorized documentation maintenance may move reports and rebase links while preserving their content and provenance. Superseded plans belong in docs/archive/.
- Prioritize parity and measured bottlenecks before optimizing. Do not assume T5 encoder cache, decoder KV cache or batching improve throughput until measured. Demonstrate that cached decoding preserves conditioning on preceding generated tokens.
- Persist per-branch raw tokens/numeric paths, policy metadata, logits/activation availability, hashes, actual runtimes and completed status. Atomic checkpoints must be safe under crashes. Analysis must read **atomically finalized checkpoints only**, not partially written files; these do not require a Git commit.
- For a long campaign, predefine the experiment grid and stopping budget; adaptive expansions must be logged and distinguished from the prospectively sampled portion. Separate the inference process from the scientific review process.

## End-of-iteration contract

For every substantive iteration:
- Update `FPA_STATUS.md` with **actual** progress, code/test states, blockers and paths.
- Append to `FPA_DECISIONS.md` only real researcher decisions (including supersessions); do not invent an approval.
- Refresh `FPA_HANDOFF.md` with a <=800-word executive summary pointing to a full report and all manifests, Git branch/pre-commit HEAD/working-tree status, dates, counts, units, elapsed, tests, limitations and next gate. Codex must never stage, commit or push.
- Report tests actually executed, scientific claims with levels `observed / suggested / hypothesis / refuted`, artifacts and changed files. Provide exactly one next bounded recommendation with cost, falsifier and user approval gate.
- Stop at the agreed gate. Do not auto-launch the next stage.

## Historical anchors

- Bigelow et al., *Forking Paths in Neural Text Generation*, ICLR 2025, arXiv:2412.07961.
- Local legacy plan: `docs/archive/FPA_CHRONOS_RESEARCH_PLAN (1).md` (verify actual path).
- Reports: `docs/reference/CHRONOS_PHASE2.md`, `docs/reference/CHRONOS_PHASE3_DESIGN.md`.
- Completed run: `result/phase2_controlled_pilot_20261116_195533/`.
- Offline controls: `result/phase3_offline_controls_20261117_175121/`.

## Refreshable ChatGPT handout (2026-11-20)

- At each completed prompt, run `scripts/maintenance/prepare_chatgpt_handout.py`.
  It replaces generated upload copies in `docs/chatgpt-handout/` and produces
  `docs/chatgpt-handout.zip`, including changed/new active documents and needed
  scientific references. Archives are excluded even when changed or linked.
  The combined `CHATGPT_HANDOUT.md` is the easy upload entry.
- Keep these disposable copies ignored. Edit canonical documents, never the
  handout copies. The refresher refuses to delete unexpected or manually edited
  files and validates that all managed paths stay in its dedicated folder.
- Clean obsolete navigation and redundant generated copies; preserve historical
  scientific reports, decisions, source plans and run artifacts as provenance.
  A superseded proposal should be clearly labeled instead of silently erased.
- Prompt 2 was authorized on 2026-11-20 with four hours for implementation/tests
  and at most thirty minutes of local model work. Its specific invocation and
  results belong in the current benchmark report and append-only decisions.
