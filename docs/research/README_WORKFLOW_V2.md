# FPA / Chronos - Research workflow v2

**Snapshot: 2026-11-20.** Prompt 1 integration and the separately authorized,
bounded Prompt 2 implementation/benchmark are complete. Read the current
[benchmark report](BENCHMARK_REPORT.md), [status](FPA_STATUS.md) and
[handoff](FPA_HANDOFF.md). This does not authorize a multi-series campaign.

At each completed prompt, run
`scripts/maintenance/prepare_chatgpt_handout.py` with the repository venv.
It replaces validated generated copies in `docs/chatgpt-handout/` and the
sibling ZIP. Upload `CHATGPT_HANDOUT.md` for the current review. Its document
links point to internal sections; the ZIP also includes transitively linked
Markdown guides and supporting documentary files. Exported copies convert
unbundled code/data links to explicit repository references. Canonical source
hashes and generated-copy hashes are recorded separately.
Run `scripts/maintenance/prepare_chatgpt_handout.py --check-links` for a
read-only audit of canonical local file and heading links.
Keep generated copies ignored.
Canonical historical reports/plans remain available. Superseded proposals are
labeled and obsolete navigation is corrected.


## Canonical navigation after integration

Paths written as repository paths below are relative to the Git root; bare
research filenames refer to this directory. Literal example/future artifact
paths do not imply those artifacts exist.

- [Root operating rules](../../AGENTS.md)
- [North star](FPA_NORTH_STAR.md), [status](FPA_STATUS.md), [decisions](FPA_DECISIONS.md)
- [Protocol](FPA_PROTOCOL_EXPLORATORY.md), [hypotheses](FPA_HYPOTHESES.md), [technical gates](FPA_TECHNICAL_GATES.md)
- [References](FPA_REFERENCES.md), [French synthesis](NOTE_SYNTHESE_SCIENTIFIQUE_FR.md)
- [Integration report](FPA_INTEGRATION_REPORT.md), [implementation audit](FPA_IMPLEMENTATION_AUDIT.md), [pending choices](FPA_INTEGRATION_CONFLICTS.md), [evidence](FPA_INTEGRATION_EVIDENCE.json), [handoff](FPA_HANDOFF.md)
- [Integration prompt (completed)](../../codex-prompts/PROMPT_01_INTEGRATE_AND_AUDIT.md), [Phase-0 proposal (superseded)](../../codex-prompts/PROMPT_00_BOUNDED_BENCHMARK.md), [Prompt 2 invocation/template](../../codex-prompts/PROMPT_02_BENCHMARK_AND_PREPARE.md), [iteration template](../../codex-prompts/PROMPT_NEXT_ITERATION.md)
- [ChatGPT instructions](../../project-chatgpt/PROJECT_INSTRUCTIONS.md), [new-chat message](../../project-chatgpt/NEW_CHAT_START.md), [research cycle](../../project-chatgpt/CYCLE.md)

**Evidence convention:** observed = inspected artifacts or explicitly attributed
source reports; suggested = unimplemented work/design; hypothesis = scientific
claim awaiting evidence. This guide proposes workflow, not research findings.

## Purpose

Use a version-controlled scientific protocol and a strict Codex -> ChatGPT ->
researcher feedback loop. Prevent context loss, unapproved compute,
methodology drift and artificial claims of evidence. The supplied proposal was
integrated on November 19. Observations belong in current status/handoff;
candidate design remains subject to scientific review and scoped approval.

## Canonical architecture

1. **Local Git repository:** versioned source of truth for code, protocols, small run manifests, validation and decision history. Large immutable raw samples/checkpoints can live outside Git, referenced through hashes and paths in manifests.
2. **Codex inside VS Code:** implementation, test, bounded execution, QA, atomic checkpoints, evidence-based reports.
3. **ChatGPT Project "FPA implementation":** scientific review, research synthesis, checks against paper scope, next-step design. A Project source is a **snapshot**, not a live mirror of local Git files.
4. **Researcher:** approve scientific changes, collection scope, hours, hardware and any model inference; decide when to stop; **personally run all Git staging, commits and pushes**.

## Files and reading order

| Relative path | Role | Change frequency |
|---|---|---|
| `AGENTS.md` | Hard operating rules for Codex; merge into existing `AGENTS.md` if it exists | Rare |
| `docs/research/FPA_NORTH_STAR.md` | Central research question, paper contributions, novelty and non-goals | Rare, approval only |
| `docs/research/FPA_PROTOCOL_EXPLORATORY.md` | Candidate experimental design and estimands | Before each approved run |
| `docs/research/FPA_HYPOTHESES.md` | Scientific hypotheses, falsifiers, alternative explanations and benchmarks | After scientific review |
| `docs/research/FPA_TECHNICAL_GATES.md` | Parity/caching/white-box/checkpoint/analysis contracts | On implementation review |
| `docs/research/FPA_STATUS.md` | Actual completed work and evidence | Every iteration |
| `docs/research/FPA_DECISIONS.md` | Append-only approved decisions, supersession and pending authorizations | Every decision |
| `docs/research/FPA_HANDOFF.md` | Compact export of Codex results for ChatGPT | Every iteration |
| `docs/research/FPA_REFERENCES.md` | Source documents, literature, source-of-truth and provenance | On literature update |
| `codex-prompts/PROMPT_01_INTEGRATE_AND_AUDIT.md` | **First Codex prompt. Read and reconcile only; no large run** | Once |
| `codex-prompts/PROMPT_02_BENCHMARK_AND_PREPARE.md` | Second bounded technical test; only after explicit approval | On authorization |
| `codex-prompts/PROMPT_NEXT_ITERATION.md` | Reusable next-work template | Every iteration |
| `project-chatgpt/PROJECT_INSTRUCTIONS.md` | Short project-specific ChatGPT instructions | Rare |
| `project-chatgpt/NEW_CHAT_START.md` | Copy into new ChatGPT Project conversation | At each new scientific chat |

## Original setup procedure (completed 2026-11-19; retained as reference)

1. Inspect and, if desired, **manually commit/back up** the current repo first. Codex must not stage, commit, push or alter Git history. Do not replace existing plans automatically.
2. Place **the single ZIP** in a location Codex can read from your VS Code workspace (e.g. repository root). Give Codex `PROMPT_01_INTEGRATE_AND_AUDIT.md` from the bundle. **No manual folder creation or per-file copying is required**; Codex creates the canonical directories and installs the files, reconciling existing versions. A ChatGPT `sandbox:/...` download URL alone is not sufficient for VS Code Codex.
3. Codex should inspect existing `AGENTS.md`, `docs/future works/FPA_CHRONOS_RESEARCH_PLAN (1).md`, `docs/CHRONOS_PHASE2.md`, `docs/CHRONOS_PHASE3_DESIGN.md` and relevant code, then propose a merge/diff. Older documents remain historical, not silently rewritten.
4. Codex automatically installs new files and performs unambiguous, non-destructive merges; it asks for approval only if substantive conflicts or destructive changes arise. It records conflicts in the handoff, runs documentation checks, and stops. **No inference or downloads in this first step. No `git add`, `git commit` or `git push`.**
5. **Researcher Git gate:** review `git status` and the Codex diff; inspect new files and `.gitignore`, especially the ZIP staged at the repository root. Selectively run `git add <approved files>` (or `git add -p`), inspect `git diff --cached`, then personally run `git commit -m "docs: integrate FPA research workflow"` and `git push`. Do **not** use `git add -A` blindly. Codex may suggest these commands but never execute them.
6. **After your push:** tell ChatGPT the branch/commit or ask it to verify the remote HEAD. Only pushed files are visible through GitHub; local changes remain invisible to ChatGPT unless separately supplied.
7. Create a **new conversation inside the existing ChatGPT Project**. Add as project reference sources the current `FPA_NORTH_STAR.md`, `FPA_STATUS.md`, `FPA_DECISIONS.md`, `FPA_PROTOCOL_EXPLORATORY.md`, `FPA_HYPOTHESES.md`, `FPA_HANDOFF.md`, original paper and milestone reports. Prefer a snapshot bundle (ZIP plus named critical docs) to a dozen inconsistent duplicate versions.
8. At each **meaningful milestone**, attach the *new* `FPA_HANDOFF.md` and its full scientific report to ChatGPT, ask for skeptical review. The review yields one bounded Codex task with explicit compute/stop limits. Update Project sources on milestones, not every trivial code change.
9. Codex records the starting Git HEAD and UTC time in its handoff. **After you commit/push**, the researcher supplies the new commit SHA for ChatGPT verification; Codex must not invent the future SHA.

## One source of truth; no double-editing

The Git documents are authoritative. ChatGPT proposes changes and evaluates them; **Codex edits approved working-tree files** in the repo, while **the researcher exclusively stages, commits and pushes**. ChatGPT Project uploads are immutable snapshots in this workflow. Whenever a document conflicts with a run manifest or actual artifacts, the **manifest, raw data and code revision** take precedence as evidence; flag the disagreement for correction.

## Explicitly not yet authorized

The 24h+ exploratory campaign, Stage A M4 new inference, optional larger CPD, new model/architecture, cloud/GPU procurement, fine-tuning, adversarial runs, official benchmark claims and manuscript drafting. These can be decided separately.
