# Current task - offline pilot analysis (COMPLETE, SCIENTIFIC REVIEW GATE)

Authorized 22 November 2026. Saved complete trajectories only; no model inference,
downloads, dependency changes or Git writes. The completed pilot request remains
in Git history and the immutable pilot AUTHORIZED_REQUEST.txt.
See [handoff](../docs/research/FPA_HANDOFF.md).

Completed: all five offline analyses, precision recommendation and review bundle.
No additional model draws. Read the
[main scientific report](../docs/reference/LOCAL_PILOT_OFFLINE_ANALYSIS.md).
STOP: campaign sampling changes require a separate researcher decision.

---

# FPA - Next Codex Iteration: Offline Scientific Analysis and Campaign Readiness

You are working in the existing `FPA_for_TSFM` repository.

This is the next task in our ChatGPT-Codex-researcher workflow, following the completed six-series local pilot.

**Your objective is to extract the most scientifically informative results from the existing trajectories, evaluate Monte Carlo reliability, and determine what sampling strategy should be used for the full exploratory campaign.**

This is an analysis task, not a new experimental campaign.

## 1. Scope and authorization

**Authorized:**
- Read all completed pilot data and frozen manifests.
- Implement offline analysis scripts and focused tests.
- Recompute metrics directly from saved individual trajectories.
- Perform statistical analyses, resampling, permutation tests and comparisons requiring no new model inference.
- Produce one comprehensive scientific report and an updated ChatGPT handoff.

**Not authorized:**
- New Chronos sampling or model inference.
- New datasets or model downloads.
- Changes to the existing scientific protocol.
- Changes to historical experimental results.
- Server deployment or infrastructure redesign.
- Launching the larger exploratory campaign.
- Git staging, commits, pushes, pulls or branch changes.

Use existing local computational resources as needed. Do not inherit arbitrary runtime or RAM limits from Prompt 2.

Prioritize rigorous analysis over producing additional plots or documentation.

## 2. Read and verify the current project

First read:

- `AGENTS.md`
- `docs/README.md`
- `docs/research/FPA_NORTH_STAR.md`
- `docs/research/FPA_PROTOCOL_EXPLORATORY.md`
- `docs/research/FPA_STATUS.md`
- `docs/research/FPA_DECISIONS.md`
- `docs/research/FPA_HANDOFF.md`
- `docs/reference/LOCAL_PILOT_REPORT.md`
- `docs/reference/LOCAL_PILOT_EVIDENCE.json`
- `docs/reference/FPA_HYPOTHESES.md`
- `docs/reference/CHRONOS_METRICS.md`

Inspect the relevant metric implementations and existing analysis scripts.

The latest GitHub HEAD verified by ChatGPT is:

`ad64422b973aa77a33e99827ced9bdae903b15cb`

Verify the actual local branch, HEAD and working tree.

The primary dataset is:

`result/local_pilot_20261120T184035Z/`

Use the individual complete trajectory ensembles and their manifests as the authoritative data. The CSV summaries are references and consistency checks, not substitutes for raw paths.

The pilot contains six original series and ten window-seed cells. Two windows have three independent seeds each.

Verify identities, conditioning, model revision, policy parameters, complete checkpoint hashes and sampling independence before pooling any trajectories.

Reproduce the existing important statistics before extending the analysis. Report any discrepancy rather than silently correcting historical outputs.

## 3. Analysis A - Monte Carlo convergence and precision

**This is the highest-priority task.**

We need to decide whether N20 is sufficient for broad exploration and whether larger N meaningfully improves the scientific conclusions.

Use the two independently replicated windows:

- M4 Daily, T000063.
- ERCOT, SOUTHERN.

Each has three independently sampled N20 conditional ensembles.

After verifying identical conditioning and candidate policies across seeds, construct estimates using N20, N30, N40 and N60 where valid.

For N30, use properly identified independent additional draws from another seed. For N40, examine the available two-seed combinations. For N60, pool all three independent seeds.

Preserve separate reference and alternative ensembles. Never duplicate samples and call them independent.

For **both W1 and ED**, evaluate:

1. Distance-estimate stability as N increases.
2. Branch-ranking stability and rank correlations.
3. Top-k branch overlap across independent estimates.
4. Variability of matched-jump alternative contrasts.
5. Independent same-token null distributions.
6. Uncertainty around alternative-versus-reference differences.
7. Stability of conclusions about consequential versus near-null forks.

Use independent-seed comparisons where available, whole-trajectory resampling and appropriate permutation diagnostics.

Treat shared reference ensembles, nested sample sizes and repeated branches as dependent observations.

Do not interpret a positive finite-sample W1 or ED as a significance test.

For ED, retain the protocol's V-statistic and optionally compute the U-statistic as a separate bias diagnostic. The U-statistic may be negative.

**Required decision:** recommend a justified sampling strategy for the larger campaign, comparing options such as uniform N20, uniform N40/N60, and broad N20 with higher-precision validation of selected contrasts.

Do not invent a universal optimal N. State which scientific decisions each option can and cannot support.

## 4. Analysis B - Downstream propagation versus stochastic noise

A preliminary reanalysis suggests:

- 157/186 primary alternatives show increasing W1 from early to late horizons.
- 59/60 independent null controls show the same pattern.
- Only 59/186 alternative-minus-null W1 profiles show an increase.

First reproduce or correct these numbers from the raw saved trajectories and explain the precise definitions.

Then investigate whether apparent downstream amplification is attributable to increasing variability of the conditional forecast distributions.

For each branch position and forecast horizon, analyze:

- Alternative-versus-reference W1.
- Independent greedy-versus-greedy null W1.
- Reference ensemble dispersion.
- Signed conditional mean difference.
- Difference in conditional forecast variance.
- Persistence, attenuation, amplification and sign reversal.

Define the signed response:

\[
\Delta\mu_{b,w}(h)
=
E[Y_h\mid w]-E[Y_h\mid g_b].
\]

For sufficiently large nonzero numerical jumps, investigate:

\[
G_{b,w}(h)=\frac{\Delta\mu_{b,w}(h)}{J_{b,w}}.
\]

Avoid unstable ratios for tiny J.

Compare observed propagation with the existing persistent-shift and simple autoregressive propagation baselines where their definitions are valid.

**Important:** subtracting empirical null W1 from alternative W1 is only a descriptive diagnostic. It is not automatically an unbiased effect estimate or a formal test. Account for shared-reference dependence and differing conditional variances.

The objective is to distinguish real changes in conditional generation from ordinary numerical propagation and horizon-dependent sampling noise.

## 5. Analysis C - W1, ED and temporal morphology

We have complete trajectories. Do not unnecessarily restrict the analysis to fixed22.

Compute **both W1 and ED** on:

1. Full strictly post-fork suffix: coordinates b+1 through 31.
2. Relative fixed22: the first 22 strictly post-fork coordinates.
3. Common absolute 22-step support: forecast coordinates 10 through 31.
4. Final-eight-step support: coordinates 24 through 31.

Also retain complete W1-by-horizon profiles.

Make the exact coordinate convention explicit for every metric.

Do not compare ED values calculated in different dimensions as though they estimate the same distributional quantity.

For each support, investigate:

- Branch-ranking agreement between W1 and ED.
- Ranking changes across supports.
- Early divergence versus persistent divergence.
- Cases where W1 and ED disagree.
- Cases where the conditional means are similar but trajectory distributions differ.

Perform secondary analyses on centered and differenced trajectories to investigate level changes versus temporal shape changes.

Specify the transformations before interpreting the results. Centering and differencing do not automatically isolate temporal dependence.

Include same-token null diagnostics for these transformed comparisons.

Prioritize robust counterexamples and scientifically informative disagreements, not attractive plots.

## 6. Analysis D - Continuous CPD and local fork contributions

The existing protocol estimates P0 through P15 for fixed outcome definitions.

Analyze the CPD curves using both:

- Existing binary threshold events.
- Continuous outcomes reconstructed from the saved trajectories.

For continuous analysis, examine terminal value, signed terminal displacement, absolute terminal displacement and final-eight-step summaries.

Use correctly weighted empirical distributions for q50 conditional mixtures, including residual mass. Do not treat every selected branch as equally probable.

Compute:

- Cumulative distributional drift from P0 to Pt.
- Adjacent distributional drift from Pt to P(t+1).
- Continuous W1 between relevant outcome distributions.
- Monte Carlo uncertainty and estimator-boundary diagnostics.
- Comparison with independent direct estimates where available.

For binary event probabilities, analyze the exact conditional-mixture identity:

\[
P_t(E)-P_{t+1}(E)
=
\sum_{w\ne g_t}q_t(w)
[P_{t,w}(E)-P_{t,g_t}(E)].
\]

Measure signed contributions, cancellation, concentration among selected tokens and the contribution of the residual mixture.

Use the same greedy-reference estimate on both sides when evaluating the empirical identity. Separately test whether independently constructed estimates of theoretically identical laws agree within sampling uncertainty.

**Do not claim that verifying this identity is a novel scientific discovery.**

The potentially interesting empirical question is whether consequential local alternatives systematically cancel in the aggregate outcome distribution.

Do not apply this linear decomposition directly to W1 or ED.

Do not interpret cumulative distributional drift as a statistically established change point.

Formal BEAST/PELT fitting is not required for this iteration.

## 7. Analysis E - Next-token uncertainty versus future variability

Using the conditional continuation ensembles, estimate the decomposition:

\[
\operatorname{Var}(Y_h\mid G_t)
=
E_W[\operatorname{Var}(Y_h\mid G_t,W)]
+
\operatorname{Var}_W(E[Y_h\mid G_t,W]).
\]

Study how much future variability is associated with the choice of the next generated token versus subsequent stochastic continuation.

Use q50 weights and account for the residual group.

Treat the selected-token-plus-residual partition as a coarsening of full token identity. Its between-group variance is not necessarily the full between-token variance.

Correct or explicitly quantify finite-sample upward bias in estimated between-group variance. A bias-corrected estimate can be negative.

Investigate relationships with:

- q50 entropy.
- p_sel entropy.
- Token probabilities.
- Numerical jump magnitude and direction.
- Forecast horizon.
- Dataset and context regime.

Keep original-series dependence explicit.

This is a secondary exploratory analysis. Do not let it delay the primary precision decision.

## 8. Scientific standards

For every major finding, distinguish:

- **Observed:** directly established by the available data.
- **Suggested:** a plausible interpretation.
- **Unverified:** a hypothesis requiring independent validation.
- **Refuted within scope:** a specific claim contradicted by the available evidence.

Actively test alternative explanations involving sampling noise, normalization, tokenization, probability, numerical jump, source-series dependence, and selection bias.

Investigate the pathological IQR behavior of M4/T000049 explicitly. Retain raw and protocol-normalized metrics, and perform labeled normalization sensitivity analyses without silently changing the main estimand.

Do not treat six original series as a large independent population.

Do not use the same noisy ranking simultaneously to select interesting forks and claim independent validation of those selections.

Avoid proposing new metrics solely because they are mathematically possible. Every analysis must serve a concrete scientific question.

## 9. Outputs

Keep the documentation simple.

Create one main report:

`docs/reference/LOCAL_PILOT_OFFLINE_ANALYSIS.md`

Store detailed CSVs, figures and analysis artifacts in a new, clearly identified subdirectory under the existing ignored pilot result directory. Do not overwrite the original pilot outputs.

Add reusable analysis code and focused tests only as necessary.

The main report must include:

1. Exact data and Git provenance.
2. Reproduced baseline statistics and any discrepancies.
3. N20/N30/N40/N60 precision and ranking results.
4. W1/ED analyses across temporal supports.
5. Noise-adjusted interpretation of temporal propagation.
6. Continuous CPD and cancellation findings.
7. Token-choice variance decomposition, if supported.
8. Three to five ranked scientific findings, including negative results.
9. Alternative explanations and the most informative falsification test for each.
10. A concrete recommendation for the full exploratory campaign's sampling design.

For the campaign recommendation, specify:

- Whether uniform N20 is defensible.
- Whether N40/N60 materially improves the desired estimates.
- Whether a two-tier exploration/validation strategy is preferable.
- How independent series should be prioritized.
- Which analyses should be prespecified before collection.
- What cannot be resolved using the current six-series pilot.
- Estimated computation and storage trade-offs based on measured costs.

Update `FPA_STATUS.md`, `FPA_HANDOFF.md`, and the current task status.

Append to `FPA_DECISIONS.md` only actual researcher-approved decisions. Do not present your recommended sampling strategy as already approved.

Regenerate the ChatGPT handout with the new report, relevant figures and CSVs, without reintroducing obsolete archives.

Leave Git operations to the researcher. Report the exact changed files and tests executed.

## 10. Stopping condition

**STOP after the offline analysis and campaign recommendation.**

Do not automatically run the full campaign or generate additional Chronos trajectories.

The next step is scientific review by ChatGPT and the researcher, followed by an explicit decision on the large local exploratory campaign.

The goal is not to manufacture positive findings.

**The goal is to determine what the existing results establish, what they fail to establish, and how to collect the next dataset so that the most important scientific questions can actually be answered.**
