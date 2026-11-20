# Chronos FPA - Exploratory campaign protocol (candidate, NOT RUN)

**Observed update - 2026-11-20:** an opt-in single-context prototype now
implements and exercises the core H32/N20 operations; see the
[benchmark report](BENCHMARK_REPORT.md). This campaign remains unrun and its
multi-series grid unfrozen. The annotation below describes November19.
For this micro-validation, selection reserves greedy first, sorts remaining
q50 probabilities descending with ascending token-ID ties, and retains
existing kth-threshold support ties. This records an implementation convention,
not a population-design approval. The broader grid still needs review.

**Integration annotation - 2026-11-19:** this is a **suggested** candidate
design; anticipated scientific effects are **hypotheses**. Historical cells are
**observed (source reports/manifests)** only. The exact grid, residual mixture,
fixed22 export, CPD and optimized capture are not implemented/validated as a
campaign. Read the [implementation audit](FPA_IMPLEMENTATION_AUDIT.md) and
[pending choices](FPA_INTEGRATION_CONFLICTS.md). Existing kth-threshold sampling
retains ties; q50 can therefore have more than 50 support IDs. No tie/candidate
reservation or new normalization policy is chosen by this integration.

**Prepared:** 2026-11-19. **Not yet an inference authorization.** Source of decisions: multi-step user/ChatGPT scientific discussion, reconciled against Phase 2 / Phase 3 reports and Bigelow original. Codex must verify feasible implementation against the actual repository before declaring the grid executable.

## A. Mission and experiment unit

Collect a **reusable research atlas** permitting post hoc evaluation of FPA severity, probability/entropy, numeric perturbation, persistence, morphology, outcome drift/CPD, sparse-screening and white-box features. This is *exploration to design the final paper campaign*, not powered hypothesis confirmation.

Hierarchical units: dataset -> original series -> forecast-window origin/context -> fork position -> forced token/role -> independent continuation ensemble -> trajectory -> horizon. Statistical inference must preserve original-series clustering and trajectory-level dependence. Windows overlapping or drawn from the same series are not independent replicates.

## B. Frozen candidate numerical protocol (requires implementation audit)

| Dimension | Candidate value | Meaning |
|---|---|---|
| Model | `amazon/chronos-t5-mini`; pin revision `bd6a4fde8403b8469acd0abd52852b29dbe61c7b` | Verify real cache and hash |
| Context `C` | 512 observed numeric values | Do not halve the encoder context when reducing forecast horizon |
| Forecast horizon `H` | 32 decoded tokens/steps | Changed estimand vs Phase 2 H64 |
| Dense FPA positions `b` | `0..9` inclusive, **every selected window** | 10 consecutive decisions, min post-fork suffix 22 |
| Sampling `N` | 20 independent suffixes **per individual token group** | Exploratory, not N20 certainty |
| Candidate policy | Effective `q50` over valid value tokens, temperature 1, top-k 50, top-p 1 | Calculate exact selected mass according to actual implementation |
| Candidate selection | Smallest prefix of sorted-by-`q50` valid tokens covering >=0.90, capped at 8 **including greedy** | Coverage below 90% allowed when cap triggers; record exact residual mass |
| Residual | At most one separate conditional mixture `R` over **all remaining q50-support tokens** | N20 independent mixture paths when `r>0`; includes token identity of each sampled residual draw |
| Null control | N20 independent forced-greedy suffixes per fork position | Estimate MC noise; separate RNG stream |
| Independent reference | Greedy token included in eight, N20 | Shared reference within same position, separate from null |
| Historical probabilities | Save `p_sel` (untruncated valid softmax) and `q50` separately, plus q50 top-k support/tie behavior | Never equate them |
| Moving origins | Prefer separation of **at least 256 observations** between accepted windows within a series, subject to eligibility | Not a guarantee of independence |
| Panel construction | Two marked strata: representative/random-within-strata and diversity-seeking (without using future FPA outcomes) | Track inclusion design, do not report diverse-only prevalence |
| Datasets | ERCOT, Exchange Rate, M4 Daily; additional available series if QC approved | Seek independent series and heterogeneous dynamics |
| Budget | Extensible long campaign, can stop early or extend; **not yet assigned a run ceiling/approved** | Benchmarks determine allocation; checkpoints mandatory |

**Do not substitute alternative selection using p_sel (untruncated) into q50 mixtures.** User explicitly selected q50 for the 90% coverage and consistent sampling. Preserve both distributions for analysis.

### Indexing and conditional laws

For window `j`, context `X_j`, fixed greedy token sequence `g[0:H)`, fork position `b` and forced valid token `w`, define under effective policy `q50`:

`P[j,b,w] = Law(Y[b+1:H] | X_j, Z[0:b]=g[0:b], Z[b]=w; later tokens sampled via q50)`.

- **Strict downstream** outcomes for distances are `Y[b+1:H]`, not the forced coordinate `b`.
- Numeric shock `J[j,b,w] = decoded(w) - decoded(g[b])`, store signed J and |J| in raw and context-IQR units.
- For common-horizon comparison, use first **22** post-fork steps for b=0..9; retain all available steps for optional full-suffix measure. Do not compare W1 averages of different supports without declaration.
- Historical `s_X = IQR(X)` for normalization; report raw and normalized values, and an explicit fallback/exclusion policy for zero or tiny IQR, predeclared before inference.

### Distances, no new composite

For alternative ensemble A and reference B (each N per branch), marginal empirical `W1_h = mean(abs(sort(A[:,h])-sort(B[:,h])))` for equal N; `W1_fixed22 = mean_{h=1..22}(W1_h)`; `W1_full = mean_{h=1..H-b-1} W1_h`. If sample counts unequal, use the proper empirical-CDF formula, **not** naive index pairing.

`rho(u,v)=||u-v||_2/sqrt(L)`. Multivariate `ED = 2 mean_ij rho(A_i,B_j) - mean_ij rho(A_i,A_j) - mean_ij rho(B_i,B_j)`, a V-statistic (including within-sample diagonals), **no final square root**. Compute both on fixed22 and full suffix; divide raw distances by same context IQR when valid. ED is sensitive to marginals as well as dependence; do not equate ED-W1 difference to dependence alone.

Null independent-greedy control should use the same estimator and sample size. Preserve separate trajectory IDs and RNG states. Include permuted whole-trajectory labels for offline equal-law diagnostics, with exploratory multiple-test caveats.

## C. Bigelow-style CPD per window: 10 full + 5 light

Fix **one outcome representation for the whole window** and all prefix lengths (do not use variable-length suffix averages for this CPD). Preferred event family vs the window's frozen greedy path:

- Terminal event `E_last(delta) = 1{|Y[31] - greedy[31]| > delta*s_X}`.
- Last-eight event `E_last8(delta) = 1{mean_{h=24..31} |Y[h] - greedy[h]| > delta*s_X}`.
- Exploratory predeclared threshold grid: `delta in {0.05, 0.10, 0.25, 0.50, 1.00}`; plot event base rates/degenerate thresholds and interpret appropriately.
- Also retain continuous numeric outcome at Y31 / last-eight summaries to avoid dependence entirely on arbitrary thresholds.

Let `P_t` be the distribution of that **same outcome** after fixing first `t` greedy tokens, allowing the next token and remainder to follow q50. `P_0` is no prefix fixed, `P_t` is prefix length t.

At FPA positions `t=0..9`, estimate the global outcome distribution from **q50-weighted branch ensembles**:

`P_hat_t = sum_{w in T_t} q50_t(w) P_hat_{t,w} + r_t P_hat_{t,R}`,

where `r_t = 1-sum_{w in T_t} q50_t(w)`. The residual ensemble's first token is drawn from q50 **conditional on not in T_t**, then suffix sampled by q50. Never double-weight suffix samples by their likelihood: branch samples already represent conditional draws.

**Reuse:** the forced-greedy ensemble at `t=9` estimates the same theoretical law as `P_10` (provided identical q50 continuation policy): `P_{t,g_t}=P_{t+1}`. It has only N20 Monte Carlo draws. Store full path coordinates so the event is well-defined, not merely numeric post-fork samples without token history.

For prefix lengths `t=11..15`, estimate `P_t` using **N=60 direct independent q50 continuations from the greedy prefix of length t**. This yields **16 distributions `P_0..P_15`** for each window; observed transitions between prefixes are 15. This is an **early-prefix CPD study**, not CPD on all H32 decisions.

Analyze e.g. `d_t = D(P_0,P_t)` (Bigelow-style drift) and local increments `D(P_t,P_{t+1})`; note they answer different questions. For binary event distributions, specify Bernoulli distance (absolute event-probability difference or L2 over two-category histograms); do not use the old trajectory ED in place of an outcome-distribution metric. Compare across windows by position (0..15), regime and original series. Formal BEAST/PELT analysis is optional and exploratory with 16 noisy points; quantify stability and estimator uncertainty before interpreting change points.

**Boundary artifact guard:** weighted mixtures from N20 conditional ensembles for `P0..9`, N20 greedy reuse for `P10`, and N60 direct for `P11..15` have different variance. Predefine resampling/path-level uncertainty and a small direct-vs-mixture overlap calibration at several positions, **subject to measured cost/explicit approval**. Never bootstrap '60' samples resampled from 20 distinct conditional paths as if 60 independent model draws. Report variance and method-switch effects.

**Separate concept:** change-point detection on `h -> W1(P[b,w]^{(h)},P[b,g]^{(h)})` measures post-fork **forecast horizon** segmentation, not Bigelow's change points over **generation prefix position t**. This is an offline secondary analysis.

## D. Experimental sample construction

- Stratify by dataset, original series and coarse pre-FPA temporal characteristics: scale, trend, intermittency, volatility, autocorrelation, periodicity, regime-change proxies. Use only the input context; optionally use pre-fork logits if available at low cost, but document such selection.
- Representative stratum: predeclared eligible series/window sample with random selection *within* strata. Diversity stratum: maximize coverage of pre-FPA feature space, with caps to avoid selecting only anomalies/outliers.
- Prefer disjoint forecast horizons and >=256 context shift within each original series, unless a scientifically justified rare regime is intentionally oversampled and marked.
- Diversity panel informs mechanism discovery, not unweighted prevalence. For prevalence rely on representative stratum and report design/weights or strictly limited descriptive target population.
- Record rejected windows (short series, NaNs, low IQR, duplicate segments), all selection seeds, exact context hashes, data source/split and metadata; avoid claiming official zero-shot benchmarking on Chronos training-split exports.
- Window count / number of original series / dataset quotas **must be set after profiling**, not guessed from old single-thread CPU timings. Do not choose favorable high-FPA windows during experiment definition.

## E. All analyses fed by same primary data

1. Raw and normalized W1/ED, per-horizon profiles, equal-22 comparisons, null/permutation diagnostics, residual coverage and q50-/p_sel-probability relations.
2. Descriptive old metrics where mathematically defined: median shifts, width q10/q90, law shifts, shape correlations, amplitude ratios, threshold crossing, extrema timing, endpoint direction. Old composite scores are **legacy diagnostics only**, not main estimands.
3. Effects of |J|, signed J, likelihood, entropy, position, dataset, original series, scale and quantization; within-series controls; alternate reasonable baselines including simple numeric perturbation models.
4. Morphology in both conditional ensembles (not single cherry-picked paths). Candidate changes of level, local peak, end trend etc only when quantitatively supported.
5. Outcome drift and CPD curves per window; CPD-vs-FPA comparison on dense overlap t0..9, no false cross-window concatenation.
6. Simulate sparse position/token/sampling budgets by masking a dense dataset. Compare recall of consequential forks, estimation error and cost; account for N20 label noise, avoid leaking held-out fork data into selection, and validate on held-out original series.
7. Candidate white-box analysis: encoder and decoder hidden layers, before/after token states, encoder/decoder/cross-attention; compare predictive information to entropy/probability/J under grouped held-out evaluation. Attention correlations are not causal proof.

## F. Historical / confirmatory cells

- Previously completed Phase 2 H64/N50 group data can be reanalyzed offline with truncation to H32, fixed22 W1/ED and N20 finite-pool subsamples. This is **not fresh random replication**; verify autoregressive prefix consistency before claiming exact equivalence to new H32 runs.
- Stage A M4: `m4_daily/T000001`, window 0, b0, seed2718, **H64/N50**, four ensembles (greedy, down2187, up2189, same-token independent control) = 200 paths. Its original design remains a distinct prospective replication *cell*, not auto-approved. If run in the same campaign, tag it separately and apply its H64 measurements, not H32 definitions silently.
- Further H64 or second-model runs are conditional future proposals, not part of the default exploratory grid.

## G. Stop, extension and preliminary interpretation

The campaign can be paused, stopped or extended without corrupting completed groups. Specify a user-approved maximum elapsed wall-time or compute budget before actual execution. A manifest drives an immutable grid. Any post hoc additional window/series/seed/position becomes a new versioned grid with explicit selection rationale and analysis label (exploratory adaptive vs prespecified). Allow simultaneous analysis of committed groups if it does not substantially throttle inference; otherwise use time-sliced low-priority analysis. No automatic promotion of exploratory p-values to paper-level evidence.
