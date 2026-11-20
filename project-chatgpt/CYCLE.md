# Minimal-friction research cycle

**One idea:** researcher/ChatGPT scientific audit -> explicit bounded Codex prompt -> Codex implementation/tests/checkpoints -> `FPA_HANDOFF.md` + full report -> ChatGPT skeptical assessment -> update versioned decisions/protocol -> next step.

### Files to upload to Project, with versioning discipline

**Initial reference:** original Bigelow PDF, `FPA_NORTH_STAR`, `FPA_PROTOCOL_EXPLORATORY`, `FPA_HYPOTHESES`, `FPA_STATUS`, `FPA_DECISIONS`, `FPA_TECHNICAL_GATES`, latest `FPA_HANDOFF`, `CHRONOS_PHASE2` and `CHRONOS_PHASE3_DESIGN`. Keep the older plan accessible only as historical provenance. If upload limits/duplication become burdensome, prefer `FPA_PROJECT_CONTEXT_SNAPSHOT.zip` plus individually readable critical MD files and reports. Keep just one **current** version of each living file in the Project when possible; archive older versions in Git, not as indistinguishable Project source names.

**Every Codex milestone:** Codex first updates the local working tree and writes the handoff/report; the **researcher** reviews diffs, stages/commits/pushes selected files; ChatGPT then reviews the pushed repository commit and available detailed reports. Refresh Project sources **only when changed**. New ChatGPT conversation in the same Project for each campaign (exploration, confirmed paper study, manuscript), not each small code edit.

**What Codex can do:** local file reads/writes, code changes, tests/inference once approved, checkpoints, detailed reports. **What ChatGPT can do here:** reason over uploaded snapshots and reports; if connected live GitHub/Drive source exists and is explicitly accessible, verify with tools; otherwise do not assume remote/local auto-sync.

**One message from Codex after every substantive iteration:**

`Git branch: ... | base HEAD before researcher commit: ... | researcher-pushed commit (if available): ... | run id: ... | actually executed: ... | outcome: ... | tests: ... | path to full report: ... | scientific uncertainty: ... | next gate: ...`

**ChatGPT reply contract:** 3-5 scientific conclusions, direct evidence vs hypotheses, competing explanations, implications for Paper 1, exact next experiment if any, bounded Codex prompt or explicit stop.

**Synchronization guard:** The local Git docs always win over stale ChatGPT Project copies for current state; manifests win over narrative status for factual execution. If dates/hashes mismatch, pause recommendations requiring execution and ask for the latest handoff.
