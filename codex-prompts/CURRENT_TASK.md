# Current task - extended batch (COMPLETE; STOP FOR SCIENTIFIC REVIEW)

Completed 2026-11-22: Stage A, eight new series, 24 dense N20 blocks,
16 selected contrasts with fresh N60, holdout random controls, scientific
analysis and review handout. Total 34,980 trajectories; 281 final offline tests pass.
No second batch, downloads, dependency changes or Git writes.

Evidence: result/extended_batch_20261122T115422Z/.
Read the [report](../docs/reference/FPA_EXTENDED_BATCH_REPORT.md) and
[handoff](../docs/research/FPA_HANDOFF.md). Completed resume was verified with
zero model launches and zero new draws. Further collection requires a new task.
The original authorization below is preserved; it is not a request to rerun it.

---

# NEXT CODEX ITERATION - FPA: Direct Baseline Validation and First Extended Campaign Batch

You are working in the existing `FPA_for_TSFM` repository.

This is the next authorized iteration in the ChatGPT-Codex-researcher workflow.

**Objective: resolve the remaining targeted methodological question, freeze a prospective experimental design, and execute the first extended local collection batch.**

Do not start another general audit, documentation cleanup or open-ended preparation cycle.

## 1. Verify project state

Read the authoritative project documentation:

- `AGENTS.md`
- `docs/README.md`
- `docs/research/FPA_NORTH_STAR.md`
- `docs/research/FPA_PROTOCOL_EXPLORATORY.md`
- `docs/research/FPA_STATUS.md`
- `docs/research/FPA_DECISIONS.md`
- `docs/research/FPA_HANDOFF.md`
- `docs/research/README_WORKFLOW_V2.md`
- `docs/reference/LOCAL_PILOT_REPORT.md`
- `docs/reference/LOCAL_PILOT_OFFLINE_ANALYSIS.md`
- `docs/reference/CHRONOS_METRICS.md`

Inspect the existing pilot collection, analysis code, configurations and checkpointing mechanisms before making changes.

GitHub `main` was last verified at:

`ea3d78a10280e83e65a2bd7474af3eaf8ee1a905`

Verify the actual local branch, HEAD, working-tree changes and applicable source versions. Do not overwrite unrelated local modifications.

Historical experimental manifests and reports remain immutable.

**Codex must not perform Git staging, commits, pushes, pulls or branch changes.**

## 2. Stage A - Directly test numerical propagation baselines

This is the one unresolved targeted offline analysis required before extending collection.

The existing analysis compares alternative W1/ED magnitudes with distances produced by persistent-shift and AR(1)-style numerical propagation.

That comparison is insufficient: two distributions can be equally distant from a reference while being very different from each other.

We need to test the actual distributional predictions of these baselines.

For each forced alternative token \(w\) at position \(b\), let:

- \(P_{b,w}\): distribution of conditional continuations after forcing \(w\).
- \(P_{b,g}\): distribution after forcing the greedy token.
- \(J_{b,w}\): signed numerical value difference between the forced and greedy tokens.

Define two candidate transformations over strictly post-fork horizons \(k=1,\ldots,31-b\):

**Persistent numerical shift**

\[
T_{\mathrm{persist}}(Y)_{b+k}=Y_{b+k}+J_{b,w}
\]

**AR(1)-style attenuation**

\[
T_{\mathrm{AR1}}(Y)_{b+k}
=Y_{b+k}+J_{b,w}\phi^k
\]

where \(\phi\) is the previously defined lag-1 context statistic. Treat it as a heuristic baseline, not a mechanistic model of Chronos.

Directly compute:

\[
D(P_{b,w},T_{\mathrm{persist}}\#P_{b,g})
\]

and

\[
D(P_{b,w},T_{\mathrm{AR1}}\#P_{b,g})
\]

using **both W1 and ED**.

Use independently sampled reference/null continuations where appropriate, preserve the shared-sample dependence in comparisons, and avoid leakage from the alternative samples when specifying transformations.

Compare these residual distributional differences with the untransformed reference comparison and same-law Monte Carlo controls.

Evaluate the declared temporal supports:

- Full strictly post-fork suffix.
- Relative fixed22.
- Common absolute coordinates 10–31.
- Final eight forecast coordinates.

Report raw distances and protocol-normalized distances separately.

Where statistically appropriate, test the hypothesis that alternative and transformed-reference samples come from the same distribution. Use whole-trajectory permutations, explicit multiplicity correction and independent-seed validation.

Do not interpret failure to reject as proof that the baseline explains the intervention.

For matched opposite-sign interventions, investigate whether either propagation model explains their apparent asymmetry.

**Required output:** determine whether there are credible, independently supported examples where simple numerical propagation is inadequate.

A negative result is scientifically valuable.

### Stage A gate

Before proceeding to new model sampling, verify that:

1. Historical W1/ED values are reproduced.
2. Direct transformed-distribution comparisons are implemented and unit-tested.
3. Sample independence and transformation indexing are correct.
4. No serious inconsistency undermines the existing collection protocol.

If a correctness problem invalidates the data or sampling law, stop and report it.

Otherwise, proceed directly to Stage B. Do not require positive scientific findings to continue.

## 3. Stage B - Freeze a prospective first-batch design

This invocation authorizes a **bounded first extended batch**, not the entire future campaign.

Select up to **8 new original-series windows**:

- 4 M4 Daily.
- 2 ERCOT.
- 2 Exchange Rate.

Use the existing eligible local datasets and established selection machinery.

Exclude all original series already used in the current pilot or earlier FPA experiments when their identities are known.

Within each dataset, include representative and diversity-oriented selections using deterministic, context-only criteria.

Selection must not use the future target values, FPA outcomes, favorable fork scores or validation results.

Freeze before model inference:

- Series IDs and dataset origins.
- Window origins and complete input contexts.
- Representative/diversity stratum labels.
- Eligibility and exclusion rules.
- Sampling seeds and RNG stream identities.
- Model revision and sampling policy.
- Selected metrics and temporal supports.
- Validation and multiplicity procedures.
- Dataset/source hashes and environment metadata.

Record correlations or shared underlying processes among source series. In particular, do not treat contemporaneous ERCOT regions or exchange-rate series as automatically independent.

Use exactly one primary context per selected original series in this batch.

If fewer than eight eligible independent source-series identities are available, document the limitation and reduce the batch rather than silently replacing them with nearby windows from the same series.

## 4. Stage C - N60 dense collection using independent N20 blocks

**For this first batch, use N60 total continuations per conditional ensemble, implemented as three independent N20 blocks.**

This is a prospective sampling-policy revision for the new batch only.

Do not rewrite the original pilot's N20 protocol or historical metadata. Record the revised batch protocol separately and make its status explicit in the decision log.

Keep the existing scientific invariants:

- Chronos-T5-mini, pinned revision.
- Context length 512.
- Forecast horizon 32.
- Dense intervention positions b0..9.
- Original q50 policy, temperature, top-k/top-p handling and valid-token mask.
- 90% selected-mass target, maximum eight selected tokens including greedy.
- Explicit residual conditional ensemble.
- Independent greedy-reference and same-token null samples.
- Exact autoregressive conditioning on every preceding generated token.
- Complete sampled token IDs and numerical trajectories.
- P0..P15 outcome distributions and continuous outcomes.
- Full and fixed22 W1/ED, plus offline supports.
- White-box capture and replay metadata without multiplying activation storage unnecessarily.

For each window and conditional ensemble, produce:

\[
N=20+20+20=60
\]

using three independently seeded sampling blocks.

Preserve block identity so that N20, N40 and N60 analyses remain possible.

The original first block must remain independently usable for exploratory selection. Never label pooled N60 samples as independent replications of N60.

For P0..P15, account for the greater number of conditional samples and preserve the distinction between q50-weighted mixture estimates and directly sampled prefix distributions.

Avoid unnecessary recomputation of the same direct conditional law if it can be safely reused with explicit covariance accounting.

**Execution ceiling:** eight original-series windows, three N20 dense blocks per window, plus only the targeted validation described below.

No automatic expansion to the remaining campaign.

## 5. Stage D - Independent validation of predefined contrasts

For each new window:

1. Use **only the first N20 block** to rank candidate alternative forks.
2. Select at most two scientifically informative contrasts using a frozen rule.
3. Include at least one randomly selected eligible control contrast, distinct from the selected positive candidates where possible.
4. Keep the second and third N20 blocks completely separate from candidate selection.

Evaluate selected contrasts on the independent N40 holdout.

Then, for at most two selected contrasts per window, generate **an additional independent N60 validation set**, using fresh RNG streams and the necessary reference, alternative and null ensembles.

Share a reference across contrasts at the same fork position only when its reuse is explicitly represented in the statistical analysis.

For opposite-sign paired alternatives, include both alternatives in the same validation design. Do not treat their shared reference as independent evidence.

Predeclare how selection works when W1 and ED disagree. Do not silently select whichever metric gives the more favorable result.

Distinguish:

- Detecting unequal conditional distributions.
- Establishing a practically meaningful effect size.
- Showing failure of a simple numerical-propagation baseline.
- Establishing stable rankings.
- Generalization across original series.

These are different claims requiring different evidence.

Use permutation tests, appropriate uncertainty intervals and explicit multiple-testing correction. State the hypothesis family used.

The random controls are essential to assess how strongly the candidate-selection rule enriches for reproducible effects.

Do not increase validation sample sizes adaptively after seeing unfavorable results without a new authorization.

## 6. Stage E - Scientific analyses of the new batch

Perform the established analyses on all completed windows:

**Distributional effects**
- W1 and ED on full, relative22, absolute22 and final8 supports.
- Raw and IQR-normalized results.
- Independent same-token noise controls.
- N20/N40/N60 precision and rank stability.
- Distributional fit of persistent-shift and AR(1)-style baselines.

**Temporal behavior**
- Signed conditional mean-response profiles.
- Variance changes.
- Persistence, attenuation, amplification and sign reversals.
- Centered and differenced trajectory diagnostics.
- Matched-jump and opposite-sign comparisons.

**CPD**
- Binary and continuous P0..P15 outcomes.
- Cumulative and adjacent drift.
- Estimator-boundary uncertainty.
- Local signed contributions and cancellation.
- Independent direct-sampling comparisons where available.

**Explanatory variables**
- Signed and absolute J.
- q50 and p_sel.
- Entropy.
- Token-bin geometry.
- Context-regime characteristics.
- Dataset and source-series identity.

Use source-series-level aggregation for cross-series summaries. Do not treat branches, generated trajectories or horizons as independent population observations.

Do not claim formal change points, internal causality or universal TSFM behavior unless the necessary evidence is actually present.

## 7. Computational and data-integrity requirements

Run locally using the existing environment and available model weights.

No server deployment, second model, retraining, dataset downloads or dependency upgrades.

Reuse the validated ensemble storage, window isolation, frozen manifests and atomic publication mechanisms.

The batch must be restartable after interruption without changing RNG identity or recomputing completed ensembles unnecessarily.

Before advancing from the first two different-series windows to the remaining six, verify:

- Conditioning and decoder parity.
- q50/residual probability mass.
- Complete branch coverage.
- Independent RNG streams.
- Exact trajectory and token preservation.
- W1/ED reconstruction.
- Checkpoint consistency.
- Memory and runtime measurements.

Stop on any failed scientific-integrity gate.

Do not impose arbitrary low runtime limits inherited from Prompt 2. Record measured costs and protect the machine from uncontrolled memory or disk usage.

Preserve all previous pilot results and offline analyses unchanged.

## 8. Required scientific deliverables

Produce one principal report:

`docs/reference/FPA_EXTENDED_BATCH_REPORT.md`

Include:

1. Exact Git/source/model provenance.
2. Frozen cohort and selection criteria.
3. Completed cells, ensembles, trajectories and independent RNG streams.
4. Direct numerical-baseline results from Stage A.
5. Precision and holdout-validation results.
6. W1/ED findings across supports and datasets.
7. Temporal propagation, morphology and CPD findings.
8. Alternative explanations and negative results.
9. Three to five ranked scientific conclusions with explicit evidence levels.
10. Implications for the remaining campaign.

For each important finding, specify:

- What is directly observed.
- What is suggested.
- What remains unverified.
- What could falsify the interpretation.
- Whether it provides evidence beyond local token probability, numerical jump and ordinary sampling variability.

Store full experimental objects, manifests, CSVs and figures in new ignored result directories. Do not overwrite historical evidence.

Update the existing active project status, handoff and minimal navigation links. Append only genuinely authorized decisions to `FPA_DECISIONS.md`.

Regenerate the ChatGPT handout with the new report and selected scientific supporting assets.

Avoid duplicate scientific summaries scattered across documents.

Report exact tests, changed files, measured execution costs and any unresolved issues.

Leave all Git changes unstaged and uncommitted.

## 9. Mandatory stopping condition

**STOP after this eight-series batch, its targeted independent validation and scientific analysis.**

Do not launch a second batch or the full campaign automatically.

The next ChatGPT-researcher review must decide:

- Whether N60 provides adequate practical precision.
- Whether independent validation needs more sampling for selected effects.
- Whether the current source datasets are diverse enough.
- Whether the observed effects contain information beyond simple numerical propagation.
- How large the remaining campaign should be.
- Which scientific hypotheses deserve confirmatory evaluation.

The intended result of this iteration is not merely more trajectories. It is **a prospectively collected, independently validated basis for choosing the final campaign design**.

Proceed with the authorized first batch when the Stage A correctness gate passes. Do not stop merely because Stage A produces negative scientific findings.
