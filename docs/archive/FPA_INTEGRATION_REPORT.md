# FPA workflow integration report - 2026-11-19

**Observed:** 2026-11-19T15:15:41Z. Repository
`C:/Users/alexandre.blain/dev/FPA_for_TSFM`; branch `main`; existing HEAD
`687c34f5f144476ea530c4210d3ed294c3b543e9`.
Initial worktree clean. **The new commit SHA does not exist yet.**
No Git index/history/remote changes, new model inference, downloads or
dependency installation by Codex.

## File mapping and reconciliation

Source paths below are relative to the temporary extracted bundle root.
All18 manifest entries were present. Created the three canonical directories
automatically; no nested proposal tree is the official source.

| Bundle source | Canonical target | Action |
| --- | --- | --- |
| `docs/research/FPA_DECISIONS.md` | `docs/research/FPA_DECISIONS.md` | installed; original rows retained, dated addendum |
| `docs/research/FPA_HANDOFF.md` | `docs/research/FPA_HANDOFF.md` | installed; replaced starter with verified state |
| `docs/research/FPA_HYPOTHESES.md` | `docs/research/FPA_HYPOTHESES.md` | installed; evidence/status annotation |
| `docs/research/FPA_NORTH_STAR.md` | `docs/research/FPA_NORTH_STAR.md` | installed; evidence/status annotation |
| `docs/research/FPA_PROTOCOL_EXPLORATORY.md` | `docs/research/FPA_PROTOCOL_EXPLORATORY.md` | installed; evidence/status annotation |
| `docs/research/FPA_REFERENCES.md` | `docs/research/FPA_REFERENCES.md` | installed; portable evidence/metadata annotation |
| `docs/research/FPA_STATUS.md` | `docs/research/FPA_STATUS.md` | installed; replaced starter with verified state |
| `docs/research/FPA_TECHNICAL_GATES.md` | `docs/research/FPA_TECHNICAL_GATES.md` | installed; evidence/status annotation |
| `docs/research/NOTE_SYNTHESE_SCIENTIFIQUE_FR.md` | `docs/research/NOTE_SYNTHESE_SCIENTIFIQUE_FR.md` | installed; evidence/status annotation |
| `codex-prompts/PROMPT_01_INTEGRATE_AND_AUDIT.md` | `codex-prompts/PROMPT_01_INTEGRATE_AND_AUDIT.md` | installed |
| `codex-prompts/PROMPT_02_BENCHMARK_AND_PREPARE.md` | `codex-prompts/PROMPT_02_BENCHMARK_AND_PREPARE.md` | installed; narrower next-task link |
| `codex-prompts/PROMPT_NEXT_ITERATION.md` | `codex-prompts/PROMPT_NEXT_ITERATION.md` | installed |
| `project-chatgpt/CYCLE.md` | `project-chatgpt/CYCLE.md` | installed |
| `project-chatgpt/NEW_CHAT_START.md` | `project-chatgpt/NEW_CHAT_START.md` | installed |
| `project-chatgpt/PROJECT_INSTRUCTIONS.md` | `project-chatgpt/PROJECT_INSTRUCTIONS.md` | installed |
| `README_START_HERE.md` | `docs/research/README_WORKFLOW_V2.md` | installed; canonical name; current snapshot/navigation |
| `AGENTS.md` | `AGENTS.md` | merged; original bytes preserved as prefix |

Additional **created** paths:
`docs/research/FPA_INTEGRATION_REPORT.md`,
`docs/research/FPA_IMPLEMENTATION_AUDIT.md`,
`docs/research/FPA_INTEGRATION_CONFLICTS.md`,
`docs/research/FPA_INTEGRATION_EVIDENCE.json`,
`codex-prompts/PROMPT_00_BOUNDED_BENCHMARK.md`.

**Skipped installation:** bundle `MANIFEST.txt` remains source metadata in
temporary storage; its entries/hashes are recorded in evidence. Source
`FPA_WORKFLOW_V2_MANUAL_GIT.zip` stays ignored and untouched. No duplicate
extracted bundle was installed in the repository. Original AGENTS bytes are
preserved as its prefix. Historical Phase1/2/3 reports, both old files under
`docs/future works/`, legacy handoff/future ideas, code/configs/tests and all
research artifacts were preserved. No canonical file is skipped or blocked.

**Reconciled:** current prompt permits candidate CPD/white-box design and a
proposed technical Phase0, superseding only incompatible old scope restrictions.
It does not approve their execution. Existing H64/N50 results and separate
StageA remain intact. No scientific conflict was silently resolved by changing
estimators or configuration. Unresolved candidate ties, IQR, CPD calibration,
budgets and checkpoint robustness are in
[reconciliation log](FPA_INTEGRATION_CONFLICTS.md).

## Verified facts, gaps and correctness risks

**Observed:** seven Phase2 groups, 1,400 paths, 78,600 suffix values, seven NPZs
(78,497 bytes); all49 array checksums and18 Phase3 source hashes match.
Phase3 is offline only. September summary hash is unchanged.
These checks validate integrity, not new statistical conclusions.

**Observed:** low-level H32 and independent nulls exist. The cumulative-q50
90%/max8/residual policy, signed J/fixed22 export, P0..15 CPD driver, encoder/KV
reuse, exhaustive white-box persistence and token replay remain gaps.
Current decoder preserves full-prefix conditioning; q50 threshold ties can
yield more than50 tokens. Current checkpoints publish whole forks.
`recover()` rewrites exports; existing CSV-based analysis lacks an immutable
concurrent-reader contract. See the complete
[implementation audit and proposed safe design](FPA_IMPLEMENTATION_AUDIT.md).

**Observed (historical reports):** selected effects coexist with null noise,
ranking instability, confounded entropy and unsupported broad morphology.
**Hypothesis:** additional information beyond J/p/entropy remains unestablished.
**Suggested:** original-series clustering, residual accounting, fixed outcomes,
estimator-boundary calibration and parity gates must precede collection.

## Checks actually executed

- Standard-library manifest/table/RNG/NPZ integrity checks: **passed**, 2.954s.
  No Chronos import, neural inference or analysis regeneration.
- Researcher installed `.venv` during this task. Existing offline suite with
  Hugging Face offline flags and socket-blocking test fixtures:
  **223 passed,1 failed in80.46s**.
- Failure: `test_paper1_resume_and_continuous_ensembles_match`,
  `results_io.py:83`, WinError5 at `os.replace` of a recovered steps CSV.
  One targeted repeat: **1 passed in9.60s**. Cause unresolved; do not call the
  full suite green. Directory publication retries locks, file replacement does
  not. No source or test changes were made.
- Final checks: all22 canonical paths exist,21 Markdown files and90 internal
  links pass; no whitespace/fence issue;15 prior decision-table lines preserved.
  All213 protected file hashes and the797-file data/result size/mtime inventory
  are unchanged. Git index hash is unchanged and staging is empty. See
  [machine-readable evidence](FPA_INTEGRATION_EVIDENCE.json) for exact counts
  and scope. No local Bigelow PDF was provided; six primary literature landing
  pages were checked for metadata only, with citations in
  [references](../reference/FPA_REFERENCES.md).

## Researcher-only Git review

Git diff covers tracked files only: `AGENTS.md` gains62 lines; the21 new
workflow/audit files are untracked and must be read separately. No tracked
source/config/test/historical-report change or deletion. A final status snapshot
is below. The researcher's additional `uv.lock` is preserved and excluded from
this docs-only staging recommendation.

Exact recommended staging paths, all within the reviewed canonical set:

- `AGENTS.md`
- `codex-prompts/PROMPT_00_BOUNDED_BENCHMARK.md`
- `codex-prompts/PROMPT_01_INTEGRATE_AND_AUDIT.md`
- `codex-prompts/PROMPT_02_BENCHMARK_AND_PREPARE.md`
- `codex-prompts/PROMPT_NEXT_ITERATION.md`
- `docs/research/FPA_DECISIONS.md`
- `docs/research/FPA_HANDOFF.md`
- `docs/research/FPA_HYPOTHESES.md`
- `docs/research/FPA_IMPLEMENTATION_AUDIT.md`
- `docs/research/FPA_INTEGRATION_CONFLICTS.md`
- `docs/research/FPA_INTEGRATION_EVIDENCE.json`
- `docs/research/FPA_INTEGRATION_REPORT.md`
- `docs/research/FPA_NORTH_STAR.md`
- `docs/research/FPA_PROTOCOL_EXPLORATORY.md`
- `docs/research/FPA_REFERENCES.md`
- `docs/research/FPA_STATUS.md`
- `docs/research/FPA_TECHNICAL_GATES.md`
- `docs/research/NOTE_SYNTHESE_SCIENTIFIQUE_FR.md`
- `docs/research/README_WORKFLOW_V2.md`
- `project-chatgpt/CYCLE.md`
- `project-chatgpt/NEW_CHAT_START.md`
- `project-chatgpt/PROJECT_INSTRUCTIONS.md`

Exclude the source ZIP, any extracted/temp bundle, `.venv/`, `uv.lock` (review
separately), caches, datasets, models, `result/`, checkpoints and generated
outputs. Existing ignore rules already cover ZIPs and research outputs; no
ignore rule was changed. Do not force-add ignored material or use `git add -A`.

**Manual commands for the researcher only; Codex has not executed them:**

```powershell
git status --short --untracked-files=all
git diff -- AGENTS.md
git ls-files --others --exclude-standard
git add -- AGENTS.md docs/research codex-prompts project-chatgpt
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "docs: integrate FPA research workflow and static audit"
git push
git rev-parse HEAD
```

The selective directory command is appropriate only after confirming that its
contents exactly match the listed paths. Inspect the cached diff and exclude
any unwanted or newly arriving files before committing. Share the actual new
SHA after the researcher commits/pushes; this report cannot predict it.

## Next bounded gate

**Suggested:** send this report, [handoff](../research/FPA_HANDOFF.md) and full audit to
ChatGPT for skeptical scientific review. The sole next recommendation is the
[proposed Phase0](PROMPT_00_BOUNDED_BENCHMARK.md), with
30minutes total and any separately approved cached-model portion capped at180s.
Checkpoint/access-denial readiness is a prior gate; no automatic sampling,
implementation campaign or StageA follows.

## Final worktree snapshot

```text
 M AGENTS.md
?? codex-prompts/PROMPT_00_BOUNDED_BENCHMARK.md
?? codex-prompts/PROMPT_01_INTEGRATE_AND_AUDIT.md
?? codex-prompts/PROMPT_02_BENCHMARK_AND_PREPARE.md
?? codex-prompts/PROMPT_NEXT_ITERATION.md
?? docs/research/FPA_DECISIONS.md
?? docs/research/FPA_HANDOFF.md
?? docs/research/FPA_HYPOTHESES.md
?? docs/research/FPA_IMPLEMENTATION_AUDIT.md
?? docs/research/FPA_INTEGRATION_CONFLICTS.md
?? docs/research/FPA_INTEGRATION_EVIDENCE.json
?? docs/research/FPA_INTEGRATION_REPORT.md
?? docs/research/FPA_NORTH_STAR.md
?? docs/research/FPA_PROTOCOL_EXPLORATORY.md
?? docs/research/FPA_REFERENCES.md
?? docs/research/FPA_STATUS.md
?? docs/research/FPA_TECHNICAL_GATES.md
?? docs/research/NOTE_SYNTHESE_SCIENTIFIQUE_FR.md
?? docs/research/README_WORKFLOW_V2.md
?? project-chatgpt/CYCLE.md
?? project-chatgpt/NEW_CHAT_START.md
?? project-chatgpt/PROJECT_INSTRUCTIONS.md
?? uv.lock
```

NO NEW MODEL INFERENCE RUN; AWAITING SCIENTIFIC REVIEW / USER AUTHORIZATION
