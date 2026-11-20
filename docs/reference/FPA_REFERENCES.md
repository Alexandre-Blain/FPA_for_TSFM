# Evidence sources, related research, and precedence

**Observed metadata check - 2026-11-19:** the six primary literature landing
pages below resolve and match their supplied authors/titles (the Mishra title
is expanded below). This was a bibliographic/abstract check, not a full-paper
methodological review or reproduction. Scientific transfer to Chronos-mini
remains **hypothesis**; proposed uses are **suggested**. No original-paper PDF
was supplied in the bundle or found in the repository. Keep the primary URLs
as source pointers; do not invent a local PDF path.

**Updated 2026-11-19.** References are anchors, not a claim that every method/result was reproduced. Always verify bibliographic metadata and actual local source versions when writing a paper.

## Local primary sources

1. Prior scientific plan: `docs/future works/FPA_CHRONOS_RESEARCH_PLAN (1).md` (verify real repo path). **Historical plan**, contains old prohibition on BEAST and old project staging; do not silently delete. The new candidate experiment explicitly revisits that boundary.
2. Phase 1 report: `docs/CHRONOS_PHASE1.md` if present.
3. Phase 2 source: `docs/CHRONOS_PHASE2.md`, run `result/phase2_controlled_pilot_20261116_195533/`, seven-group controlled pilot; raw trajectory files and manifests.
4. Phase 3 source: `docs/CHRONOS_PHASE3_DESIGN.md`, offline data `result/phase3_offline_controls_20261117_175121/`. **Stage A new inference not executed** as of user confirmation.
5. Historical clean score-composite scan: `result/clean_confirm_no_refinement_20260915_114823/` (mostly summary files and known metric limits).
6. Local repository source code, configuration, model revision, raw datasets, manifests, hashes and terminal logs are the authoritative computational evidence. Distinguish claims from reports vs freshly verified code.

## Directly related literature

- Bigelow, Holtzman, Tanaka & Ullman. *Forking Paths in Neural Text Generation*. ICLR 2025. https://arxiv.org/abs/2412.07961 . Defines fixed base path, forced alternate tokens, outcome distributions, outcome drift and change-point model. In their paper base path may be *such as* greedy; our protocol uses greedy specifically. CPD is across **prefix position**, not future horizon.
- Bigelow et al. *Forking Fast: Efficiently Estimating Uncertainty Dynamics in Text Generation*. arXiv:2608.19611 (2026). https://arxiv.org/abs/2608.19611 . Related sample efficiency, pooling and CPD; do not claim generic pooling/striding novel.
- Ansari et al. *Chronos: Learning the Language of Time Series*. arXiv:2403.07815 (2024). https://arxiv.org/abs/2403.07815 . Model/tokenization architecture.
- Zur, Geiger, Lubana & Bigelow. *Are language models aware of the road not taken? Token-level uncertainty and hidden state dynamics*. arXiv:2511.04527 (2025). https://arxiv.org/abs/2511.04527 . Internal representations / uncertainty, not proof of Chronos FPA predictability.
- Wiliński et al. *Exploring Representations and Interventions in Time Series Foundation Models*. ICML 2025. https://proceedings.mlr.press/v267/wilinski25a.html . TSFM hidden representations and intervention methods; verify exact experimental transfer.
- Mishra. *Dissecting Chronos: Sparse Autoencoders Reveal Causal Feature Hierarchies in Time Series Foundation Models*. arXiv:2603.10071 (2026). https://arxiv.org/abs/2603.10071 . Chronos-T5 Large preprint, not our T5-mini validated mechanism.

## Future directions (record only, not tasks)

- TSFM vs LLM general comparison of FPA; patch/token representation and computation implications.
- Copula numerical paths on TimesFM (see Baron et al., arXiv:2510.02224); adversarial future-input/history region selection conditional on showing predictive value, not assumed from generative forks.
- Input/history perturbation and UCR classification can be separate **task-matched** validation designs, but are not intrinsically equivalent to output-token branching.

## Precedence for conflicts

Raw trajectories + manifest + hash and measured environment > executed test logs > original phase reports > living status/docs > ChatGPT conversation or memory > assistant speculation. If an old report uses different metric conventions, report both and do not normalize them into one figure silently.

## Portable evidence pointers checked during integration

**Observed:** all local sources below exist. Original reports/plans are retained
without edits; historical absolute paths in manifests are provenance, not current
lookup paths. Relative Phase 3 input hashes match the current local Phase 2 files.

- [Phase 1](CHRONOS_PHASE1.md), [Phase 2](CHRONOS_PHASE2.md), [Phase 3](CHRONOS_PHASE3_DESIGN.md)
- [Historical scientific plan](<../archive/FPA_CHRONOS_RESEARCH_PLAN (1).md>) and [historical phase prompts](<../archive/CODEX_PHASE_PROMPTS (1).md>)
- [Legacy handoff](../archive/FPA_CET1_RESEARCH_HANDOFF.md) and [future ideas](../archive/CHRONOS_FPA_FUTURE_IDEAS.md)
- [Phase 2 frozen config](../../configs/chronos_controlled_pilot/phase2.json) and [reduced scope](../../configs/chronos_controlled_pilot/half_execution.json)
- Local-only artifacts: result/phase2_controlled_pilot_20261116_195533/ config.json, execution_plan.json, selection.json, progress.json; seed-specific branch_groups and trajectory manifests; and result/phase3_offline_controls_20261117_175121/protocol.json.
- [Integrity evidence](../archive/FPA_INTEGRATION_EVIDENCE.json) lists exact inspected paths/hashes. These ignored run artifacts are not guaranteed available from a remote Git checkout; attach the required manifests/report evidence for external review.
