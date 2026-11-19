# Phase 2: Completed Controlled Pilot

Date: 2026-11-17. **The approved reduced pilot is complete: 7/7 groups.**
The original 14-group design was not completed: the user explicitly reduced
execution to seven groups for validation. Its other seven groups are deliberately
deferred, not failures. No Phase 3 or additional inference was launched to finish
this report.

Root: `result/phase2_controlled_pilot_20261116_195533/`.
Unless specified otherwise, result paths below are relative to this root.

## 1. Scientific Summary

1. **Verified:** independent same-token distances are substantial. Several
   alternatives are at or below that sampled control. Nonzero W1/ED is not
   sufficient evidence of a meaningful fork; N=20/50 comparisons and one seed
   repeat demonstrate material Monte Carlo sensitivity.
2. **Verified:** stronger conditional separation exists in selected plausible
   alternatives. Exchange Rate/currency_3 at b=16 has N=50 W1/control ratios
   3.89 and 3.27, and ED/control ratios 10.14 and 9.21. These are descriptive
   contrasts against one control, not significance tests or dataset-wide effects.
3. **Verified:** ERCOT's rank-3 early separation appears in both seeds, but its
   full-suffix ordering reverses. **Inferred:** temporal localization is a more
   promising candidate than a persistent large fork in this example.
4. **Verified:** pooled entropy correlations are negative, not weak or absent,
   in this small pilot. **Inferred:** series identity and relative numeric jump
   are major competing explanations. This does not establish either independence
   from model uncertainty or an intrinsic negative entropy/sensitivity relation.
5. **Verified:** ensemble inspection finds level/distribution changes and
   overlapping shapes, not a validated plateau-to-trend or peak-creation result.
   Negative and near-control examples are retained rather than relabeled.

This completes Phase 2 as an exploratory/workflow pilot, not the statistical
validation needed for Paper 1. Findings concern Chronos mini on these three
contexts, not a forecasting-quality or zero-shot benchmark.

## 2. Executed Design And Accounting

Scientific configuration: `config.json`; explicit amendment: `execution_plan.json`
(source: `configs/chronos_controlled_pilot/half_execution.json`). Selection and
source-context hashes: `selection.json`.

| Original series | Window/start | Fork positions b | Seeds actually run |
| --- | --- | --- | --- |
| ercot/EAST | 0 / 0 | 0 | 1729, 2718 |
| ercot/EAST | 0 / 0 | 16 | 1729 |
| exchange_rate/currency_3 | 0 / 0 | 0, 16 | 1729 |
| m4_daily/T000001 | 0 / 0 | 0, 16 | 1729 |

**Verified counts:** three original series, three historical windows, six
distinct fork points, seven point/seed groups, twelve distinct alternative forks,
fourteen alternative/seed observations. N=20 and N=50 give 28 analysis rows,
not 28 independent forks. Candidate top-k=3 includes the greedy reference:
two alternatives, one reference ensemble and one independent same-token ensemble
per group. Total: **1,400 sampled paths**, 78,600 saved suffix coordinates,
seven compressed NPZ archives totaling 78,497 bytes. Greedy construction also
costs computation and is not counted as a sampled stochastic path. Small
compressed size reflects repeated quantized values, not absent paths.

Reference and null arrays are each saved once per group and reused across its
two alternatives. Suffix shapes: [50,63] at b=0 and [50,47] at b=16.
`analysis_half/analysis_protocol.json` lists the seven deferred groups, including
both currency_5 rare-token stress groups and the five other seed-2718 ordinary
groups. `missing_approved_groups` is empty.

### Execution History And Timing Limitations

- The first group triggered the original four-hour projected-budget stop.
  `analysis/INITIAL_PHASE2_REPORT.md` and `analysis/` preserve that snapshot.
- The user then approved the seven-group subset with an eight-hour cumulative
  execution ceiling recorded in its amendment.
- Windows denied checkpoint publication after group 2 finished. Checksums, rows,
  identities, trajectory links and commit order validated; explicit recovery
  preserved it without regenerating samples. See `checkpoint_recovery_20261116.json`.
- A computer shutdown interrupted Exchange Rate b=0 before commit. Three
  committed groups survived; the unfinished group had to restart.
- Inference finished 7/7; only postprocessing failed because pandas' Spearman
  path imported missing SciPy. Pearson on average ranks now replaces that path,
  as elsewhere in this repository. No generation was repeated to finish analysis.

`progress.json` reports about 21,361 seconds (5.93 hours) of recorded execution.
This is **not total computational cost**: progress is written at group boundaries,
so work lost during abrupt shutdown is absent from the last saved elapsed value.
One recovered group's duration is also absent from the per-group timing list,
although its work entered the exception-time elapsed record. Downtime, restart
overhead and lost work prevent a clean hardware benchmark or strict retrospective
total-budget claim.

## 3. Protocol And Exact Estimands

**Verified:** cached `amazon/chronos-t5-mini`, revision
`bd6a4fde8403b8469acd0abd52852b29dbe61c7b`; CPU float32; one intra-op and
one inter-op Torch thread. C=512, H=64. Local training-split exports from
`autogluon/chronos_datasets`, under `data/raw/chronos_benchmark/`.

All branches share the greedy prefix before b. Force the greedy reference token
or an alternative, then sample N=50 suffixes using temperature=1, top-k=50,
top-p=1 and valid-token masking. `p_sel` is the untruncated valid-token softmax,
not the top-50-renormalized sampling policy. Separate per-token/role RNG streams
are recorded; the null forces the reference token but samples independently.

For decoded suffix arrays A,B at b+1,...,H-1, L=H-b-1:

```text
W1_h = mean_i |sort(A[:,h])_i - sort(B[:,h])_i|
W1_post = mean_h W1_h
rho(u,v) = ||u-v||_2 / sqrt(L)
ED_post = 2 mean_ij rho(A_i,B_j)
          - mean_ij rho(A_i,A_j) - mean_ij rho(B_i,B_j)
J = |decoded alternative at b - decoded reference at b|
s_X = q75(historical context) - q25(historical context)
normalized W1, ED, J = respective raw quantity / s_X
```

ED is the V-statistic including diagonal within-ensemble pairs, **without a
square root**. The forced coordinate is excluded from both downstream metrics.
Raw distances have series units; dividing by the same historical IQR makes
all three dimensionless. Null distances use exactly the same convention.
ED can reflect marginal and temporal-dependence changes, not dependence alone.

`*_over_null` compares against one sampled control, not an effect probability,
calibrated test or confidence interval. `*_excess_iqr` is a signed diagnostic
difference, not a debiased distance. No IID p-values are computed.

Sources: `code/chronos_fpa/metrics/chronos_distances.py`,
`code/chronos_fpa/core/chronos_decoding.py`,
`code/chronos_fpa/runtime/trajectory_export.py`, and
`scripts/viz/analyze_chronos_controlled_pilot.py`.

## 4. Effect Sizes And Sampling Noise

Source: `analysis_half/branch_effects.csv`, N=50. Distances divide by context IQR.
R denotes alternative/control ratio. Alternatives share their reference and null.

| Series | b | Seed | Rank | p_sel | J/IQR | W1 | W1 R | ED | ED R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EAST | 0 | 1729 | 2 | .125841 | .028803 | .070705 | .840 | .013708 | .947 |
| EAST | 0 | 1729 | 3 | .105169 | .057603 | .085261 | 1.013 | .019796 | 1.367 |
| EAST | 0 | 2718 | 2 | .125841 | .028803 | .100704 | 1.340 | .019134 | 1.425 |
| EAST | 0 | 2718 | 3 | .105169 | .057603 | .074536 | .992 | .013460 | 1.003 |
| EAST | 16 | 1729 | 2 | .175728 | .028799 | .066586 | 1.408 | .015903 | 1.912 |
| EAST | 16 | 1729 | 3 | .159246 | .028803 | .053191 | 1.124 | .008294 | .997 |
| currency_3 | 0 | 1729 | 2 | .108724 | .475277 | .325733 | 1.205 | .086917 | 1.818 |
| currency_3 | 0 | 1729 | 3 | .037296 | .475272 | .583880 | 2.160 | .227012 | 4.749 |
| currency_3 | 16 | 1729 | 2 | .070854 | .475277 | .669394 | 3.894 | .259340 | 10.141 |
| currency_3 | 16 | 1729 | 3 | .066802 | .475272 | .561403 | 3.266 | .235454 | 9.207 |
| T000001 | 0 | 1729 | 2 | .168208 | .204606 | .111845 | .972 | .016992 | .712 |
| T000001 | 0 | 1729 | 3 | .122837 | .204581 | .307863 | 2.675 | .119129 | 4.989 |
| T000001 | 16 | 1729 | 2 | .133069 | .204606 | .179084 | 1.643 | .047055 | 2.126 |
| T000001 | 16 | 1729 | 3 | .112977 | .204581 | .162803 | 1.494 | .041210 | 1.862 |

**Verified:** EAST b=0 rank-2/rank-3 ordering reverses between seeds for both
metrics. Rank 2 goes from below the full-suffix null to above; rank 3 goes from
slightly above to essentially equal. A single realization cannot reliably rank
these small effects. Positive null distances are expected for independent
ensembles; the reference self-distance is a different, zero-valued quantity.

### N=20 Versus N=50 Is Not Independent Replication

Sources: `analysis_half/nested_n_comparison.csv`, `analysis_half/branch_effects.csv`.
N=20 uses the first 20 saved paths, N=50 all 50.

**Verified:** ED is lower at N=50 in 13/14 paired alternative/seed comparisons.
This is consistent with sampling variation and V-statistic finite-sample
behavior; it does not prove population effects shrink with N or N=50 is adequate.

Example: currency_3 b16/rank2 W1/control changes .988 -> 3.894 and ED/control
.866 -> 10.141. Its null W1 drops .501036 -> .171899 and null ED
.269403 -> .025573. The large ratio change is not equivalent to tenfold growth
in the alternative effect. One control cannot estimate a stable null distribution.

### W1, ED And The Historical Composite

W1 and ED are separate estimands with different magnitudes. A different ratio
to control is not evidence that ED isolated temporal dependence. No controlled
matched-marginal empirical example is established by this pilot.

Actual historical-score columns are retained at N=50. For EAST b0/seed1729,
`legacy_context_iqr_scaled_token_bin_forking_score` ranks token 2229 above 2228
(.184216 versus .073699), while both distances rank them oppositely. This is
an estimand difference, not proof of a software defect. Do not substitute
`legacy_token_bin_forking_score_over_context_iqr`: dividing a completed heuristic
by IQR is not generally equivalent to normalizing inputs before a nonlinear
composite. Legacy values are absent on N=20 rows, where they were not recomputed.

## 5. Propagation, Numeric Jump And Position

### A Transient Profile Survives The One Available Seed Repeat

Source: `analysis_half/w1_profiles.csv`. Split: first ten downstream steps
versus the remainder. Chosen during initial inspection: **exploratory/post hoc**,
not a confirmatory endpoint.

| EAST b0, token2228 | Early W1/IQR | Early null | Later W1/IQR | Later null |
| --- | --- | --- | --- | --- |
| seed1729 | .131853 | .051900 | .076470 | .090219 |
| seed2718 | .092337 | .052534 | .071178 | .079416 |

**Verified:** both realizations separate more than their controls early and
less on average later. **Inferred:** a transient local effect is a defensible
candidate, not proven population reconvergence or persistent amplification.
Downstream distance exceeding J alone cannot establish amplification because
the independent null can also exceed J.

### Almost Equal Absolute Jumps Need Not Give Equal Effects

At M4 Daily b=0, rank 2 moves down 19.683105 original units and rank 3 moves up
19.680664: both approximately .2046 IQR. W1 is .111845 versus .307863;
ED .016992 versus .119129. The latter exceeds this sampled control; the former
does not. **Inferred:** absolute jump alone is not a sufficient description of
these empirical outcomes. Direction, probability and sampling are not isolated
by this two-token comparison; no conditional probability effect is established.

### Position Does Not Have A Universal Direction

The `*_first47_iqr` columns compare the first 47 downstream steps at both b
values. For currency_3/rank2, W1 rises .330045 -> .669394 from b0 to b16;
ED .103697 -> .259340. T000001/rank3 instead falls from
.314986/.138011 to .162803/.041210.
**Verified:** the contrast is not solely the mechanical 63-versus-47 length.
Conditioning prefixes and future regions still differ. One seed/window per
series does not identify a general position effect.

## 6. Entropy, Likelihood And Scale

### The Pooled Pattern Is Not An Entropy Finding After Controls

Source: `analysis_half/descriptive_correlations.csv`, N=50/main. Fourteen rows,
twelve unique alternatives, only six fork points and three original series.
Entropy repeats across alternatives/seeds; no IID significance is reported.
The tables below describe association, not predictive calibration or independence.

| Predictor | Pearson W1/IQR | Spearman W1/IQR | Pearson ED/IQR | Spearman ED/IQR |
| --- | --- | --- | --- | --- |
| Raw token entropy | -.737704 | -.849281 | -.690525 | -.822462 |
| p_sel | -.804383 | -.662997 | -.804347 | -.640971 |
| J/IQR | .915935 | .914585 | .871069 | .812471 |

Normalized entropy gives the same coefficients here. Its historical denominator
is log(number of positive floating-point probabilities), not necessarily fixed
vocabulary size; raw entropy is retained too.

Within-series entropy Spearman is +.828/+.414 (EAST), -.447/-.894 (currency_3)
and 0/0 (T000001), for W1/ED. **Each series has only two entropy values**, one
per position. ERCOT's seed repeat also makes pooled weighting uneven. These
are descriptive contrasts, not sufficient within-series evidence for a law.
Restrict to seed1729 and average the two alternative distances at each point:
six point summaries give Spearman -.885714 for both metrics. Removing duplicated
entropy rows does not remove the cross-series ordering or resolve confounding.

**Inferred:** series and jump-size controls are essential. Minimum tested jumps
are approximately .0288 IQR (EAST), .2046 (T000001), .4753 (currency_3).
Adjacent tokens represent different shocks relative to historical variation.
Entropy is simultaneously highest in EAST (2.26-2.77 nats) and lowest in
currency_3 (.518-.529). With two positions per series and almost fixed adjacent-bin
jumps within a series, an entropy effect conditional on jump is **not identified**.

Neither weak correlation in historical runs nor negative correlation here proves
that FPA measures independent uncertainty. The historical intuition is being
reassessed with different estimands, controls and a much smaller population,
not reproduced on an equivalent sample.

### Small Context-Only Normalization Sensitivity Check

Primary analysis remains IQR everywhere. Offline diagnostic: divide the same
raw W1, ED and J by each historical scale consistently for **all** observations.
Saved float32 contexts are promoted to float64; standard deviation uses ddof=0;
range is max-minus-min. No future values enter denominators. Seed1729, twelve rows:

| Scale | Entropy/W1 Spearman | Entropy/ED Spearman | J/W1 Spearman | J/ED Spearman |
| --- | --- | --- | --- | --- |
| context IQR | -.890509 | -.862239 | .910088 | .832484 |
| context std | -.862239 | -.862239 | .867759 | .832484 |
| context range | -.862239 | -.890509 | .867759 | .857176 |

Exact scales (IQR/std/range): EAST 310.157501/223.784157/994.079956;
currency_3 .013333008/.011740829/.063582003;
T000001 96.199951/60.197339/254.299805.

**Verified:** the pooled ordering survives these three context-only scales.
Raw unnormalized cross-series entropy correlations have the opposite sign
(W1 +.805699, ED +.706753), but raw units differ across domains, so that pooled
comparison has no common physical-unit interpretation. This neither proves one
normalization intrinsically correct nor identifies an IQR bug. All IQRs exceed
1e-12; no fallback was used. Within each series, b0/b16 share the same context,
so a common positive denominator cannot change a within-series rank correlation.

### Probability Filters And Candidate Coverage

Sources: `analysis_half/probability_coverage.csv`, `analysis_half/fork_points.csv`.
Thresholds 0, .001 and .01 retain all twelve alternatives/fourteen seed rows.
At .05 only currency_3 b0/token2182 (p=.037296) is removed: eleven alternatives,
thirteen rows remain. The strongest b16 effects (p=.070854, .066802) remain.

Candidate mass **including reference**: EAST .366/.517 at b0/b16;
currency_3 .996/.997; T000001 .983/.993. Candidate coverage therefore differs
greatly at the same top-k. `alternative_mass_total` summed across points is a
mass-sum, not one probability, and may exceed one.

**Not tested:** genuinely rare forced-token stress. No executed alternative
has p<.01; currency_5 was deferred. The pilot cannot validate the historical
claim that .001 filtering removes rare-token outliers. A likely forced token
also does not prevent rare suffix paths under the sampling policy.

## 7. Descriptive Morphology And Counterexamples

Pool: twelve distinct alternative forks; five chosen by deterministic role rules,
seven figures because two candidates have a seed repeat. No rare-token example
was generated. All seven figures were inspected alongside numeric ensembles.

Directory: `analysis_half/figures/morphology_candidates/`.
Exact selection rows/IDs: `analysis_half/morphology_candidates.csv`.
Figures show both ensembles (first 20 faint paths), all-50 pointwise median/q10-q90,
forced coordinate, W1/null profiles, ED and endpoint-change histograms.
Bands are marginal, not simultaneous intervals.

| Figure role | Exact fork | Observation and limit |
| --- | --- | --- |
| `strong_main_ED_seed_1729.png` | currency_3 w0 b16 token2184 | Shifted reference/alternative levels and W1 profile; overlapping distributions. Endpoint-positive 27/50 versus29/50 does not demonstrate trend reversal. |
| `near_control_main_seed_1729.png` | T000001 w0 b0 token2187 | W1/control .972, ED/control .712; broad overlap; endpoint-positive29/50 in both. Negative example, not proof of equal laws. |
| `middle_main_ED_seed_1729.png` | T000001 w0 b16 token2187 | Later marginal separation despite overlap; endpoint-positive27/50 versus24/50 is not an established frequency change. |
| `W1_ED_rank_disagreement_seed_1729.png`, `_seed_2718.png` | EAST w0 b0 token2228 | Similar oscillatory shapes; early separation, later near-control behavior. Endpoint-positive0/50 in both ensembles/seeds. Role name is a selection label, not a proven dependence-change mechanism. |
| `effect_per_direct_jump_seed_1729.png`, `_seed_2718.png` | EAST w0 b0 token2229 | Overlapping shapes; full-suffix ratios change with seed. A large distance/J ratio alone is misleading without its null. |

The currency_3 b16/token2184 histogram exposes an extreme continuation:
sample index 32 (0-based) ends at .443550; endpoint change is -30.8908 IQR.
It is not among the first 20 faint paths. This does not imply the entire
alternative ensemble reverses direction.

An explicitly **post hoc leverage diagnostic**, not a correction, removes only
that path (alternative N=49 against unchanged reference N=50). Exact unequal-size
W1 changes .669394 -> .621206; ED .259340 -> .263220. The largest effect is
therefore not explained entirely by that path. Outcome-dependent deletion changes
the empirical distribution and must not replace the primary results. Stored
arrays remain untouched.

**Not established:** plateau-to-trend transitions, peak creation/removal,
statistically reliable peak-time changes, or population reconvergence.
Y[H-1]-Y[b+1] is an endpoint descriptor, not a trend/motif classifier. No event
probability claim or classifier is introduced, or inferred solely from a median.

## 8. Artifacts, Fixes And Verification

| Path | Purpose |
| --- | --- |
| `progress.json`, `analysis_status.json` | Both complete; inference and analysis completion tracked separately. |
| `seed_*/branch_groups/` | Six groups at seed1729 plus one at2718; checksums, rows and archive links validated. |
| `seed_*/trajectories/*/{manifest.json,ensembles.npz}` | Numeric suffixes, contexts, probabilities, RNGs and provenance. |
| `analysis_half/branch_effects.csv`, `w1_profiles.csv` | Fourteen N=50 observations plus fourteen nested N=20 rows and marginal profiles. |
| `analysis_half/seed_stability.csv`, `nested_n_comparison.csv` | One replicated point and paired nested-N diagnostics. |
| `analysis_half/descriptive_correlations.csv` | Pearson/Spearman, counts and undefined reasons; no IID significance. |
| `analysis_half/probability_coverage.csv`, `fork_points.csv` | Filtering, candidate mass and actual experimental-unit counts. |
| `analysis_half/figures/effect_vs_same_token_control.png` | Equality line is not a significance threshold. |
| `analysis_half/figures/nested_sample_comparison.png` | First20 against all50, not independent repeats. |
| `analysis_half/analysis_protocol.json` | Current source/config/plan hashes, conventions, missing/deferred groups. |
| `analysis_half/report_checks.json` | Exact offline normalization sensitivity, temporal segments, balanced point means and explicitly post hoc tail-path leverage check. Source CSV hashes included. |
| `analysis/INITIAL_PHASE2_REPORT.md`, `analysis/` | Initial one-group snapshot, not final coverage. |

Completion changes were narrow:

- `scripts/viz/analyze_chronos_controlled_pilot.py`: average-rank Spearman removes
  an undeclared SciPy dependency; log bounds follow positive observations instead
  of extending to 1e-6 unnecessarily. Nonpositive plotting pairs are disclosed.
  Protocol records the correlation convention and actual gallery size.
  **W1, ED, sampling and normalization formulas did not change.**
- `tests/chronos_fpa/unit/test_controlled_pilot_analysis.py`: known tied-rank
  answer 1/3 with SciPy import blocked; positive-data log bounds.
- This report and documentation links supersede the partial-status entry.

All seven groups/archives validate. Recomputed N=50 W1/ED agree with committed
values at rtol=1e-10, atol=1e-10. Full offline suite: **214 tests pass**, one
unrelated AnyIO/Pytest warning. Nine PNGs are nonempty; both overviews and all
seven gallery figures were inspected. Historical September summary SHA256
is unchanged: `04a41da4b55ed353986796c1378ede65abe4d269e20a520ea2f344c75c75021e`.
Full future logits are not archived and cannot be recreated from numeric paths.

Repeat analysis without inference from the project root:

```powershell
.\.venv\Scripts\python.exe scripts\viz\analyze_chronos_controlled_pilot.py result\phase2_controlled_pilot_20261116_195533
```

Pilot `--resume-from` also skips all seven groups and updates analysis status.
SciPy is not needed for this analyzer. Initial `analysis/` and historical runs
are not regenerated.

## 9. Ranked Candidates And Minimum Phase 3 Proposal

| Candidate claim | Pilot status | Missing control |
| --- | --- | --- |
| Positive empirical distance identifies a meaningful fork | **Not supported.** Null can match/exceed the alternative. | Repeated effect/null draws, not a universal ratio threshold. |
| Plausible alternatives yield larger downstream separation | **Descriptively supported** in currency_3 and M4 rank3/b0. | New original series and repeat seeds. |
| Absolute jump fully describes sensitivity | **Insufficient** for near-matched opposite-direction examples. | Direction, probability, context and sampling controls. |
| EAST rank3 has a localized rather than persistent effect | **Survives one point's two seeds descriptively.** | Fixed temporal endpoint and independent-series replication. |
| Entropy is weakly related/unrelated to the new distances | **Not supported pooled; conditional relation unresolved.** | Series, jump, direction, position and coverage controls. |
| W1/ED disagreement proves changed temporal dependence | **Not established.** | Matched-marginal evidence. |
| .001 filtering removes rare-token outliers | **Not tested.** | Approved rare-token stratum. |
| Forks create qualitative motif transformations | **Not established.** Modest level/transient descriptions survive. | Ensemble-level evidence, not a new classifier. |

**Proposed, not approved or launched:** focused confirmation, not a full scan
or automatic completion of deferred groups.

- Primary surviving question: does near-matched-magnitude signed token choice
  produce reproducible separation above sampling variability? Secondary
  descriptive question: early/later localization, fixed before new data.
- Small feasibility design: six **additional original series**, two per current
  dataset, one nonoverlapping eligible context/window each, b=0, two root seeds,
  N=50. Lock IDs using context/logit information, not new W1/ED. Prefer opposite
  adjacent-bin alternatives with approximately matched |J| and p_sel>=.01.
  Document ineligibility instead of silently widening the rule. Probability,
  signed J and covered mass remain covariates, not automatically matched factors.
- If all eligible: twelve point/seed groups, 2,400 sampled paths, 151,200 suffix
  coordinates. Both distances use the same arrays; independent same-token control
  per group; unchanged historical-IQR convention; raw quantities retained.
- **Proposed budget:** observed H=64 groups took approximately 44-76 minutes;
  twelve groups would cost about 9-15 hours, or **13-23 hours with a 1.5 margin**,
  plus setup. Not an optimized hardware benchmark. Suffix payload is about .58 MiB
  uncompressed float32, plus contexts, manifests, CSVs and figures.
- Respect original-series clusters and paired seeds/alternatives. Six new series
  are a feasibility floor, not a power calculation or domain-general sample.
  N=50 does not guarantee a stable noise floor; review repeated controls before
  fixing a confirmatory decision rule.
- This minimum tests a jump/direction contrast, **not** a general conditional
  entropy relationship. That requires several independently selected points per
  series and a separately priced protocol. A second model, stress stratum,
  classifier or architecture is not required by default.

**Stop:** Phase 2 is delivered. No Phase 3 or manuscript preparation has been
authorized by this completion request.
