# PROMPT 01 FOR CODEX - Integrate workflow and documentation; audit WITHOUT RUNNING the experiment

You are the coding/reproducibility partner in an ongoing PhD research project on Forking Paths Analysis of autoregressive Chronos-T5 forecasting. **Do not restart from scratch or reinterpret paper scope without reading attached versioned documents.** The provided `FPA_WORKFLOW_V2` folder is a **proposal to integrate and reconcile**, not permission to overwrite history. Current conversation explicitly authorizes workflow/doc preparation, not long computation.

## RESEARCHER-ONLY GIT CONTRACT (highest priority)

The researcher personally controls `git add`, `git commit`, and `git push`. **You must not stage files, create commits, push or pull, change branches, rewrite history or modify the Git index, even if the integration succeeds.** Do not use GitHub write APIs to bypass this restriction. Only read-only Git inspection is allowed. At the end, show `git status --short`, a summary of `git diff`, the current branch and existing HEAD, the exact paths you recommend the researcher stage, files to exclude (especially the source ZIP), a suggested commit message, and manual commands. Clearly state that the new commit SHA does not exist yet.

## INSTALLATION CONTRACT - do this automatically, no manual folder creation by the researcher

The researcher will provide the complete ZIP or extracted `FPA_WORKFLOW_V2` bundle inside the VS Code workspace. **Do not assume you can read a `sandbox:/...` ChatGPT link**. If the bundle is not physically accessible in your workspace, stop and ask the researcher to place the ZIP in the repository root (or another path accessible from VS Code). This is the **only required manual file-placement step**.

1. Determine the **actual Git repository root** using `git rev-parse --show-toplevel`; inspect `git status --short` and current branch/HEAD. Do not create a nested Git repository.
2. Locate and unpack the provided bundle in a **temporary staging directory** if needed. Check `MANIFEST.txt` and verify the required files exist before integrating anything.
3. **Create the following target directories automatically** in the repository root, if absent: `docs/research/`, `codex-prompts/`, and `project-chatgpt/`. Do not ask the researcher to create these folders.
4. Install the proposal files in their canonical locations, **without leaving a nested `FPA_WORKFLOW_V2/docs/...` tree as the official location**:
   - `FPA_WORKFLOW_V2/docs/research/*.md` -> `<repo>/docs/research/*.md`
   - `FPA_WORKFLOW_V2/codex-prompts/*.md` -> `<repo>/codex-prompts/*.md`
   - `FPA_WORKFLOW_V2/project-chatgpt/*.md` -> `<repo>/project-chatgpt/*.md`
   - `FPA_WORKFLOW_V2/AGENTS.md` -> **merge into** `<repo>/AGENTS.md` (never blindly overwrite)
   - `FPA_WORKFLOW_V2/README_START_HERE.md` -> `<repo>/docs/research/README_WORKFLOW_V2.md` (or link to a preexisting equivalent)
5. For **new paths**, create and populate them automatically. For **existing paths**, read the actual current content and merge conservatively: preserve preexisting experimental facts, historical decisions, headings and user edits. In `FPA_DECISIONS.md`, append or supersede with dated entries, not historical deletion. For `AGENTS.md`, integrate compatible instructions and preserve existing operational rules. Never overwrite uncommitted user modifications.
6. If a merge is unambiguous, perform it and explain the changes in the integration report. **Ask for user approval only for substantive conflicts or irreversible/destructive changes**; stop rather than guess on those individual files. Safe creation of missing folders and files does not need another confirmation.
7. Leave original phase reports, old plans, raw artifacts and executable code unchanged. Do not run `git add`, `git commit`, `git push` or any other Git-writing operation; do not download models or generate trajectories. The newly staged ZIP/extracted bundle is source material, not a replacement for the repository; flag duplicate staged material so it is not accidentally committed twice.
8. Verify that all canonical files exist, internal Markdown paths resolve, and no required scientific source vanished. List every installed, merged, skipped and conflicted path in `FPA_INTEGRATION_REPORT.md`, plus branch/commit and remaining uncommitted changes.

**End state:** the researcher should not need to move individual Markdown files or create any directories manually. Codex establishes the documentation/workflow baseline inside the *existing* repository, subject only to genuinely conflicting files.

## Objectives, in this order

**(1) Create / optimize the long-term Codex <-> ChatGPT <-> researcher workflow** with repository-root `AGENTS.md`, versioned scientific documents, short evidence handoffs, atomic run checkpoints and an external-review gate after each meaningful iteration. Existing source code and run artifacts remain untouched.

**(2) Produce/merge authoritative research documents** preserving all current scientific considerations, negative findings, decisions, experimental configuration and legacy provenance. Do not rely on conversation memory as an authoritative source. Use supplied files under `docs/research/` as the proposed updated text and reconcile them against the existing checkout and actual reports.

## Mandatory first reading

1. New `README_START_HERE.md` and `AGENTS.md` (merge with preexisting AGENTS, never clobber).
2. `docs/research/FPA_NORTH_STAR.md`, `FPA_STATUS.md`, `FPA_DECISIONS.md`, `FPA_PROTOCOL_EXPLORATORY.md`, `FPA_HYPOTHESES.md`, `FPA_TECHNICAL_GATES.md`, `FPA_REFERENCES.md`.
3. Local original sources: `docs/CHRONOS_PHASE1.md` (if exists), `docs/CHRONOS_PHASE2.md`, `docs/CHRONOS_PHASE3_DESIGN.md`, prior research plan under `docs/future works/`, and the exact pipeline/run manifests referenced therein.
4. Relevant code/config for sampling policy, candidate selection, token positions, persistence/checkpoint logic, CPU/GPU and hidden state capture. Focus on checking that the new docs are possible, **not re-running the whole historical audit**.

## Explicit scientific invariants

- Paper 1 investigates information from **output-token** interventions in generative TSFMs beyond entropy/probability and direct numerical jump. It does NOT require UCR input-attribution or attack success.
- Keep C512/H32, FPA b0..9, N20/group, q50 90% target or max8 (greedy included), residual mixture, independent null, fixed22/full W1+ED, per-window CPD P0..15 from weighted dense branch ensembles + N60 direct P11..15. The Stage A M4 H64/N50 proposal is separate and unexecuted.
- Encoder reuse and decoder caching must **preserve** conditioning on all previous generated tokens; maximizing white-box capture requires benchmark/parity, not silent omissions.
- Do not claim that the exact grid, new model optimizations or CPD inference are implemented merely because a protocol now exists.

## Tasks permitted RIGHT NOW

A. Inspect Git status, real local docs and code. Identify missing supplied files and existing overlapping AGENTS/instructions. Suggest a backup/manual commit if needed; all staging/committing/pushing belongs to the researcher and is forbidden for Codex.
B. Integrate the proposed document set into the actual repo paths in a conflict-aware way. **Record merges/diffs and present them in the report; ask approval only for genuine conflicting or irreversible replacements**. For existing living docs, merge old decisions/status then apply the superseding 2026-11-19 entries; append rather than erase scientific history. Keep the old Phase1/2/3 reports and old scientific plan unchanged as sources. For unresolved differences add `docs/research/FPA_INTEGRATION_CONFLICTS.md` rather than guessing.
C. Inspect whether `H=32`, q50-conditioned residual mixture, direct CPD, prefix caching and all-layer white-box capture are available in code; report gaps and test strategy. **No implementation of these major changes in this prompt.**
D. Audit existing checkpoint format for atomic commit, partial recovery and concurrent read-only analysis. Propose concrete safe design with a cost/quality checklist.
E. Update `FPA_STATUS.md` and `FPA_HANDOFF.md` with *actually verified* repo facts and the complete report paths. Do not mark any proposed run as completed.
F. Run only formatting/document/path checks that do not load Chronos for inference. Optionally run existing **pure offline** unit tests if quick and explicitly disclose scope and duration; do not run data generation.

## Forbidden in this prompt

- Chronos inference, Stage A, a 24h grid, model downloads, training/fine-tuning, repo-wide refactor, dataset downloads, cloud spend, ad hoc dependency upgrades, overwriting historical run outputs, claiming provenance absent manifests.
- Automatically changing frozen estimator definitions, q50 policy, H/N/K, source-series selection or experiment scope.

## Deliverables / STOP condition

1. Short `FPA_INTEGRATION_REPORT.md`: file mapping, merge/conflict decisions, Git diff, actual source facts, implementation gap list, threats to correctness, recommended next bounded work, and a **researcher-only Git checklist**: recommended staging paths, excluded artifacts, `git diff --cached` inspection, suggested commit message and manual push. Do not execute these commands.
2. Updated living docs and `FPA_HANDOFF.md` no longer than ~800 words; every research claim labeled observed/suggested/hypothesis.
3. A **proposed** Phase-0 bounded benchmark/smoke-test prompt with planned runtime ceiling and scientific success/failure gates; do not run it.
4. Explicit final line: `NO NEW MODEL INFERENCE RUN; AWAITING SCIENTIFIC REVIEW / USER AUTHORIZATION`.

Stop. Ask the researcher to send the integration report + handoff to ChatGPT for a skeptical review before proceeding.
