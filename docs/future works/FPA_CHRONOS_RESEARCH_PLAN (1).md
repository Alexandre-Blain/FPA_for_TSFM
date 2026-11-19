# Forking Paths Analysis on Chronos: Paper 1 Research and Implementation Plan

**Status:** Active scientific specification, to be used with `CODEX_PHASE_PROMPTS.md`.
**Scope:** First research paper on token-based autoregressive time-series forecasting with Chronos v1.
**Execution:** Start directly at **Phase 1**. A broad repository audit was already conducted; there is **no standalone Phase 0**.
**Evidence:** Historical counts and code observations below are findings *reported by the existing Codex audit*. The agent must verify relevant details against the checkout when implementing, not redo the entire audit.
**Governing principle:** Build the smallest scientifically defensible extension of the existing Chronos FPA pipeline. Do not treat future research ideas as implementation requirements.

## 1. Scientific objective and intended contribution

### 1.1 Central research question

> How do plausible local token decisions in autoregressive time-series foundation models change the distributions of future numeric forecasts, and how can those changes be interpreted as meaningful transformations of temporal trajectories?

The project adapts the **conditional branching principle** of Bigelow et al., *Forking Paths in Neural Text Generation* (ICLR 2025, arXiv:2412.07961), to **Chronos v1**, a model that tokenizes and autoregressively generates numeric time-series values.

Paper 1 should aim for three **candidate** contributions, without presuming they will all be demonstrated:

1. **A reproducible Chronos FPA protocol:** a fixed greedy prefix, a forced reference or alternative token, stochastic continuations under a declared decoding policy, and statistically justified distances between conditional forecast distributions.
2. **Empirical characterization of branching:** disentangle immediate numeric displacement, downstream effect, propagation dynamics, token probability, local entropy, and Monte Carlo estimation noise. Retain only findings that survive controls.
3. **Morphological interpretation:** show with reproducible examples how an alternative token changes subsequent forecast shapes or events: plateau-like behavior to trend, shifted/extinguished peaks, persistent troughs, divergence followed by reconvergence, etc.

**Do not claim**: an uncertainty calibration method, causal explanation of forecasting errors, an automatic topology-discovery algorithm, or a dataset-independent sensitivity law without appropriate evidence.

### 1.2 Non-goals for Paper 1

Do not implement:

- TimesFM or other numerical-patch fork methods.
- Copula-based trajectory synthesis or generic architecture adapters.
- Adversarial attacks, input-history perturbation pipelines, backdoors, or memorization extraction.
- BEAST change-point inference, Bigelow survival/hazard modeling, or mutual-information estimation.
- A learned morphology classifier, persistence-homology toolkit, automatic ranking of sensitive motifs, or a new composite morphology score.
- A general-purpose distribution-distance framework or major performance refactor unrelated to actual bottlenecks.
- A full forecast-accuracy or zero-shot benchmark. Forecast quality is ancillary context, not Paper 1's primary target.
- Repairing all early experiments with inconsistent provenance unless a critical claim genuinely depends on them.

These subjects may be mentioned briefly in future-work notes, but are **not Codex action items**.

### 1.3 Required versus conditional deliverables

| Required for Paper 1 | Conditional / only after evidence |
|---|---|
| Correct mathematical definition of the generation and intervention policy | Second Chronos model size/checkpoint |
| Both marginal W1 and trajectory Energy Distance on the same saved continuations | Alternative joint-distance estimators |
| Direct-token versus downstream-effect separation | General branch-position probability-weighted scores |
| Same-token/two-independent-ensemble noise controls | Event probabilities for every imaginable motif |
| Saved raw sampled numeric trajectories and reproducible metadata | Extensive motif benchmark or topology pipeline |
| Critical testing of existing findings, including negative findings | New architecture or adversarial application |
| Representative, auditable morphology figures | Statistical claim that some motif class is intrinsically more sensitive |

---

## 2. Existing implementation and evidence: reported, not newly verified here

Reference paper: Bigelow et al. (2025), https://arxiv.org/abs/2412.07961.
Model paper: Ansari et al., *Chronos: Learning the Language of Time Series* (2024), https://arxiv.org/abs/2403.07815.

Reported repository modules:

- `code/chronos_fpa/core/chronos_decoding.py`: forced-token decoding and stochastic continuation.
- `code/chronos_fpa/core/chronos_io.py`: model, numeric tokenization, scaling and decoding.
- `code/chronos_fpa/metrics/chronos_analysis.py`: horizon-level quantile distances.
- `code/chronos_fpa/metrics/chronos_score.py`: legacy weighted composite.
- `code/chronos_fpa/metrics/chronos_scales.py`: propagation descriptors.
- `code/chronos_fpa/analysis/chronos_uncertainty_alignment.py`: entropy and uncertainty analyses.
- `code/chronos_fpa/analysis/chronos_scenario_sensitivity.py`: existing scenario outcomes.
- `scripts/runs/run_chronos_benchmark_scan.py`: scan entry point.

Reported clean September 2026 run: `result/clean_confirm_no_refinement_20260915_114823`.

- Model: `amazon/chronos-t5-mini`.
- 15 original series, 63 forecasting windows, 252 branch positions, 1,008 alternative branches; 20 sampled continuations per forced token.
- Horizon `H=64`, relative branch indices `[0,4,8,16]`, top five candidate tokens including the greedy token.
- Data domains: ERCOT, Exchange Rate, M4 Daily; overlapping context/window origins.
- The historical continuation generator reportedly uses temperature 1, a valid-token mask and top-50 sampling; alternative selection uses masked, untruncated logits/softmax probabilities.
- The old distance profiles reportedly **include the forced coordinate** and are not strict post-fork measurements.
- Historical exports mostly save summary CSV/quantiles, not individual sampled trajectories. Search for raw paths once when implementing; do not assume their absence beyond the inspected outputs.
- The July top-15 refinement is partial/provenance-inconsistent, and should remain exploratory, not merged silently into the clean run.

Historical, **unconfirmed** findings worth testing:

- Rare alternatives generated extreme composite scores; filtering tokens at `p >= 0.1%` removed several extremes but not typical-sized effects.
- Entropy/composite correlations varied by dataset and score normalization; apparent Exchange Rate effects may reflect between-series differences.
- Initial jump and persistence or amplification may differ; the old score makes this difficult to interpret.
- Some forecast-summary outcomes change after forks, but historical summary labels do not establish event probabilities across individual trajectories.

**What the audit exposed:** the composite score is heuristic, its relative-amplification term can remain substantial as the absolute difference tends to zero, the shape-correlation convention is problematic for constant curves, same-token independent-sample controls are missing, and repeated overlapping observations are not independent.

**Do not promise the historical findings will survive** the replacement of the score. Negative results are legitimate scientific outcomes.

---

## 3. Mathematical formulation: what is being sampled

### 3.1 Indexing, tokens and numeric values

Let:

- `X = (x_1,...,x_C)` be the observed context for one time series/window.
- `H` be the number of forecasted numeric steps, indexed `0,...,H-1`.
- `b in {0,...,H-1}` be the chosen fork position.
- `z^g_<b` be the **fixed greedy generated-token prefix** up to but excluding position `b`.
- `w_0` be the valid greedy token at `b`; `w` be another valid candidate token.
- `v_X(w)` be the context-scaled, decoded numeric value associated with token `w` at position `b`.
- `p_sel(w | c_b)` be the candidate-selection probability at prefix `c_b = (X,z^g_<b)`.
- `pi(v | X,z_<t)` be the **actual policy used for stochastic continuation** after forcing a token. It may differ from the model's full untruncated distribution.

In the reported implementation, an approximate policy expression is:

\[
\pi_{\tau,K}(v\mid c) =
\frac{\mathbf{1}\{v\in\mathcal V_{\mathrm{valid}}\cap T_K(c)\}
\exp(\ell_v(c)/\tau)}
{\sum_{u\in\mathcal V_{\mathrm{valid}}\cap T_K(c)}\exp(\ell_u(c)/\tau)}.
\]

`T_K(c)` is the set admitted by the implemented top-k rule; the mask, tie policy, temperature and model-dependent constraints must be verified in code. **Do not assume** `p_sel = pi` or that a forced alternative is in the unforced continuation-policy support. Keep both probabilities, when meaningful, with distinct names.

The reference is **not one completely greedy trajectory**. Greedy generation fixes the prefix and reference token; *after that token*, the baseline and alternative continuations are sampled stochastically.

### 3.2 Intervention-conditioned continuation law

Define the strictly downstream numeric continuation:

\[
Y^{(b,w)}_{>b} = (Y^{(b,w)}_{b+1},\ldots,Y^{(b,w)}_{H-1})
\in\mathbb R^{L_b},\qquad L_b=H-b-1.
\]

Its law under the implemented decoder is:

\[
\widetilde P_{b,w}^{\pi} =
\operatorname{Law}_{\pi}\!\left(
Y_{>b}\mid X, z^g_{<b},\operatorname{do}(Z_b=w)
\right).
\]

The reference is `\widetilde P_{b,w_0}^{\pi}` with **independently sampled suffixes**. This is an *interventional decoding-policy-conditioned* distribution, not necessarily the full probabilistic model's original continuation law. The `do` notation is operational and refers to forcing a decoding token, not a causal intervention on the observed real-world process.

If `b=H-1`, `L_b=0`; the strict downstream metric is **undefined/not applicable**, not silently zero. It can still have a nonzero direct-token displacement.

### 3.3 Distinguish three estimands

1. **Direct token jump** (deterministic conditional on context and tokens):

   \[
   J_{b,w}=|v_X(w)-v_X(w_0)|.
   \]

   Record raw units and an optional context-normalized value. This is not propagation.

2. **Strictly downstream divergence**, comparing only indices `b+1,...,H-1`. This is the main target of both new distances.

3. **Total effect**, including the forced coordinate `b`. This may be useful for backward compatibility and figures, but must be named separately. **Never describe a total-effect score as purely downstream amplification.**

The original suffix before the forced token is identical by construction. Exact zero before `b` is therefore not evidence of stability; it is imposed by the experimental design.

### 3.4 Exact relationship to Bigelow (methodological inheritance, not code to reproduce)

Bigelow uses an outcome representation `R(Y)` of a generated continuation and, at a fixed prefix, defines the token-conditioned outcome expectation

\[
o_{b,w}=\mathbb E[R(Y)\mid c_b,Z_b=w],
\qquad o_b=\sum_{w}p(w\mid c_b)\,o_{b,w}.
\]

For categorical outcomes, `R` can be a one-hot event vector; the expected representation is then an outcome-probability vector. Bigelow analyzes such outcome distributions and uses downstream change-point/survival analyses. Our immediate paper instead compares **numeric conditional forecast laws**, first by marginal W1 and then full-path ED, and optionally illustrates specific `R`-type temporal events from sampled paths. This is an adaptation, **not** a claim that the numeric distances or branching idea were invented here.

The mixture identity above is over the **complete candidate selection distribution**; a top-k-only sum without renormalization or residual-mass accounting is not the same mixture. No probability-weighted mixture or Bigelow hazard estimator is required in Paper 1.

---

## 4. Both required distances: population definitions, estimators and caveats

Use the **same stored sampled numeric trajectories** for both distances. Implement two direct functions in the existing metrics module or a small adjacent module; do not create a generic distance registry.

Let `A = (a_1,...,a_n)` and `B = (b_1,...,b_m)` be samples from the reference and alternative strictly post-fork continuation laws, each element a vector in `R^{L_b}`. Typical planned pilot uses equal sample counts `n=m=N`, but avoid assuming equality throughout the code unless explicitly enforced.

### 4.1 Distance A: mean marginal Wasserstein-1, `W1_post`

For each downstream horizon `h = b+1,...,H-1`, let `P_h` and `Q_h` be the one-dimensional marginal laws of the sampled numeric value at `h`.

\[
W_1(P_h,Q_h)=\int_0^1|F^{-1}_{P_h}(u)-F^{-1}_{Q_h}(u)|\,du.
\]

Our main horizon-aggregated marginal distance is:

\[
D_{\mathrm{W1}}^{\mathrm{post}}(b,w)
=\frac{1}{L_b}\sum_{h=b+1}^{H-1}
W_1\bigl(\widetilde P^{\pi}_{b,w_0,h},\widetilde P^{\pi}_{b,w,h}\bigr).
\]

For **equally weighted, equal-size empirical samples** (`n=m=N`) at one horizon, exact empirical W1 is:

\[
\widehat W_{1,h}=\frac1N\sum_{i=1}^N
|a_{(i),h}-b_{(i),h}|,
\]

where `(i)` indicates sorting **within that horizon**, not pairing trajectories by identity. For unequal sample counts, compute exact empirical one-dimensional W1 via the empirical CDF formula or a tested library implementation, not an arbitrary fixed quantile grid.

**Interpretation:** mean difference in marginal forecast distributions. It intentionally ignores inter-horizon dependencies. Also preserve the horizon-wise vector `\widehat W_{1,h}` to study divergence, amplification and reconvergence; don't only save the average.

The historical mean absolute difference over nine quantiles is a **coarse quantile-grid summary**, not exact W1, and cannot be converted to exact W1 from nine points alone.

### 4.2 Distance B: full-path Energy Distance, `ED_post`

Define a norm on equal-length suffix trajectories:

\[
\rho_{L}(u,v)=\sqrt{\frac1L\sum_{j=1}^{L}(u_j-v_j)^2}
=\frac{\|u-v\|_2}{\sqrt L}.
\]

The `1/sqrt(L)` factor expresses RMS separation per future timestep. It reduces the mechanical effect of comparing different suffix lengths, but does **not** make effects at different branching positions fully comparable; their conditioning and forecast-horizon populations still differ.

For independent `U,U' ~ P` and `V,V' ~ Q`, define the Energy Distance **functional** using this norm:

\[
\mathcal E_{L}(P,Q)=
2\mathbb E\rho_L(U,V)
-\mathbb E\rho_L(U,U')
-\mathbb E\rho_L(V,V').
\]

With Euclidean `rho_L` and finite first moments, this quantity is nonnegative at the population level and zero exactly when the two joint trajectory laws are equal.

Use the **biased V-statistic plug-in estimator by default** for a stable, nonnegative empirical measure:

\[
\widehat{\mathcal E}_{V}=
\frac{2}{nm}\sum_{i=1}^{n}\sum_{j=1}^{m}\rho_L(a_i,b_j)
-\frac1{n^2}\sum_{i,j=1}^{n}\rho_L(a_i,a_j)
-\frac1{m^2}\sum_{i,j=1}^{m}\rho_L(b_i,b_j).
\]

The V-statistic can be **positive even for independent samples from the same distribution**. Do not subtract an estimated bias ad hoc and call the result a metric. If an unbiased U-statistic estimator is later needed, implement it as a separately named quantity; it may be negative in finite samples. Do not conflate the functional with its square root or the different finite-sample estimators.

**Interpretation:** distributional difference over complete suffix trajectories, sensitive to inter-horizon dependence as well as marginal changes. A large `ED_post` **does not by itself prove that dependence changed**. Any claim about changes in dependence alone would require additional controls or examples with matched marginals.

**Computational cost:** for `N` paths of length `L`, calculating ED uses `O(N^2 L)` pairwise operations; W1 uses approximately `O(L N log N)` for equal sample counts. For planned sample counts this is small compared with neural inference. Benchmark and report actual overhead instead of claiming a measured speedup.

### 4.3 Normalize carefully, never silently

Let `s_X = IQR(X)` be the historical-context IQR on the same numeric scale as forecast values. Report:

\[
D_{\mathrm{W1,scaled}}^{\mathrm{post}} = D_{\mathrm{W1}}^{\mathrm{post}}/s_X,
\qquad
\mathcal E_{\mathrm{scaled}}^{\mathrm{post}}=\mathcal E_L/s_X,
\qquad
J_{\mathrm{scaled}}=J/s_X.
\]

Always retain **raw** distances. If `s_X` is zero, effectively zero or invalid under an explicitly fixed tolerance, mark the normalized values **undefined** and flag the context. Do not quietly replace the denominator with future ground truth, alternative samples, a window maximum, or a different scale. A documented context-only fallback may be considered **only with explicit approval**.

A common scale factor helps comparison across units but can also drive spurious correlations and outliers when near zero. Perform a small normalization sensitivity analysis for key results; do not make an extensive normalization framework.

### 4.4 Finite-sample/null controls: compulsory

At selected contexts/positions, independently draw **two disjoint continuation ensembles with the same forced token**, `A0` and `A0'` (and optionally repeated seeds/candidates). Compute `W1(A0,A0')` and `ED(A0,A0')` exactly as for an alternative.

These values empirically characterize the **finite-sample null noise floor** for each metric under the same sampling policy and sample size. They are not automatically universal significance thresholds. For an alternative, compare its effect and variability with appropriate same-token controls and repeated realizations; report null distributions/intervals where possible.

Important distinctions:

- Comparing a saved ensemble with **itself** produces zeros and is **not** a valid independent null control.
- Both empirical W1 and V-statistic ED generally exceed zero under independent equal-law samples.
- Sharing one reference ensemble among many alternatives produces dependence; record this design and account for it in analysis.
- Increasing the number of sampled continuations reduces estimation noise but does not create independent original series or windows.

### 4.5 Fixed-horizon robustness

Because `L_b=H-b-1` changes with `b`, record `b` and `L_b` on every measurement. Primary strict-suffix distances use all available post-fork horizons.

For comparisons across different `b`, **consider** a predeclared common downstream length `L_* <= min_b L_b` on a relevant subset, using exactly the first `L_*` post-fork horizons. Only run this sensitivity analysis if cross-position comparisons are central to a finding; do not build an elaborate multi-horizon metric suite.

### 4.6 Follow-up propagation descriptors (small set, not an alternative composite)

From the horizon-wise `W1_h`, optionally report:

- Early/middle/late mean W1 over explicitly defined post-fork segments.
- End-of-suffix or fixed-lag W1 (define lag/length before analysis).
- Peak W1 and its lag from the fork, with an explicit ties rule.
- Direct jump `J` alongside these W1 summaries, not mixed into them.
- Reconvergence examples, based on a documented downward W1 profile and the same-token noise scale.

Do not build a new weighted FPA index. The old composite stays **legacy-only**.

---

## 5. Probabilities, plausibility and statistical design

### 5.1 Candidate selection is not probability-weighted averaging

For each fixed context and fork position, candidate selection should record:

- Greedy reference token and alternative token IDs and decoded values.
- Candidate rank and `p_sel(w | c_b)` under the **actual documented selection distribution**.
- `p_sel(w_0 | c_b)`, entropy of that selection distribution, and probability mass covered by considered candidates.
- Actual sampling-policy configuration for the suffix (`temperature`, `top_k`, token masks, other decoding flags).

The existing candidate top-k and probability thresholds (`none`, `0.1%`, `1%`, `5%`) may be retained as **analysis subsets**, with their retained point/series/window coverage reported. They do not require multiple generations if candidate outputs are saved from an unfiltered scan.

**Do not interpret equal-weighted alternative averages as probabilities of events in normal generation.** A probability-weighted population expectation requires accounting for the probability mass of untested tokens; candidate truncation changes the estimand.

Paper 1 will focus on **individual forced-token forks** and descriptive group summaries. A general point-level weighted score is not required now.

### 5.2 Confounders and experimental units

At a minimum, evaluate key relationships with:

- `J/s_X` and raw `J`: decoded forced-token magnitude.
- Candidate probability / surprisal and local entropy (with the proper level of aggregation).
- Fork position `b`, remaining horizon `L_b`, and decoding configuration.
- Dataset and **original series** identity, plus window origin/time.
- Repeated alternatives sharing a reference conditional ensemble.

The unit used for inference must respect nesting: alternative within fork point within overlapping window within original series, and possibly correlated series within domain. Avoid branch-row IID confidence intervals.

The historical scan has only **15 series across 3 datasets**. It supports exploratory patterns but weak domain-level generalization. Prefer additional original series to many redundant shifts of the same series for confirmation. Use cautious cluster/bootstrap or hierarchical methods appropriate to the actual number of clusters, and disclose wide uncertainty rather than forcing significance.

Avoid presenting a null entropy correlation as evidence of independence or proof that FPA measures a new type of uncertainty. In the general case, for a future event `E`, `I(Z_b; E | c_b) <= H(Z_b | c_b)`, but this does not imply strong correlation between token entropy and branch-level distances. We do **not** need to estimate mutual information in Paper 1.

### 5.3 Forecasting quality is not the target

A generative divergence is not a prediction error, calibrated confidence interval, or evidence of successful adversarial manipulation. Use forecasting metrics only to provide context if they affect a claim. The data exports in the audit were reportedly from a training split, so do not assert zero-shot evaluation, unseen training membership, or general predictive performance without evidence.

---

## 6. Morphological interpretation: required, descriptive, and traceable

**Scientific purpose:** Give FPA temporal interpretability analogous in spirit to the semantic outcome examples in Bigelow. The goal is to explain **what changes in the forecast continuations** after a plausible token decision, not to identify all sensitive motifs in a dataset.

### 6.1 Two objects that must not be confused

1. **Source context or reference shape:** what the historical or generated reference looks like near `b`. Labels assigned from the **completed greedy reference** are retrospective and not available for prospective selection at `b`.
2. **Downstream changed morphology:** how the sampled reference and alternative future continuations differ after `b`. This is the primary object for Paper 1.

Do not infer that "plateaus are intrinsically more sensitive" from a few examples of plateau-to-trend transformations. That would require base-rate denominators and controlled, representative comparisons across all eligible positions.

### 6.2 Candidate descriptive transformations

Search among **validated or well-characterized** forks for:

- Plateau-like continuation to sustained upward/downward trend.
- Trend reversal or a clear change of endpoint direction.
- A peak or trough appearing, disappearing or shifting in time.
- Changes in peak prominence, not merely raw height due to different scales.
- Divergence that amplifies after the forced token versus divergence that decreases or reconverges.
- Large marginal shift with little qualitative shape change; small marginal shift with an apparently meaningful change in temporal arrangement, if actually supported.
- A near-null/control fork where the alternative does **not** alter qualitative behavior.

These are **hypotheses for illustrations**, not phenomena assumed to exist.

### 6.3 Small numerical descriptors, not a new algorithm

When useful for a specific figure, use a few transparent descriptors calculated **per sampled trajectory** or per clearly labeled ensemble summary:

- Direction or slope on a declared physical time grid, with units such as `target units / hour` or `IQR(X) / horizon-step`.
- Plateau-like variability relative to context scale, with a predeclared tolerance.
- Local peaks/troughs with declared prominence and minimum separation; define treatment of flat extrema and ties.
- Peak/trough timing, with censoring/undefined labels when no unique event exists.
- Endpoint direction, trend reversal, or selected threshold crossing, only when the event definition is meaningful and fixed.

A plotted angle ("45 degrees" or "60 degrees") is **not invariant to axis aspect ratio** and is not an acceptable scientific slope measure.

If a claim is about a morphological event probability, compute `k/N` on **individual sampled trajectories** and show finite-sample uncertainty; do not infer it from a median or a quantile-band crossing. Trajectory-level event labels are optional and should be implemented only for selected illustrated events, not a general taxonomy.

### 6.4 Selection and figure discipline

Build a candidate shortlist with explicit inclusion rules:

- Strong, medium and near-null effects according to a declared metric.
- Plausible alternatives and possibly one clearly labeled low-probability stress test.
- Representation across multiple series, where available.
- At least one counterexample where a compelling visual intuition fails under ensemble inspection.

Record the candidate pool size, ranking/selection rule, all inspected cases where feasible, and exact series/window/fork/token/seed identifiers. Do not repeatedly search until a visually striking story appears and then present it as typical.

For each final example show or document:

1. Historical context and fixed reference prefix, without mixing observed history with generated forecast values.
2. Forced position and decoded reference/alternative values, candidate probability and direct jump.
3. Sampled **reference and alternative continuation ensembles**, with clear distinction between an individual path, median and quantile bands.
4. The marginal W1-by-horizon curve and trajectory-level ED, with units and raw/normalized values.
5. The relevant same-token noise check and number of samples.
6. A concise claim supported by the ensemble, plus uncertainty and competing explanations.

**Do not claim** the full time-series process becomes a mountain or a plateau because one token changed; state precisely how the **conditional generated future distribution** changes.

### 6.5 Morphology is not a separate algorithmic contribution

The first paper's morphology section should be a small **interpretive result set and figure gallery**, not a morphological inference framework. We do not require statistics proving that peaks are more sensitive than plateaus. This could become a *later* question if the descriptive analysis reveals a systematic association worth testing.

---

## 7. Execution phases: start with Phase 1

### Phase 1: Minimal additive implementation and mathematical tests (START HERE)

**Purpose:** Obtain correct, reusable raw trajectory data and both distances without disrupting historical code.

**Authorized scope:** implementation, focused unit tests, serialization round-trip, and an extremely small smoke run if a model is already locally available. **Not authorized:** a broad new inference campaign.

**Required:**

1. Verify only relevant audit facts at the exact code points to be edited: how the forced token is included, what arrays exist in memory, how suffix sampling works, whether raw trajectories are already stored, and which decoder settings are used. **Do not repeat the full audit.**
2. Implement exact empirical marginal W1 and trajectory-level ED using the formulas in Section 4, plus raw/context-normalized outputs and the horizon-level W1 vector.
3. Keep direct jump, strictly post-fork and (if cheap) total-effect quantities clearly distinguished. Do not overwrite legacy score columns, shapes, names, or definitions.
4. Implement a small same-token/two-independent-ensemble control, with explicitly managed RNG state/seeds. Do not compare the same samples to themselves and call it a null test.
5. Add an opt-in output format for raw **individual numeric sampled trajectories** (for example compressed NumPy arrays or Parquet with shape metadata) and a manifest. Save reference ensembles once per fork point where sensible, link candidate ensembles with stable IDs, and preserve repeated-seed information.
6. Add narrowly scoped deterministic tests (see below) and a smoke check that does not require downloading or retraining any model. If no checkpoint is available locally, skip model inference and report the limitation.

**Minimum metadata:** dataset/series ID, source window origin, context length/scale, context hash or reproducible pointer, horizon, fork `b`, forced tokens and their numeric values, `p_sel`, candidate rank, model ID and revision/hash if obtainable, tokenizer config, decoder config, sample count, RNG seeds/state identifiers, software/git commit, paths/shape/dtype of saved arrays, and flags for invalid scales.

**Tests with known answers:**

- Equal-size 1D empirical distributions shifted by a constant `c` have W1 `|c|`.
- Identical saved trajectory sets have V-statistic ED zero up to numerical tolerance; two independent sets from the same law need **not** be zero.
- Two empirical 2D path ensembles with **identical marginals but different pairings** have average marginal W1 zero but trajectory ED positive (e.g. correlated versus anticorrelated two-point paths).
- Deterministic path distributions at different fixed vectors have Energy functional `2 rho_L(a,b)`.
- Fork `b=H-1` records a direct effect but no strict downstream metric; different `b` values produce correct suffix slices.
- Raw/scaled outputs have correct units and invalid-IQR handling; legacy outputs remain byte/definition-compatible where practical.
- Saved/reloaded arrays reproduce the same W1 and ED.

**Deliverable:** small code diff, tests with outputs, documented array/manifest schema, a compatibility check, and proposed bounded pilot design. Stop before Phase 2 until approved.

### Phase 2: Bounded pilot and early morphology (approval required for inference budget)

**Purpose:** Select sample counts and test whether the new distances are reliable enough to study the main findings.

**Before running:** Propose a stratified limited design: series, windows, positions, candidate probabilities, decoded jumps, number of continuations (e.g. small comparison of N=20/50/100), seeds, expected cost/storage and available compute. **Await approval for substantial inference.**

**After approval:**

1. Generate and save reference/alternative ensembles under the same decoding policy; compute both distances and same-token null controls.
2. Test sensitivity to `N`, direct shock, token likelihood, position/length, and scale. Prefer cheap controls that can falsify historical claims.
3. Show how existing findings change when the legacy composite is replaced by W1 and ED; distinguish complete loss of effect from an estimand change.
4. Begin a shortlist of 4-8 candidate morphology/counterexample cases, inspecting the ensembles, not isolated hand-picked paths.
5. Recommend the **minimum** confirmatory design, without launching it.

**Deliverable:** pilot report, null noise curves, metric comparison, ranked surviving/non-surviving candidate findings, morphology shortlist, proposed confirmatory budget. Stop for review.

### Phase 3: Confirmatory study (approval required for inference budget)

**Purpose:** Verify a small number of high-value, predeclared claims on additional independent series and/or nonoverlapping windows.

1. Freeze estimands, outcome definitions, candidate criteria, sample counts and testable hypotheses before seeing confirmatory results.
2. Prioritize new original series over many overlapping windows; record nested dependence; use appropriate clustering or hierarchy-aware uncertainty intervals.
3. Test direct shock versus downstream effects, local entropy/likelihood associations **conditional on jump magnitude and series**, and when supported, the difference between marginal and full-path descriptions. Report negative and heterogenous results.
4. Use both distance metrics on identical saved ensembles. Preserve all individual paths for later morphology figures.
5. Consider a second Chronos checkpoint only when justified by the pilot, available compute and desired venue; it is not automatic.

**Deliverable:** confirmatory evidence table with effect sizes, intervals, limitations, data provenance and exactly which claims survive. Stop for scientific review.

### Phase 4: Morphological interpretation and figures (no new inference by default)

**Purpose:** Complete a transparent, descriptive atlas of the transformations demonstrated by validated forks.

1. Search only saved trajectory ensembles, selecting representative positive, medium, null and counterexample forks under documented rules.
2. Apply minimal relevant descriptors (slopes, peaks, troughs, timing, plateaus, reconvergence) with clear units/thresholds/tie rules.
3. Produce a small set (e.g. 3-6) of reproducible ensemble figures with metadata and W1/ED context; document every claim as an ensemble property or a single-path illustration.
4. Check candidate narratives against per-path samples, not just aggregate medians, and record failures and negative examples.
5. Do **not** infer a general motif-by-dataset sensitivity law or build a topology model.

**Deliverable:** reproducible figure scripts and concise interpretation notes. If a particular selected case truly requires more samples, propose a narrow targeted rerun and await approval.

### Phase 5: Scientific synthesis, paper readiness and venue decision

**Purpose:** Choose the defensible results before writing a manuscript.

1. Distill the results into at most 2-3 **scientific findings**, not ten descriptive statistics.
2. For each finding: evidence, effect size, uncertainty, alternative explanation, potential novelty, limitation, and informative falsifier.
3. Check related work on Bigelow/conditional branching, probabilistic TSFM generation, distributional sensitivity and interpretable temporal shapes.
4. Decide if the morphology section is substantively informative or only illustrative, and state that honestly.
5. Judge publication potential against actual venue scope: a well-matched CORE/ICORE B target is **conditional**, A is an **ambitious possibility**, A* is not a justified expectation at present. Do not equate rank with acceptance likelihood.
6. Propose figures, sections, reproducibility appendix and strictly blocking final experiments. **Do not draft the manuscript without separate approval.**

**Deliverable:** ranked findings memo, scope/limitations, submission strategy and manuscript outline.

---

## 8. Stop rules and efficiency safeguards for Codex

1. Work **one phase only** per prompt. Do not execute later phases speculatively.
2. Phase 1 directly authorizes the minimum implementation and focused tests, not a large inference run.
3. Before editing, inspect the actual target files and make a **short file-by-file patch list**. If an audit assumption is wrong, explain and adjust the minimal design; do not do another broad audit.
4. Reuse current data structures and plotting/test conventions. Do not introduce a general-purpose package, new dependency or storage layer unless a real blocker justifies it.
5. Never modify, merge, clean, or overwrite legacy result directories as a side effect.
6. Avoid reprocessing the damaged July refinement. Prefer the clean September run for comparisons.
7. Keep both W1 and ED; do not combine them into an unexplained weighted score.
8. Preserve null controls and individual path saving. These are not optional embellishments.
9. Treat morphology as required **descriptive interpretation**, not a predictive event-classification feature.
10. Keep explicit `Verified / Inferred / Unverified / Proposed` labels in research reports.

## 9. References

- Bigelow et al. (2025), *Forking Paths in Neural Text Generation*, ICLR. https://arxiv.org/abs/2412.07961
- Ansari et al. (2024), *Chronos: Learning the Language of Time Series*. https://arxiv.org/abs/2403.07815
- SciPy documentation, `scipy.stats.wasserstein_distance`: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wasserstein_distance.html
- Szekely and Rizzo (2013), *Energy statistics: A class of statistics based on distances*, *Journal of Statistical Planning and Inference*. https://doi.org/10.1016/j.jspi.2013.03.018
- Codex's previously supplied audit, authoritative only to the extent supported by its inspected repository paths and historical artifacts.

