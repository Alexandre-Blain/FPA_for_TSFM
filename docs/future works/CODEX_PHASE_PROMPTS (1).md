# Codex Prompts: Chronos FPA Paper 1

**Companion specification:** `FPA_CHRONOS_RESEARCH_PLAN.md` (place both files in the same repository folder, e.g. `docs/research/`).

**Start with Prompt 1. There is no Phase 0.** A broad audit has already been completed. Its conclusions are background, not instructions to repeat the audit. Send only **one prompt at a time**, after reviewing the previous phase's output. Do not paste all five prompts into Codex as a single job.

---

## PROMPT 1 - Implement both distances, raw trajectory saving and necessary controls


```text
You are working in my existing Chronos Forking Paths Analysis (FPA) research repository.

Read `docs/research/FPA_CHRONOS_RESEARCH_PLAN.md` in full. It is the active scientific specification for Paper 1. If I placed it elsewhere, locate it by exact filename. The repository has already undergone a comprehensive Codex audit; do NOT perform another broad audit or an offline investigation phase.

THIS IS PHASE 1. You are AUTHORIZED to implement only the small additive code changes and focused tests described below. You are NOT authorized to start a new benchmark scan or a costly inference campaign.

Scientific objective: compare, on the SAME sets of sampled Chronos continuations, both:
  A) Mean horizon-wise empirical marginal Wasserstein-1 (W1).
  B) Multivariate Energy Distance (ED) over complete strictly post-fork numeric trajectories.

The reference intervention must force the greedy token and then SAMPLE the suffix, just like every alternative. The prefix before the fork must be identical. Distinguish the numeric effect at the forced token b from subsequent propagation at indices b+1,...,H-1. The continuation law is defined by the ACTUAL decoder (reported temperature=1, top_k=50 and valid-token masking), not automatically by untruncated model softmax.

WORKFLOW:
1. Inspect only the specific existing decoding, tokenization, metrics, export and tests needed for this change. Verify the relevant observations in the previous audit: indexing of b, decoder sampling policy, arrays available in memory, candidate probability definitions, use of historical metrics, and whether individual paths are already saved. Do not duplicate the comprehensive audit or repair old refinement experiments.
2. Before edits, give a concise file-by-file patch plan. Then implement directly, without waiting for another confirmation unless a blocking ambiguity changes the scientific meaning or requires a breaking interface change.
3. Implement exact empirical one-dimensional W1 for the sampled distributions at each strictly downstream horizon. Save the W1-by-horizon vector and its mean. In the equal-sample-size case the exact empirical formula is mean_i |sorted(A[:,h])[i] - sorted(B[:,h])[i]|. If unequal sizes are supported, compute exact empirical W1, not the old nine-quantile approximation.
4. Implement trajectory-level Energy Distance on the same post-fork arrays, with per-step RMS Euclidean ground distance rho_L(x,y)=||x-y||_2/sqrt(L) and the explicitly documented V-statistic estimator:
      2*mean_pairwise_cross - mean_pairwise_within_A - mean_pairwise_within_B.
   The empirical V-statistic is not expected to be zero under independent equal-law samples. Keep the ED convention (no undocumented square root) and do not interpret ED as a pure dependence-change measure.
5. Save raw and context-IQR-normalized versions of W1, ED and direct token jump. Invalid or near-zero context IQR must be flagged, with raw outputs retained. Do not silently use future truth or a different scale as denominator. Preserve the existing historical score and column definitions; new metrics must have distinct names.
6. Add a same-token/two-INDEPENDENT-ensembles null-control path, with tracked seeds/RNG streams. A comparison of one saved ensemble to itself is NOT an acceptable null. Reuse existing sampling utilities and avoid expensive redundant generation.
7. Add opt-in saving of the INDIVIDUAL NUMERIC sampled suffix trajectories plus a minimal metadata manifest: series/window IDs, b, forced-token IDs and decoded values, candidate probabilities/rank, context scaling and invalid-scale flags, model ID/revision if available, exact decoder settings, sample count, RNG identifiers, code version, file paths, shapes and dtypes. Store reference ensembles once per fork point when practical. Preserve old output directories and compatibility.
8. Add focused tests with known mathematical answers: W1 constant shift; ED zero on identical empirical sets; ED positive for path ensembles with the same time marginals but different temporal pairings; deterministic-path ED=2*rho; correct exclusion of forced coordinate; b=H-1 empty suffix; independent same-token null not assumed zero; normalization edge cases; saved/reloaded sample parity. Include a tiny smoke check if the checkpoint is already cached and it is cheap. Never initiate a large download or benchmark run for the smoke check.
9. Keep dependencies and code changes minimal. No new framework, no BEAST/hazard/MI implementation, no sophisticated morphology engine, no TimesFM, no attacks and no changes to historical runs.

DELIVER AT THE END OF PHASE 1:
- Changed-file list with the reason for each change.
- Exact implemented formulas and units, with any deviation from the research specification called out.
- Test results and any remaining failures.
- Output file/manifest schema and a small shape/example preview.
- Compatibility assessment with the existing scan and its legacy outputs.
- A concise proposal for the smallest useful Phase 2 pilot: exact branches/series selection principles, tentative N choices, cost and data storage. Do not run that pilot yet.

Stop after Phase 1. Do not automatically continue to another phase. Flag genuine scientific ambiguities instead of inventing defaults.
```

---

## PROMPT 2 - Controlled pilot, sampling noise and first morphology candidates

```text
Read `docs/research/FPA_CHRONOS_RESEARCH_PLAN.md` and the approved Phase 1 implementation report. THIS IS PHASE 2 ONLY.

First propose a small stratified inference plan and an explicit estimated budget: original series, windows, branch positions, candidate token likelihoods, numeric jump sizes, number of reference/alternative samples, seeds, compute and output storage. Include independent same-token controls. Use the sample counts N=20/50/100 only as a candidate range, not a compulsory full grid.

Do not start nontrivial inference until I explicitly approve the budget.

After approval:
1. Generate the minimum stratified sample needed to compare W1_post and ED_post, their null noise floors, and the influence of N, direct jump, candidate probability and branch position. Save the exact individual sampled trajectories and metadata.
2. Reassess the historical intuitions rather than trying to confirm them: apparent large forks after implausible tokens; immediate displacement versus post-fork propagation; entropy/likelihood associations conditional on the numeric jump; sensitivity to scale and partial candidate coverage. Separate within-series and between-series patterns.
3. Keep W1 and ED independent. If they disagree, explain which properties they each measure; do not assume ED detects a pure change in temporal dependence unless marginal differences are controlled.
4. Start MORPHOLOGY EXPLORATION using already saved samples: shortlist a few clear, medium, near-null and counterexample forks. For each candidate inspect BOTH sampled conditional ensembles and distinguish a changed median from a change in per-path event frequency. Seek plateau-to-trend, peak/timing changes, trend reversals, amplification and reconvergence only if they actually occur. Do not implement a classifier or claim motif classes are generally sensitive.
5. Provide a concise null-noise and effect-size report, negative results, morphology candidate IDs, and a minimum Phase 3 design.

Stop after the pilot report; do not start the large confirmation experiment.
```

---

## PROMPT 3 - Confirmatory experiments on the strongest surviving claims

```text
Read the active plan and approved Phase 1-2 outputs. THIS IS PHASE 3 ONLY: confirmatory study, not method development.

Before model inference, propose and freeze a budgeted protocol: primary questions/contrasts, population of original series, window/origin design, candidate eligibility and p thresholds, sample sizes, both W1 and ED conventions, same-token controls, numeric-jump controls, normalization rules, fork horizon handling and cluster-aware uncertainty procedure. Prioritize additional independent series over more overlapping windows on the same few series.

Wait for my explicit budget approval before running new inference.

Then:
1. Run only the approved design, storing all individual numeric trajectories and reproducibility metadata.
2. Confirm or reject whether downstream sensitivity differs from the direct numeric token jump; whether probability/entropy associations remain after numeric-jump and series controls; and whether W1 and ED reveal meaningfully different forecast behaviors.
3. Account for alternative branches sharing prefixes/reference ensembles, overlapping windows and repeated observations within series. Never compute IID confidence intervals over branch rows as if they were independent series.
4. Report negative findings, uncertainty, observed effect sizes, coverage lost to probability thresholds, and the exact population to which each conclusion applies.
5. Consider a second Chronos checkpoint only as an explicitly priced optional robustness test, not a default requirement. No TimesFM, attacks, zero-shot benchmarking or topology discovery.

Return a ranked evidence report and a decision on which claims can support Paper 1. Stop before the Phase 4 final morphology atlas.
```

---

## PROMPT 4 - Descriptive morphological fork atlas and figures

```text
Read the active plan, especially its Section 6 (Morphological interpretation), and the approved Phase 2-3 sampled-trajectory datasets and results. THIS IS PHASE 4 ONLY.

Build a reproducible, DESCRIPTIVE atlas of what selected local token choices change in the subsequent forecasts, analogous in purpose to the interpretable outcomes shown in Bigelow's LLM FPA paper.

1. Select a small gallery of strong, medium, near-null and counterexample forks from a documented candidate pool. Record how many candidates were inspected and the exact series/window/fork/token/seed identifiers. Do not cherry-pick examples while implying they are typical.
2. Distinguish morphology near the source fork from morphology of the future conditional continuations. Reference shape annotations using values generated after b are retrospective, not available prospectively at b.
3. For each chosen example, show: historical context and shared generated prefix; forced reference/alternative token value and probability; both sampled ensembles and their labelled summaries; W1-by-horizon, scalar ED, direct token jump, normalized/raw units and same-token noise diagnostics.
4. Characterize only features required by the example: plateau-like behavior, slope in actual time/value units, peaks/troughs and prominence/timing, trend reversal, divergence and reconvergence. Do not describe a slope as 45 degrees because graph angles depend on plotting aspect ratio.
5. If claiming an event becomes more common, evaluate it per individual sampled trajectory with a predeclared event rule and give observed counts/proportions and uncertainty. Do not infer a full-trajectory event probability from a median or from q90 crossing a threshold.
6. Include negative/counterexample cases and flag any attractive narratives that do not survive ensemble inspection. No new topology method, no motif-level sensitivity law by dataset, no extensive classifier.

Deliver a small set of figure candidates and scripts, reproducible captions, provenance table and exactly supported scientific statements. Default to no new inference. If an image needs additional samples, propose a narrow budget and wait for approval.

Stop before writing a manuscript.
```

---

## PROMPT 5 - Scientific synthesis and publication strategy

```text
Read the active plan and approved reports from Phases 1-4. THIS IS PHASE 5 ONLY. Do not draft the paper yet.

Act as a critical scientific coauthor, not a project manager seeking completion at any cost.

1. Identify the most important scientific questions and the exact meaning of each metric. Group results into at most 2-3 major findings. For each: direct evidence, plausible interpretation, alternative explanations, statistical limitations, novelty relative to Bigelow and other prior work, and a falsifying experiment.
2. Assess whether the results survive controls for sampling noise, numeric forced-token jump, candidate likelihood, normalization, correlated windows and between-series effects.
3. State explicitly whether each morphology figure demonstrates an ensemble-level phenomenon, a selected illustrative path, or a reproducible event-frequency difference. Do not manufacture a general topology contribution.
4. Perform a targeted literature review of Bigelow, Chronos, forecasting sensitivity and time-series morphology. Verify sources; distinguish established techniques from original contributions.
5. Evaluate the suitability of a CORE/ICORE B venue as a CONDITIONAL target, A only if the result and coverage justify it. Report likely reviewer objections and avoid claiming publication is assured.
6. Propose a paper title, 2-3 principal contributions, sections, figures, limitations, reproducibility artifacts and ONLY any genuinely blocking experiments.
7. Keep TimesFM, optimization, memorization, attacks and broader explainability algorithms as future research unless the data justify a different direction.

Return a ranked scientific findings memo and manuscript outline. Do NOT write the manuscript or run further experiments without my separate approval.
```

---

## If Codex proposes unnecessary additional scope

```text
Critically audit your proposed work against Paper 1's actual research questions. For each additional feature, explain what specific claim it makes testable and why it blocks the current phase. Remove work justified only by generality, extensibility or mathematical sophistication. DO NOT remove the two required distances, direct/post-fork separation, independent same-token controls, raw trajectory export or descriptive morphology. Continue only within the approved phase and budget.
```

