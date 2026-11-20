# FPA / Chronos - Scientific north star

**Observed technical update - 2026-11-20:** separately approved Prompt2
completed; see [report](BENCHMARK_REPORT.md). It validates selected engineering
operations on one context, without establishing the scientific contributions
below or authorizing a campaign. The November19 annotation retains its date.

**Integration annotation - 2026-11-19:** prospective contributions and scientific
mechanisms below are **hypotheses**; design priorities are **suggested** until a
bounded execution prompt is approved. The existing-evidence section is
**observed (source reports)**, not a new replication. Local artifact/code checks
are recorded in [status](FPA_STATUS.md) and the
[implementation audit](FPA_IMPLEMENTATION_AUDIT.md). The current user prompt
confirms the H32/N20 candidate invariants and output-token scope; installation
does not establish implementation or authorize inference.

**Version 2 proposal, 2026-11-19.** Supersedes the scope commentary of the older north-star document **if integrated and approved**. Does not supersede original experiments or reports. Review before manuscript preparation.

## Problem: decisions in generation, not saliency of observed input

The research object is the conditional distribution of **future numerical trajectories** after forcing a plausible autoregressive output token instead of the corresponding reference token, given a fixed reference-generated prefix. The main model is `amazon/chronos-t5-mini` (Chronos v1, T5 encoder-decoder). Analysis of past input sensitivity or attribution for UCR classifiers targets a different operation; UCR classification is **not** the required evidence of FPA usefulness for Paper 1.

**Central research question:**

> What consequential, interpretable changes in autoregressive TSFM generation does numerical Forking Paths Analysis reveal that are not adequately characterized by local token probability, entropy or the immediate decoded numerical jump?

The Bigelow (ICLR 2025) base-path paradigm provides the conceptual method. Our fixed base path is **greedy**, whereas Bigelow allows a base path such as a greedily decoded sequence. The suffixes are sampled, not greedy. The intervention is on a *generated token*, not on the physical data-generating mechanism.

## Candidate scientific contributions

**C1 - Measured conditional branching:** Correct, reproducible, declared sampling policy; alternative vs reference continuation laws; exact marginal W1 and multivariate Energy Distance with controlled finite-N noise; direct jump vs downstream effects. Robust methodology is a prerequisite, not in itself proven novelty.

**C2 - Distributional characterization:** Describe distribution, prevalence under an explicit candidate-selection population, severity and location/persistence of consequential forks; heterogeneity across original series, windows and domains; test whether probability, entropy, numerical jump, signed direction and context suffice to characterize downstream sensitivity.

**C3 - Temporal meaning:** Compare *ensembles*, describe trajectory-level effects (level, direction, extrema, uncertainty width, timing and trend) when empirically supported; include counterexamples/negative cases. Avoid equating an illustrative single trajectory to an ensemble property.

**Potential secondary avenues:** (i) original Bigelow-style CPD of outcome distributions as the greedy prefix grows; (ii) CPD/segmentation on post-fork W1 horizon profiles (different estimand); (iii) predictive information in hidden states/attention; (iv) sample-efficient region selection, pooling, caching; (v) future architecture comparisons and adversarial region selection. Do not force these as independent paper contributions before results.

## How we demonstrate scientific value

An observed fork with large W1 or ED is not sufficient. More persuasive evidence includes **controlled non-reducibility** to local quantities and interpretable changes that survive Monte Carlo controls / alternative numerical propagation explanations. Appropriate baselines include probability and entropy; |J| and signed J; context scale; simple numeric autoregressive propagation when feasible; random and inexpensive screening policies, at matched computational budget. A successful comparison must concern a **common estimand**. A benchmark retrieving FPA labels evaluates the information and cost of *screening*, not independently validates the scientific usefulness of FPA itself; acknowledge potential circularity.

If simple baselines predict downstream forks well, this is a valuable **negative** finding about when costly FPA is unnecessary; do not spin it into a positive novel mechanism. One checkpoint does not establish a universal TSFM law.

## Empirical design priorities

1. First ensure correct laws/outputs, provenance, reproducibility and statistical unit; then prefer **different original series/domains/regimes** before repeatedly exploring nearly identical windows. Use representative and diversity-selected windows as two explicitly labeled strata.
2. Primary exploratory campaign: windows with H32, C512, FPA dense b0..9, N20/ensemble, up to eight q50 candidates including greedy, 90% target / eight cap, residual conditional mixture and independent same-token control; extend per-window CPD to P15 with N60 direct for P11..15. This is **candidate protocol**, not executed or necessarily final.
3. Use window-level profiles, paired branch controls and original-series clustered analyses. A CPD curve per window is useful even with only 16 conditional distributions; formal change-point certainty with so few noisy points remains unresolved.
4. Capture maximum feasible white-box measurements, with benchmark and replay; profile encoder reuse / decoder cache / batching. Do not sacrifice exact conditioning or introduce estimator drift for speed.
5. Keep selected `H64,N50` M4 Stage A as a **separate confirmation cell**, not a seamless extension of new `H32,N20` exploration. No inference is approved by writing this plan.

## What existing evidence actually supports

- Phase 1 constructed empirical W1/ED, raw trajectories and same-token control; Phase 2 sampled seven groups / 1,400 paths on only three original series, not a broad prevalence survey.
- M4 T000001 b0 opposite near-equal-|J| tokens show unequal observed distances **in one selected context** (novel mechanism unproven); Stage A new seed not run.
- ERCOT EAST b0 transient/early larger effect appears on two seeds **at one selected point**, temporal split post hoc.
- Exchange Rate currency_3 b16 alternatives separate but ordering is noisy.
- Entropy/distance relationships suffer within-series and between-dataset confounding. No universal monotonic relationship or robust independence from local entropy established.
- Quantitative peak/plateau/trend transformations remain mostly **hypotheses**, not proven population features.
- Historical 2026 summer/September composite-score exports largely lack individual trajectories and do not directly validate the new distances; do not silently merge their scores into modern analyses.

## Publication barriers we must actively test

- Is the claim simply ordinary numerical shock propagation rather than a TSFM-specific generative insight?
- Does a fixed decoder/sampling policy impose trivial endpoint convergence in greedy-distance outcomes?
- Is 'extra information beyond entropy' an artifact of tokenization, normalization, grouped probabilities, or dataset mix?
- Is a perceived change point an estimator boundary artifact (weighted N20 mixture vs direct N60)?
- Are pooled windows / tokens falsely treated as independent data points?
- Are 'important forks' identified by the same N20 noisy estimates used to evaluate a screening method?
- Are generality and venue ambitions consistent with actual number of independent original series and architectures?

**The publication story should be selected *after* the exploratory campaign's critical analysis.** This project seeks genuine contributions, not a preselected positive narrative.

## Outside the currently approved experiment

UCR classifier-attribution benchmark, adversarial history attacks and backdoors, TimesFM/LLM comparative experiments, copula paths, zero-shot accuracy benchmark, causality claims from attention, a novel composite score, large learned morphology model or automatic paper drafting. Preserve as future ideas, not implicit Codex tasks.
