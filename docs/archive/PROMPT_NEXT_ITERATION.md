# REUSABLE CODEX ITERATION PROMPT - FPA research

**Current authorized task:** `[ONE BOUNDED TASK WITH EXACT DELIVERABLE]`
**Approval/reference:** `[USER APPROVAL MESSAGE OR TRACKER ID]`
**Allowed compute / new samples:** `[EXACT BUDGET OR NONE]`
**Allowed code files:** `[PATHS OR PURPOSE]`
**Forbidden scope changes:** `[ADD SPECIFIC EXCLUSIONS]`

First read `AGENTS.md`, `FPA_NORTH_STAR.md`, `FPA_STATUS.md`, `FPA_DECISIONS.md`, relevant protocol and only the necessary original reports/code.

Researcher-only Git rule: Codex edits/tests within approved scope but never stages, commits, pushes, pulls, changes branches or rewrites history. At handoff provide branch, original HEAD, `git status --short`, changed paths, safe staging suggestions and commit-message proposal; only the researcher performs Git writes.

Before executing: define one scientific question, competing explanation, falsifier, exact measures and experimental unit, code/data invariants, test plan, runtime ceiling, checkpoint/resume plan, and stopping condition. If any explicit user approval is missing, do a read-only or offline design only.

During execution: preserve raw samples and hashes; emit only committed checkpoints; separate direct observation from inference; capture failures and negative results; stop at resource limit. Never change estimands/selection mid-run without logged new grid version and authorization. If analysis runs in parallel, it may read committed checkpoints only.

At completion: update status and handoff with Git hash, exact newly executed groups and N, results with units and controls, rejected hypotheses and alternatives, tests actually run, runtime/memory/MB, artifact paths, and one concrete next decision; append to decision log only for explicit researcher choices. STOP for external ChatGPT scientific review.
