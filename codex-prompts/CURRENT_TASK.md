# Current task - exploratory discovery (COMPLETE; STOP FOR SCIENTIFIC REVIEW)

Started 2026-11-24 on clean main at 302b98782cd5ed5a25754c44501526d85b2226cb.
Evidence: result/exploratory_benchmark_20261124T095906Z/.
All bounded collection, independent validation and replay phases are complete.
The supervisor addendum received 2026-11-26 changes interpretation/literature
priorities only; no UCR, Kronos or extra inference was executed.
The requested final code/mathematical audit is complete; 299 offline tests pass.
Read the [final report](../docs/reference/FPA_EXPLORATORY_BENCHMARK_AND_FINDINGS.md)
and [handoff](../docs/research/FPA_HANDOFF.md). Original ceilings remain below.
No Git writes, dependency changes, additional model or broader campaign.

---

# NEXT CODEX ITERATION
## Exploratory FPA: Scientific Discovery, Benchmarking, Sampling, Training Exposure, CPD H64 and White-Box

### Overall scientific objective

We are moving from implementation validation toward scientific discovery.

**Central Paper 1 question:**

Does intervention-based exploration of autoregressive TSFM generation reveal useful information about future trajectories, consequential decisions or predictive uncertainty that conventional methods do not recover as effectively at comparable computational cost?

The goal is to discover and characterize interesting phenomena, investigate their reproducibility, and identify the strongest potential contribution for Paper 1.

**This is an exploratory research iteration, not a definitive confirmatory campaign.**

Prioritize scientific insights over exhaustive statistical analysis.

Do not turn this task into another general audit of Monte Carlo estimators.

However, do not promote sampling fluctuations into scientific findings.

### 1. Verify project state

Read the authoritative project documentation:

- `AGENTS.md`
- `docs/README.md`
- `docs/research/FPA_NORTH_STAR.md`
- `docs/research/FPA_HYPOTHESES.md`, or its actual current reference path
- `docs/research/FPA_PROTOCOL_EXPLORATORY.md`
- `docs/research/FPA_STATUS.md`
- `docs/research/FPA_HANDOFF.md`
- `docs/research/FPA_DECISIONS.md`
- `docs/reference/FPA_EXTENDED_BATCH_REPORT.md`
- `docs/reference/LOCAL_PILOT_OFFLINE_ANALYSIS.md`
- Relevant historical Chronos and TimesFM findings.

Verify the actual local branch, HEAD, working tree, model revision and available experimental artifacts.

Last GitHub `main` HEAD verified:

`302b98782cd5ed5a25754c44501526d85b2226cb`

The actual local source state takes precedence. Clearly distinguish committed sources from local modifications.

Preserve all previous data, experiments, reports and manifests.

No Git staging, commits, pushes, pulls or branch changes by Codex.

### 2. General research philosophy

We need to distinguish three stages.

**Discovery**

Explore freely. Look for patterns, unexpected behaviours, temporal structures, modes, rare events and counterexamples.

Use visualizations and descriptive statistics.

Do not require a corrected statistical significance test before investigating a potentially interesting observation.

**Reproducibility**

Before presenting an observation as a supported finding, verify it on independent Monte Carlo streams.

For new H32 experiments:

- Use N60 conditional continuations.
- Collect three independent N20 blocks.
- Use block 0 for exploratory selection.
- Keep blocks 1 and 2 independent for holdout evaluation.

**Targeted validation**

For a bounded number of promising observations, collect fresh independent ensembles.

Do not validate every exploratory pattern.

Do not increase sample size automatically when a result is unfavourable.

A non-reproduced observation remains a useful exploratory hypothesis or negative finding, not a confirmed effect.

### 3. Main objective A: benchmark FPA against conventional methods

Start with the existing saved trajectories.

Compare FPA against the following approaches whenever they can be evaluated faithfully:

1. Natural autoregressive trajectory sampling.
2. Token probability, local entropy and probability margin.
3. Numerical jump magnitude and direction.
4. Forecast variance and quantile interval width.
5. Trajectory-diversity measures.
6. Dense FPA.
7. Sparse FPA.
8. Numerical-diversity and stratified token selection.
9. Trajectory grouping or clustering.
10. SGA, when a faithful implementation is feasible.

Investigate the paper:

*SGA: Uncertainty Quantification for Multi-Step Forecasting in Time Series Foundation Models*
arXiv:2609.28582.

Identify its exact inputs, algorithm, assumptions, public implementation availability and evaluation protocol.

Do not substitute generic clustering for SGA while retaining the SGA name.

If full SGA is not feasible in this iteration, explicitly document what prevents a faithful comparison and implement only separately labelled, justified baselines.

#### Benchmark A1: forecasting uncertainty

Evaluate how well different methods identify forecasts associated with higher actual forecasting errors.

Use the same windows, horizons and ground-truth targets.

Ground truth must never enter the uncertainty indicator itself.

Investigate the evaluation metrics used by SGA, including ranking-based uncertainty evaluation, where applicable.

Existing windows may support initial exploration, but do not claim reliable dataset-level generalization from only a few independent series.

#### Benchmark A2: discovery of consequential futures

This is potentially the more distinctive FPA benchmark.

Evaluate how efficiently each exploration method discovers:

- Large excursions.
- Direction changes.
- Threshold crossings.
- Persistent trajectory differences.
- Rare but plausible future behaviours.
- Different trajectory modes.
- Alternative future scenarios.

For each method, measure:

- Number and diversity of behaviours discovered.
- Coverage of relevant outcomes.
- Missed consequential branches.
- Stability across independent samples.
- Actual inference cost.

At matched computational budgets, distinguish:

1. What ordinary sampling discovers.
2. What FPA discovers by imposing alternatives.
3. What both discover.
4. What cannot be resolved because the evaluation reference is incomplete.

Do not infer that a future behaviour is impossible under natural sampling merely because it was absent from N60 or N120 ordinary trajectories.

When possible, use token probabilities and conditional event probabilities to estimate the natural probability mass of consequences exposed by forced branching.

Do not count artificial frequency increases caused by deliberately forcing rare tokens as naturally occurring probability mass.

### 4. Main objective B: dense versus sparse and sampling efficiency

Use previously collected dense ensembles as exploratory references.

Investigate:

- All available b0..9 positions.
- Early-only positions.
- Regularly spaced positions.
- Random position selection.
- Adaptive position selection based on information available before branching.
- Probability-ranked token selection.
- Numerical-diversity and stratified token selection.
- Different sample allocations per branch.
- Grouped conditional outcomes.

Measure the trade-off between computational budget and scientific information retained.

Explore whether the most consequential forks concentrate in certain positions or regimes.

Identify examples where sparse exploration succeeds and examples where it misses important alternatives.

**Critical methodological constraint:**

Our current dense reference covers only the available positions and explicitly selected tokens. It is not a complete oracle over all possible forks.

Do not evaluate unobserved token-selection policies as though their alternatives had been collected.

Use exact offline subset comparisons where valid.

Where an alternative selection policy requires unsaved conditional trajectories, mark that comparison as requiring new inference rather than manufacturing results.

Use separate data for choosing a policy and evaluating its performance wherever feasible.

Sampling efficiency should initially be treated as an experimental tool. It becomes a potential paper contribution only if a meaningful and reproducible cost-information advantage emerges.

### 5. Main objective C: training exposure and possible memorization

Continue with Chronos-T5-mini.

Do not use Chronos-2 or develop a new forking mechanism.

Investigate whether the behaviour of FPA differs between series or temporal regions potentially exposed during Chronos-T5 pretraining and genuine zero-shot evaluation data.

Use the original Chronos publication and documented dataset provenance.

**Exposure is not synonymous with memorization.**

#### Existing datasets

Begin with:

- M4 Daily.
- ERCOT.
- Exchange Rate.

Verify the published pretraining and evaluation classifications.

For M4 Daily, investigate the training/test temporal boundary.

The current H32 experiment may include both potentially training-exposed and held-out future observations.

Verify this against the exact dataset exports before drawing conclusions.

#### Additional datasets

Prioritize a comparison within a similar forecasting domain.

Candidate pairs:

**Hourly electricity**

- Electricity Hourly, in-domain.
- ERCOT Load, zero-shot.

**Half-hourly electricity**

- London Smart Meters, in-domain.
- Australian Electricity, zero-shot.

Select one in-domain dataset and one zero-shot dataset for the new H32 collection.

Prefer the pair offering the best combination of documented provenance, matching frequency, comparable original-series characteristics and data availability.

Do not assume that equal frequency and domain imply equivalent data-generating processes.

Document differences in aggregation, seasonality, number of original series and scale.

#### Exposure experiments

Record for each experimental window:

- Dataset and original-series identifier.
- Documented pretraining status.
- Source split and version.
- Temporal training/test boundary where available.
- Forecast origin and horizon.
- Context characteristics.
- Forecast error.
- Token uncertainty.
- FPA sensitivity.
- Consequential future outcomes.
- Trajectory diversity.

Where possible, compare potentially exposed and held-out targets **at equal forecast lead times**.

Do not mistake the difference between early and late prediction horizons for a memorization effect.

Preserve uncertainty about whether a particular training segment was actually sampled during pretraining.

Look for patterns suggesting exposure-related changes in:

- Branching sensitivity.
- Predictability.
- Forecast quality.
- Future-mode diversity.
- Persistence or reconvergence.

Clearly distinguish:

1. Exposure association.
2. Evidence compatible with memorization.
3. Evidence specifically supporting memorization.

Do not claim level 3 from dataset membership alone.

This study should be lightweight and integrated into the rest of the experiments.

### 6. New H32 collection: N60 with independent blocks

Only after the offline exploration and dataset-provenance checks, execute the following bounded collection.

**Maximum collection:**

- Two newly added dataset identities.
- Three original-series windows per dataset.
- Six new H32 windows in total.
- Context length C512.
- Horizon H32.
- Fork positions b0..9.
- Original q50/token policy.
- Maximum eight explicitly selected tokens including greedy.
- Residual conditional ensemble preserved.
- Independent greedy-reference and same-token controls.
- N60 per conditional ensemble, implemented as 3 independent N20 blocks.

Keep the pinned Chronos-T5-mini revision and decoder invariants.

Preserve the entire token sequence and numerical trajectory for every sample.

Keep the existing bounded white-box capture and replay metadata.

Freeze dataset selection, source hashes, window origins and RNG streams before inference.

Select windows using context-only criteria.

Do not select new experimental windows from FPA outcomes.

#### Block usage

**Block 0, N20**

Exploration and candidate selection.

**Blocks 1 and 2, independent N40**

Evaluate whether the selected candidates survive independent sampling.

**Pooled N60**

Produce more precise descriptive estimates, while explicitly acknowledging that the pooled data contain the selection block.

Do not treat pooled N60 as an independent replication.

### 7. Fresh independent validation: N120, strictly bounded

Allocate a separate validation budget only for the most informative candidates.

**Maximum: eight distinct contrasts in total.**

- At most six scientifically selected contrasts.
- At least two randomly selected eligible control contrasts, where the available cohort permits.
- No more than two validation contrasts per window.

Select these contrasts using the exploratory results, then freeze their identities, hypotheses and validation outcomes before generating fresh trajectories.

For each validated contrast, collect:

- N120 fresh alternative trajectories.
- N120 fresh greedy-reference trajectories.
- N120 fresh same-token null trajectories.

Reference/null ensembles may be shared across contrasts at the same fork only with correct covariance accounting.

Use independently seeded streams unrelated to the dense blocks.

The fresh validation allocation is at most eight contrast evaluations; avoid generating duplicated reference ensembles unnecessarily.

Prioritize candidates representing different scientific mechanisms, not merely the largest W1.

Examples:

- A fork changing the probability of a particular future mode.
- A strong persistent effect.
- A transient effect or reconvergence.
- A candidate missed by sparse exploration.
- A difference between exposure categories.

The random controls are necessary to assess selection enrichment.

Do not select all validation targets from the same dataset or type of effect if diverse candidates exist.

**Scientific goal:** determine which exploratory findings survive fresh sampling and whether their effects are large enough to matter.

N120 is a fixed validation budget, not a guarantee of adequate power.

If the effect remains unresolved, report that limitation. Do not automatically increase N.

### 8. New natural-sampling evaluation reference

For each of the six new H32 windows, collect an additional **independent N120 natural-sampling ensemble**.

These trajectories are reserved for evaluating coverage and consequence discovery.

They must not be used for selecting candidate forks or choosing which methods to benchmark.

Distinguish the natural-sampling evaluation reference from a ground-truth oracle.

A behaviour absent from this finite sample remains unobserved, not impossible.

Measure actual sampling and inference costs.

Where possible, compare methods both at equal trajectory budgets and at equal measured runtime budgets.

### 9. CPD H64: exploration followed by targeted validation

Implement a small extension to:

- Forecast horizon H64.
- Greedy-prefix positions P0..P30.
- Up to three original-series windows.

Use consistent absolute future outcomes across all positions.

#### CPD Stage 1: exploratory collection

For each prefix P0..P30:

- N60 direct trajectories.
- Three independent N20 blocks.
- Independent RNG streams.
- Identical outcome definitions across the curve.

Do not automatically perform full dense FPA over all 30 token positions.

Focus on outcome-distribution evolution along the greedy path.

Examine:

- Smooth evolution.
- Apparent transitions.
- Reconvergence.
- Sudden shifts.
- Stability periods.
- Outcome-probability changes.

Use plots, trajectory examples and uncertainty bands to locate interesting patterns.

Do not interpret isolated changes between neighbouring estimates as actual change points.

#### CPD Stage 2: targeted validation

Freeze at most:

- Two candidate transitions per window.
- One randomly selected control transition per window.

A transition is a comparison between two explicitly identified prefix positions.

Collect fresh independent N120 direct trajectories for each required prefix distribution, reusing a prefix ensemble across comparisons when appropriate.

Maximum: three transition comparisons per window, involving at most six fresh prefix ensembles per window.

Do not increase the number of candidates after inspecting validation results.

Distinguish:

- Changes reproduced across seeds.
- Changes explained by ordinary Monte Carlo variation.
- Changes possibly caused by increasing greedy conditioning.
- Outcomes that remain unresolved.

Do not fit elaborate change-point models unless a meaningful reproducible pattern emerges.

A negative CPD outcome is acceptable.

### 10. White-box: verify replay and begin scientific analysis

Before using internal activations, identify which of the following tests already exist and which remain unverified:

1. Exact token-path replay.
2. Numerical forecast equivalence.
3. Logit equivalence.
4. Hidden-state equivalence.
5. Self-attention and cross-attention equivalence.
6. Reproducibility after model reload in a fresh process.

Do not repeat thousands of validated tests.

Perform only the missing targeted checks.

If the original execution did not preserve the tensors needed for a retrospective equivalence comparison, explicitly state what cannot be verified.

Distinguish teacher-forced deterministic replay from resampling the stochastic continuation.

Then perform a small exploratory white-box analysis on:

- A validated consequential fork.
- A weak or near-null fork.
- A same-token control.

Examine:

- Layer-wise representation differences.
- Temporal evolution after intervention.
- Attention patterns.
- Relationship between internal divergence and output divergence.

Use descriptive visualizations first.

Do not infer causal mechanisms from attention maps or representation distances alone.

No large probing model, SAE training or new interpretability framework in this iteration.

### 11. Analysis principles

For each scientific observation, answer:

**What happened?**

Describe the observed phenomenon using actual trajectories, quantitative results and examples.

**Why might it happen?**

Investigate a small number of plausible competing explanations.

**Does it reproduce?**

Check independent N20 blocks, independent N40 holdout and targeted fresh N120 where authorized.

**Why is it scientifically interesting?**

Explain how it changes our understanding of generative decisions or the utility of FPA.

**What would falsify the interpretation?**

Identify the next experiment that would distinguish competing explanations.

Use W1 and ED as measurement tools, not as the sole scientific outcomes.

Do not run large families of permutation tests by default.

Use appropriate uncertainty estimates and formal tests when they directly inform an important decision.

Do not aggregate dependent branches, horizons or repeated windows as independent population observations.

Preserve negative findings and counterexamples.

Prefer three strong scientific hypotheses over twenty weak statistical observations.

### 12. Required deliverable

Create one primary report:

`docs/reference/FPA_EXPLORATORY_BENCHMARK_AND_FINDINGS.md`

Structure it as follows.

#### I. Cold scientific assessment

- What we knew before this iteration.
- What this iteration adds.
- Which earlier hypotheses became more or less plausible.
- Which research directions remain unsupported.

#### II. Ranked scientific findings

Identify three to five major findings or hypothesis candidates.

For each, report:

- Scientific question.
- Observed evidence.
- Representative examples.
- Counterexamples.
- Reproducibility status.
- Alternative explanations.
- Novelty relative to FPA, Forking Fast and SGA.
- Most informative falsification experiment.

Do not invent five findings if only two are interesting.

#### III. Conventional-method and SGA benchmark

Explain:

- What was compared.
- Which comparisons are scientifically fair.
- Actual inference and computational costs.
- What ordinary sampling discovers or misses.
- What FPA discovers or misses.
- Where FPA has an advantage, if any.
- Where FPA is unnecessary or too expensive.
- Exact status of SGA reproduction.

#### IV. Sampling-efficiency study

Present dense/sparse comparisons, candidate selection methods, coverage, missed effects and runtime.

Separate offline simulations from methods actually executed prospectively.

#### V. Training-exposure study

Document dataset provenance, exposure status, matched comparisons and observed associations.

Explicitly state whether there is any actual evidence supporting memorization.

#### VI. CPD and white-box

Present the H64 findings, validation results, replay evidence and initial representation analyses.

#### VII. Paper 1 implications

Recommend:

1. The strongest defensible primary contribution.
2. The best alternative contribution.
3. The biggest unresolved scientific objection.
4. The most informative confirmatory experiment.
5. The conditions under which the current direction would need to change.

### 13. Execution constraints

Run offline analysis before new inference.

New inference is limited to:

**H32**
- At most six new windows.
- N60 dense conditional ensembles in three N20 blocks.
- At most eight fresh N120 contrast evaluations.
- One additional independent N120 natural-sampling evaluation ensemble per new window.

**H64**
- At most three new windows.
- At most 31 direct CPD prefix distributions per window.
- N60 exploratory trajectories per prefix.
- At most three targeted transition comparisons per window, using fresh N120 per required prefix distribution.

No unrestricted expansion, second model, training, fine-tuning or cloud infrastructure.

Dataset downloads are restricted to the two explicitly selected, provenance-verified datasets needed for this iteration. No unrelated downloads, model-weight changes or dependency upgrades without separate authorization.

Use the existing checkpointing, deterministic RNG identities, manifest verification and atomic publication mechanisms.

Run scientific-integrity checks before advancing to full collection.

If a correctness gate fails, stop the affected collection and document the issue.

Preserve historical outputs and local modifications.

Track measured runtime, RAM, disk usage and completed ensembles.

Do not silently replace failed or incomplete work with additional series.

### 14. Handoff and final stop

Update the active scientific status and handoff concisely.

Record the new researcher-approved experimental scope without rewriting historical decisions.

Regenerate the ChatGPT handout with:

- The primary scientific report.
- Key figures.
- Relevant analysis CSVs.
- Validation summaries.
- Dataset provenance.
- White-box reproducibility evidence.
- Execution and integrity checks.

Keep historical artifacts unchanged and avoid unnecessary documentation proliferation.

No Git staging, commits, pushes, pulls or branch changes.

**STOP after this bounded exploratory iteration.**

Do not launch a broader campaign, additional validation, more datasets or another model automatically.

The next ChatGPT-researcher review will decide which findings deserve the definitive Paper 1 campaign.

### Final scientific priority

**The purpose of this iteration is to discover scientifically interesting properties of autoregressive forecasting generation and determine what FPA contributes beyond conventional sampling.**

Statistical controls exist to protect findings, not to replace scientific exploration.

The desired output is a small number of insightful, reproducible phenomena with clear scientific implications, not another exhaustive catalogue of distance estimates.
