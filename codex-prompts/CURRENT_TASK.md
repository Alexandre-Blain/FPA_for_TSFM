# Tache courante - pilote local (EN PAUSE)

Le chercheur a autorise le perimetre ci-dessous, puis demande une pause pour
simplifier la documentation. Reprendre uniquement sur instruction du chercheur,
au point indique dans [le handoff](../docs/research/FPA_HANDOFF.md).
Les chemins documentaires du texte sont adaptes a la nouvelle organisation;
la copie originale est conservee dans le checkpoint local.

---

# NEXT CODEX ITERATION - Local multi-series FPA pilot and estimator validation

You are working in the existing `FPA_for_TSFM` repository.

**This is the next iteration of our current ChatGPT-Codex-researcher workflow, NOT the historical Prompt 3 stored under `docs/archive/`.**

The objective is to move from the successful single-context Chronos prototype to a scientifically informative, reproducible local multi-series pilot, while resolving only the technical issues necessary for reliable collection.

## 1. Read the authoritative project state

Before making changes, read:

- `AGENTS.md`
- `docs/research/README_WORKFLOW_V2.md`
- `docs/research/FPA_NORTH_STAR.md`
- `docs/research/FPA_STATUS.md`
- `docs/research/FPA_DECISIONS.md`
- `docs/research/FPA_PROTOCOL_EXPLORATORY.md`
- `docs/reference/FPA_HYPOTHESES.md`
- `docs/reference/FPA_TECHNICAL_GATES.md`
- `docs/research/FPA_HANDOFF.md`
- `docs/reference/BENCHMARK_REPORT.md`
- `docs/archive/FPA_PROPOSED_GRID.json`
- `docs/archive/PROMPT_NEXT_ITERATION.md`

Inspect the relevant code, tests, configuration and actual local Prompt 2 artifacts. Avoid repeating the completed broad repository audit.

Verify the current branch, exact HEAD, working tree and locally available results.

The last remote HEAD verified by ChatGPT was:

`main: b9c6a011e14a93235ed90cf88a11a25cead7264a`

The researcher has independently updated `.gitignore`. Preserve that local modification, whether committed or not.

The historical research plan and numbered prompts under `docs/archive/` are provenance, not the governing execution plan.

## 2. Exact authorization and scope

**By sending this prompt, the researcher authorizes:**

- Necessary implementation fixes and automated tests.
- Offline dataset inspection, selection and quality control.
- A local pilot on **up to six distinct original-series windows**, following the current H32/N20 exploratory protocol.
- Monte Carlo calibration using independent seeds on at most two of those windows, with up to three total seeds per selected window.
- Local profiling, checkpoint validation, bounded white-box replay and scientific analysis of the completed pilot.

This authorizes at most **ten complete window-seed experimental cells**: six primary cells and up to four additional independent-seed replications.

The limit defines the scientific scope of this iteration, not an assumed hardware limitation.

No artificial CPU-only, memory or short wall-time restrictions should be inherited from Prompt 2. Use the locally available hardware appropriately. Monitor performance, memory, disk usage and progress, and implement safe interruption and recovery.

**Not authorized:**

- The large exploratory campaign beyond this pilot.
- Remote-server or cloud execution.
- A second forecasting model.
- Stage A H64/N50 replication.
- Training, fine-tuning or adversarial experiments.
- A methodological redesign or unapproved change in estimands.
- Git staging, commits, pushes, pulls or branch changes.

The researcher retains control of all Git-writing operations.

## 3. Scientific objective

The principal question remains:

**What do plausible autoregressive output-token interventions reveal about subsequent numerical forecast distributions beyond local token probability, entropy and immediate numerical displacement?**

This iteration is exploratory. Its purpose is not to claim a confirmed effect or prove the paper's contributions.

Prioritize these comparisons:

1. Alternative versus independently sampled greedy-reference conditional distributions.
2. Downstream W1/ED versus immediate signed and absolute token displacement.
3. Downstream effects versus `q50`, `p_sel` and local entropy.
4. Downstream effects versus the independent same-token sampling-noise floor.
5. Between-series heterogeneity and examples contradicting simple explanations.
6. Reliability of weighted outcome-mixture estimators versus direct sampling.

The primary independent observational unit for cross-series scientific conclusions is the original series, not the individual generated trajectory or token branch.

## 4. Technical correctness gate

Before starting the six-window pilot, implement and verify the following.

### A. Multi-window persistence isolation

Inspect `ensemble_store.py`, `publish_fork_manifest()`, `collect_window()` and the relevant run drivers.

Ensure distinct windows cannot interfere with one another, even when they have:

- The same fork position.
- The same reference token.
- The same candidate token IDs.
- The same sampling seed.
- The same parent campaign output directory.

Each run/window must have stable identities covering dataset, original series, forecast origin, context hash, model revision, grid revision, policy and seed.

Use unambiguous per-window storage isolation and verify it through automated integration tests.

Test interleaved execution, interrupted writes, restart and recovery, immutable snapshot reading, and attempts to load artifacts from another window.

Never silently reuse an ensemble associated with a different context.

### B. Sampling and measurement invariants

Preserve the approved protocol:

- Chronos-T5-mini with pinned model revision.
- Context length 512, forecast horizon 32.
- Dense positions b=0..9.
- N20 independent conditional continuations per selected token.
- Effective q50 sampling with temperature 1, top-k 50 and top-p 1.
- Greedy token included in the selected set.
- Target cumulative q50 coverage >=90%, capped at eight selected tokens.
- Conditional residual group representing all unselected positive q50 mass.
- Independent greedy-reference and same-token null ensembles.
- Full token IDs and numerical paths saved.
- Strict downstream indexing, excluding the forced coordinate.
- Signed and absolute direct jump, full and fixed22 W1/ED.
- P0..P9 conditional mixtures, P10 reference reuse and P11..P15 direct N60.
- Fixed per-window terminal and last-eight outcomes and existing threshold grid.

Do not silently change the greedy-first tie convention, q50 support behavior or probability definitions.

Test scenarios requiring the eight-token cap, including coverage below 90% and a substantial residual. The previous real context selected only three tokens and is not sufficient validation of these edge cases.

### C. Evidence provenance

Inspect the `target_N20` field in `FPA_PROMPT02_EVIDENCE.json`, currently reported as a path string rather than the expected structured information.

Determine whether it is an export/serialization defect or an intentional field.

Preserve the frozen original evidence. Publish a clearly linked correction or addendum if necessary, rather than silently rewriting historical experimental records.

Verify the locally archived N20 source revision and report any remaining provenance uncertainty.

## 5. Construct a scientifically defensible six-window pilot

Use the datasets already under review:

- M4 Daily.
- ERCOT.
- Exchange Rate.

Select two windows per dataset, preferably from **two distinct original series**, giving six different original series overall.

For each dataset, use:

- One representative selection from a documented eligible sampling population.
- One diversity-oriented selection based on pre-FPA context characteristics.

Define selection rules before looking at new FPA outcomes.

Use only information available up to the forecast origin. Do not select windows using future observations, forecast errors or favorable historical FPA scores.

Record:

- Dataset and source files.
- Original series identifier.
- Forecast origin and context indices.
- Source and context SHA-256.
- Eligibility rules, rejected candidates and reasons.
- Selection seeds and representative/diversity stratum.
- Context IQR and descriptive time-series characteristics.
- Any suspected relationship to Chronos training data.

Exclude invalid scale or unusable context windows rather than silently modifying normalization.

Do not treat the previously studied M4/T000001 context as an independent new scientific replicate.

The six-window panel is a **pilot**, not a final sample-size decision or an estimate of population prevalence.

Freeze the selected pilot manifest before starting model inference.

## 6. Execute the local pilot

First execute and validate two windows from different original series. If their outputs satisfy the correctness and persistence checks, proceed automatically to the other four windows within this approved pilot.

For each window, collect the complete H32/N20 experiment specified above, including q50 candidates, residual, null controls, P0..P15 outcomes and overlap calibration.

Preserve individual numeric trajectories, token sequences, conditional-ensemble identifiers, probabilities, scales, hashes and run metadata.

Keep the full white-box research objective. Use replay and batched or streaming capture where appropriate to avoid unnecessary memory duplication. Do not silently discard essential trajectory or token information.

If full activation capture on every path is disproportionately expensive, preserve replayability and measure the cost using selected paths. Clearly distinguish fields captured immediately from those reconstructable later.

Use existing local data and cached model weights. Do not download new datasets, model weights or install unapproved dependencies.

Stop and report the precise blocker if a correctness gate fails. Do not continue producing scientifically questionable data.

## 7. Monte Carlo calibration

The previous N20 validation showed mixture-versus-direct differences of approximately:

- P0: 0.236.
- P9: 0.142.
- P10: 0.100.

These are observed finite-sample discrepancies, not established implementation errors.

On at most two selected pilot windows, perform the authorized additional independent-seed replications.

Investigate:

1. Variation of weighted-mixture event-probability estimates across independent seeds.
2. Variation of direct estimates across independent seeds.
3. Difference between methods at P0, P9 and P10.
4. Changes in estimator variance at the P10/P11 boundary.
5. Covariance induced by reusing the forced-greedy ensemble for P10 and the conditional mixture.
6. Event rarity, degenerate estimated probabilities and misleading zero plug-in standard errors.

Distinguish Monte Carlo uncertainty from between-series variation.

Do not treat bootstrap resamples as additional independent model draws.

Provide quantitative diagnostics, confidence or uncertainty calculations with clearly stated assumptions, and evidence of whether the discrepancy is compatible with finite-sample noise.

Do not implement formal BEAST/PELT change-point inference unless the existing data and validation provide a clear scientific justification. The primary objective of this iteration is reliable distribution estimation.

## 8. Scientific analysis of the pilot

Perform the initial analysis using only committed, complete experimental objects.

At minimum, provide:

- Per-window and per-dataset W1/ED distributions.
- Raw and context-IQR-normalized results.
- Independent same-token null comparisons.
- Effects versus signed J, absolute J, q50, p_sel and entropy.
- Fixed22 and full-suffix comparison.
- Per-horizon W1 profiles.
- P0..P15 fixed-outcome probability curves and their estimation uncertainty.
- Negative, near-null and contradictory examples.
- Preliminary morphology inspection using **both conditional ensembles**, not cherry-picked individual paths.
- Selected mass, residual mass and achieved coverage at every fork position.

Interpret across-series results descriptively. Six original series are insufficient for broad population claims.

Explicitly test alternative explanations:

- Ordinary numeric perturbation propagation.
- Candidate probability and quantization-bin geometry.
- Historical scale and normalization.
- Selection bias between representative and diversity strata.
- Sampling noise and correlated estimators.
- Decoder or replay implementation differences.

Do not create a new composite FPA score.

## 9. Deliverables and stopping condition

Produce a detailed report with:

1. Exact Git branch, starting HEAD and working-tree changes.
2. Implemented fixes and full test results.
3. Frozen six-window selection manifest and rejection log.
4. Complete accounting of executed windows, positions, ensembles, trajectories and independent seeds.
5. Integrity/recovery tests and checkpoint metadata.
6. Runtime, memory, storage and capture/replay measurements.
7. Monte Carlo estimator calibration, including uncertainty and covariance limitations.
8. Prioritized scientific findings, distinguishing **observed**, **suggested**, **unverified** and **refuted**.
9. The most serious alternative explanation for each scientifically interesting result.
10. A proposed larger local campaign design, with original-series counts and justification derived from pilot variability, domain coverage and expected scientific precision.

Update the canonical `FPA_STATUS.md`, `FPA_HANDOFF.md` and relevant technical documents. Append to `FPA_DECISIONS.md` only decisions actually authorized by the researcher.

Refresh `docs/chatgpt-handout/` and `docs/chatgpt-handout.zip` using the established script, including the full new report and supporting evidence.

Leave all Git modifications unstaged. Provide the precise changed-file list and suggested selective commit instructions.

**STOP after the six-window pilot and calibration. Do not automatically expand to the full campaign.**

The next step is a scientific review by ChatGPT and the researcher, followed by a separately authorized large-scale local collection.