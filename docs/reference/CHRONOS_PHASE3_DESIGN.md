# Phase 3: Offline Controls And Targeted Replication Proposal

Date: 2026-11-17. **Deliverable A only. No new Chronos inference authorized or run.**
Phase 1 and the approved seven-group Phase 2 pilot remain complete. This document
supersedes the tentative six-new-series proposal in the Phase 2 report, not its
experimental record. No Phase 3 experimental-results report or Phase 4 atlas is
claimed here.

## 1. Decision Summary

**Verified:** whole-path permutation and repeated-subset analyses strengthen two
specific candidates, not a general FPA uncertainty claim:

1. M4 Daily/T000001 b=0: nearly equal, opposite token jumps give different
   reference-relative distances. The contrast is comparatively stable inside the
   saved sample pool and deserves fresh RNG replication first.
2. ERCOT/EAST b=0/token2228: an early-versus-later contrast is more informative
   than its full-suffix mean. The temporal contrast is unusual under relabeling
   in both available seeds, but its interval/example were selected post hoc.
3. Exchange Rate/currency_3 b=16: both alternatives differ from the reference;
   their ordering is unstable. Large alternative/control ratios should not be
   confused with a stable directional asymmetry.

**Recommendation:** first approve one new M4 seed group, then review. A maximum
five-group staged design adds two new original series if separately authorized
or included explicitly in the approval. This is targeted replication/feasibility,
not a powered domain-general confirmation. Do not fund the much larger RQ3
extension merely to make the same campaign answer every question.

## 2. Sources, Scope And Mathematical Invariance

Active specifications and records:

- `docs/future works/FPA_CHRONOS_RESEARCH_PLAN (1).md`
- `docs/CHRONOS_PHASE1.md`, `docs/CHRONOS_PHASE2.md`
- **Only inference source:** `result/phase2_controlled_pilot_20261116_195533/`
- **Offline controls used below:** `result/phase3_offline_controls_20261117_175121/`

The last path is abbreviated **O/** below. It contains a new offline analysis,
not newly generated trajectories. Earlier development invocations are not the
source of the reported numbers. Original Phase 2 arrays, CSVs, configurations and
analyses were not modified. This is not a reanalysis of the historical September
or July experiments.

Unchanged: greedy shared prefix; reference token forced then sampled; alternative
forced then sampled; post-fork indices b+1,...,H-1; separate direct jump J;
exact marginal W1 averaged over horizons; Energy V-statistic with diagonal
within-sample pairs and rho(u,v)=||u-v||/sqrt(L), **no final square root**;
raw and context-IQR outputs; independent same-token control; same samples for
both distances. ED/W1 differences do not isolate temporal dependence.

No model is loaded by `scripts/viz/analyze_chronos_phase3_controls.py`.
Its cached numerical implementation is checked against the existing distance
functions and independent known-answer examples. For signed empirical weights u
on a pooled path set and RMS distance matrix D, ED equals -u.T D u. W1 is exact
empirical-CDF integration on each pooled sorted coordinate, not a new estimator.

## 3. Additional Offline Statistical Controls

### 3.1 Whole-Trajectory Randomization

For each of fourteen alternative/seed observations and seven independent
same-token controls, pool reference and other ensemble (50+50 complete paths),
then randomly reassign exactly 50 paths to each label. Each row's full vector
stays intact. **Timesteps are never permuted independently.**

Assumption: conditional on the fixed context/prefix, independent trajectories
are exchangeable under equality of the two conditional laws. A fixed greedy
prefix or arbitrary dependence within a trajectory does not invalidate this
assumption; dependence between sampled paths would. Generator streams are
separate per token/role in the source manifests.

Budget fixed before this analysis: B=999 random relabelings per test; independent
offline RNG streams derived from seed20261117 and group/role identity. Report
right-tail p=(1+#(T_perm>=T_observed))/(B+1), retaining floating-point ties.
The minimum reported p is .001, never zero. This is a randomization test against
equal conditional laws, not a test of forecasting accuracy or practical importance.
The plus-one rule follows [Phipson and Smyth (2010)](https://doi.org/10.2202/1544-6115.1585)
and the [independent permutation-test convention](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html).
No SciPy installation is required by our script.

Holm adjustment is applied to **28 alternative/seed/metric tests together**.
Shared references make their p-values dependent; Holm does not require their
independence when marginal p-values are valid. See the [R statistical reference](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/p.adjust.html).
The fourteen same-token tests are diagnostics, not discoveries. Separate
asymmetry and temporal families below do not provide a combined study-wide
error guarantee. Crucially, no multiplicity correction removes the historical
selection of these contexts or the post hoc questions: **all pilot p-values
remain exploratory**.

Source: **O/permutation_tests.csv**, **O/permutation_distributions.npz**.

| Fork, seed1729 unless stated | p W1 | p ED | Holm W1 / ED, family28 | Interpretation |
| --- | --- | --- | --- | --- |
| M4 T000001 b0/token2189 | .001 | .002 | .028 / .046 | Strongest M4 candidate, conditional on this selected point. |
| M4 T000001 b0/token2187 | .769 | .842 | 1 / 1 | Useful near-control alternative despite the nonzero distance. |
| currency_3 b0/token2182 | .003 | .003 | .066 / .066 | Suggestive, not below .05 after this adjustment. |
| currency_3 b0/token2184 | .192 | .089 | 1 / 1 | No clear separation at this N under these statistics. |
| currency_3 b16/token2184 | .001 | .001 | .028 / .028 | Distributional separation candidate. |
| currency_3 b16/token2182 | .001 | .001 | .028 / .028 | Distributional separation candidate. |
| EAST b0/token2228, seed1729 | .298 | .226 | 1 / 1 | Full-suffix mean does not isolate the localized effect. |
| EAST b0/token2228, seed2718 | .761 | .725 | 1 / 1 | Same limitation in the repeat. |

Other EAST/M4 b16 tests are also above .05. Six of28 alternative tests fall below
.05 after Holm; they are three alternative/seed observations measured twice,
not six independent replicated findings. Same-token p-values range .267-.960
(W1) and .393-.921 (ED); this small diagnostic set does not establish calibration.

Monte Carlo precision is limited: p=.001 means no more-extreme sample among999
draws, not a known exact tail probability of .001. The M4 ED adjusted value .046
is particularly close to a decision boundary. We did not extend permutations to
obtain a more favorable conclusion; independent replication matters more now.

### 3.2 Matched-Magnitude Directional Contrast

Five point/seed groups have opposite signed jumps whose absolute sizes match
within relative tolerance .001. For each, retain the same finite reference A
and compute delta_D=D(A,up)-D(A,down), separately for W1 and ED. Relabel **whole
paths between up and down only**, keeping A fixed. Use |delta_D| for the
two-sided tail; Holm over the ten resulting tests.

**Exact null:** equality of the up/down conditional trajectory laws. This is a
stronger hypothesis than equality of their population distances to the reference.
This randomization test is **not** a generally valid test of the weaker null
D(P_ref,P_up)=D(P_ref,P_down) when the alternative laws differ. Reference sampling
uncertainty is also conditioned on rather than integrated out. Fresh reference
and alternative ensembles in independent seeds are needed before interpreting
these empirical asymmetries as reproducible population effects.

Source: **O/directional_asymmetry.csv**.

| Point | delta W1/IQR | delta ED/IQR | p W1 / ED | Holm W1 / ED, family10 |
| --- | --- | --- | --- | --- |
| T000001 b0 | +.196018 | +.102137 | .001 / .001 | .010 / .010 |
| currency_3 b0 | -.258147 | -.140095 | .004 / .001 | .028 / .010 |
| currency_3 b16 | +.107991 | +.023886 | .068 / .056 | .280 / .280 |
| EAST b16 | +.013396 | +.007609 | .114 / .020 | .342 / .120 |
| T000001 b16 | -.016281 | -.005845 | .365 / .459 | .730 / .730 |

**Inferred:** the M4 contrast deserves priority; a universal claim that upward
jumps are stronger is contradicted by the sign pattern. Probability remains
different: M4 up/down p=.122837/.168208; currency_3 b0=.108724/.037296.
Equal |J| does not make direction, token identity and likelihood independent.

### 3.3 Targeted Temporal Contrast, Not A New Global Search

Only the existing EAST b0/token2228 example and its same-token controls were
tested. The statistic is first10-step mean W1 minus remaining53-step mean W1.
Its one-sided permutation tail asks whether separation is unusually concentrated
early **under equal-law exchangeability**, not whether the laws become equal
later. Both the example and interval were selected in Phase 2: post hoc.

Source: **O/temporal_localization.csv**. Holm family includes the two alternative
seed tests, not the same-token diagnostics.

| Seed | Early W1/IQR | Later W1/IQR | Contrast | p | Holm, family2 |
| --- | --- | --- | --- | --- | --- |
| 1729 | .131853 | .076470 | .055383 | .001 | .002 |
| 2718 | .092337 | .071178 | .021160 | .010 | .010 |

Same-token contrasts are -.038319 and -.026882, with p=.402/.456.
**Inferred:** localization survives a useful additional control at one fixed
point. It is not confirmed population reconvergence, nor a general property of
ERCOT. Full-suffix nonsignificance and localized separation are not contradictory:
the two statistics ask different questions. W1/J>1 is still not amplification.

### 3.4 Repeated Subsets: What N=50 Does And Does Not Support

For each group, draw100 independent subset selections without replacement for
N=20 and N=35 from the stored fifty paths per ensemble. Within each selection,
reuse the same reference subset and same-token subset across both alternatives;
alternative subsets are sampled separately. Pair alternative differences before
summarizing their ordering. N=50 is evaluated **once**, not artificially repeated.

The q05-q95 ranges are conditional finite-pool resampling ranges, **not confidence
intervals for population distances**. As subset size approaches50, variability
must shrink because the pool is finite. N=50's zero subset variability proves
nothing about independent generation variability. These draws cannot estimate
precision at N=100 or simulate a fresh seed.

Sources: **O/subsampling_draws.csv**, **O/subsampling_stability.csv**,
**O/subsampling_rank_stability.csv**.

| Point/seed | N20 agreement with full50 ranking: W1 / ED | N35 agreement: W1 / ED |
| --- | --- | --- |
| T000001 b0/1729 | .91 / .93 | .99 / .99 |
| T000001 b16/1729 | .48 / .48 | .64 / .66 |
| currency_3 b0/1729 | .80 / .84 | .94 / .94 |
| currency_3 b16/1729 | .60 / .57 | .72 / .63 |
| EAST b0/1729 | .61 / .59 | .66 / .76 |
| EAST b0/2718 | .64 / .54 | .86 / .75 |

Example: T000001 b0, down-minus-up N35 contrasts have q05-q95
[-.282259,-.065738] for W1 and [-.170809,-.042635] for ED. At N20 these
ranges cross zero. Currency_3 b16 remains poorly ordered even at N35.

**Recommendation:** retain N=50 with independent seed replication for the strong
M4 contrast, not N20 for speed. Do not declare50 generally sufficient. At roughly
equal neural cost, two N50 seeds give two new references and two controls, while
one N100 seed gives larger ensembles but no seed replication. They are not
statistically interchangeable. For weak effects neither allocation is guaranteed
adequate; do not fund a blind N100 grid using finite-pool ranges as a power study.

## 4. Ranked Research Questions

| Rank | Question | Proposed testable target | Not identified |
| --- | --- | --- | --- |
| 1: RQ1 | Is abs(J) sufficient to describe sensitivity? | Fresh samples reproduce selected near-equal-magnitude asymmetries; independently selected new series offer a feasibility extension. | Pure causal effect of direction, likelihood or token identity; domain-general magnitude law. |
| 2: RQ2 | Is separation localized or sustained? | Fixed first10/later53 profiles on new b0 data; optional fixed-support position extension. | Proof of equality later, universal reconvergence, sensitivity of a motif class. |
| 3: RQ3 | Does entropy add information after other controls? | Separately sampled within-series point variation, fixed b and direction, with jump/probability/coverage diagnostics. | A within-series relation from one point per series or a comprehensive conditional law from a few clusters. |

The Phase 2 pooled entropy correlations are not recomputed or treated as
independent branch observations here. The new tests give no basis for promoting
them to an uncertainty contribution.

## 5. Minimum Proposed Design: Five New Groups Maximum

### 5.1 Exact Cases And Stages

Unchanged model/revision: `amazon/chronos-t5-mini`,
`bd6a4fde8403b8469acd0abd52852b29dbe61c7b`; C512, H64, b0, N50;
temperature1, continuation top-k50, top-p1, current valid-token masking;
CPU float32, one model and one Torch thread. Save all numeric strict suffixes.

| Stage | Series | Window/start | b | New seeds | New groups |
| --- | --- | --- | --- | --- | --- |
| A | m4_daily/T000001 | 0 / 0 | 0 | 2718 | 1 |
| B1 | m4_daily/T000005 | 0 / 0 | 0 | 1729,2718 | 2 |
| B2 | exchange_rate/currency_6 | 0 / 0 | 0 | 1729,2718 | 2 |

Stage A directly repeats reference2188/down2187/up2189 with fresh streams; its
seed1729 ensembles already exist and must not be regenerated. The exact forced
values, p and context hash must match the Phase 2 archive before sampling.
It can refute a selected example, not serve as unselected evidence of prevalence.

Stage B adds **two original series not in Phase 2 or the clean September run**;
no claim that they were absent from every historical directory. The identities
are fixed using availability/order, not their new outcomes. T000005 has1020
observations; currency_6 has7588. Their first512 context values are finite, with
positive context IQR, and C+H fits. These checks used local data only, no model.

Source files are exactly
`data/raw/chronos_benchmark/autogluon_chronos_datasets__m4_daily__train.jsonl`
and `.../autogluon_chronos_datasets__exchange_rate__train.jsonl`.
**O/proposed_data_selection.json** records full source-file hashes, proposed
window identities and float32 context hashes from a data-only check. The three
core contexts have distinct hashes. Revalidate them at approval/execution;
do not use the stale path strings in the old export manifest to substitute data.

**Staged stopping:** approve A alone (one group) or explicitly approve all five.
Always pause after A for review, positive or negative. No automatic case
replacement, extra seed, N increase or Stage B extension follows the outcome.
For a five-group authorization, pause again after the two B1 groups. Hardware or
integrity failure stops with validated checkpoints rather than changing the design.

### 5.2 Prospective Candidate Eligibility For New Series

Before alternative generation, after approval only:

1. Encode the fixed context and obtain the greedy reference and valid-token
   logits at b0. This bounded greedy preflight is model inference too; none has
   been executed for these new cases.
2. The global top3 valid candidates must contain the reference and two tokens
   decoding to opposite signed jumps. Require adjacent numeric bins, nonzero J,
   and relative absolute-jump mismatch <=.001.
3. Both p_sel>=.01 and max(p_up,p_down)/min(p_up,p_down)<=2. Record exact ranks,
   p_sel, policy probabilities, signed/raw/IQR jumps, entropy, scale and covered
   candidate mass. The probability-ratio condition is a proposed design choice,
   not a validated theorem or a modification of suffix sampling.
4. If a new point fails, record **ineligible** and do not generate it or widen
   top-k/search more positions. Seek a revised approval if coverage is inadequate.
   Stage A's known pair passes the same .01/probability-ratio rules.

Top3 is candidate coverage, not the continuation top-k50. Forced token IDs and
eligibility of new cases are **unverified until approved preflight**; the design
and maximum compute are exact, while realized eligible counts may be smaller.
This intentionally studies a plausible, near-symmetric candidate subset, not
all possible tokens. No score-selected admissions or top15 campaign is proposed.

The current pilot runner does not implement these prospective admission checks.
After approval, the narrow gate must be tested before new sampling; existing
global top-k cannot silently stand in for a matched-pair rule. No such inference
or runner change is included in Deliverable A.

### 5.3 Accounting And What The Minimum Can Answer

Maximum **new** computation: five reference ensembles, ten alternative ensembles,
five independent same-token ensembles, each N50: **1,000 sampled trajectories**.
At b0, L63: 63,000 float32 suffix coordinates =252,000 bytes (~.240 MiB), plus
contexts, manifests, CSVs and figures. Small-array compression observed in Phase 2
is not a storage guarantee; reserve at least20 MiB for analysis/plots and metadata.

Including reused Phase 2 seed1729 at T000001: six point/seed groups from three
original series and three contexts, not six independent series. The two genuinely
new series each contribute one fork point with two seeds. RQ1 has a deliberately
small external feasibility check; RQ2 can characterize these b0 profiles; RQ3
within-series entropy is **not identifiable** from this design.

## 6. Statistical Protocol To Freeze Before New Sampling

### Primary Outcomes And Contrasts

- Separately report delta_W1 and delta_ED, up-minus-down, in raw units and common
  context IQR. Do not combine them. Pair alternatives by point and seed, sharing
  exactly the same reference. Also retain each alternative/reference and
  independent reference/null distance.
- Stage A's predeclared candidate is up>down in both distances, as observed in
  Phase 2. A reversal or unstable ordering in seed2718 is negative replication
  evidence; a positive result does not remove the original selection effect.
- Stage B tests for asymmetry without predeclaring a universal stronger direction.
  Report each point's signed deltas for both seeds; avoid absolute-value selection
  masquerading as a known directional prediction.

Whole-path alternative-label randomization with reference fixed is permitted
under equal alternative laws, with the limitation in section 3.2 stated. Use
9,999 offline permutations per final test for better resolution, not extra model
samples. All tests use the two-sided absolute delta; the Stage A sign prediction
is reported separately and does not change the tail after observing results.
Freeze one primary family of **ten new tests**: five new point/seed groups,
two distances each. Holm adjustment spans that family; ineligible planned tests
are retained as p=1 for the planned-family adjustment, not silently removed.
The reused Stage A seed1729 remains the exploratory origin outside the new-data
family, never counted as confirmation. Do not choose a more favorable family
after seeing the results. Holm handles p-value dependence but cannot validate a
scalar-distance null that does not imply exchangeability. The feasibility
interpretation does not depend on p<.05.

### Temporal Secondary Outcome

For new b0 data, predeclare early=relative lags1..10, later=11..63. Report both
mean W1 values, their difference, and the independently sampled same-token profile.
Keep these secondary/exploratory, or allocate a separate predeclared multiplicity
family if an inferential claim is later requested. A downward profile or later
nonsignificance is not evidence that population laws have become equal. No
amplification claim from W1/J alone. All main groups share L63, so remaining
horizon cannot explain a main-design contrast.

### Sampling And Scientific Uncertainty

- Seeds replicate Monte Carlo generation at the same fixed context, not series.
  Alternatives and seeds are paired measurements, never IID branch rows.
- Conditional permutation inference concerns sampled conditional laws for fixed
  inputs. It does not supply original-series population uncertainty.
- With only two new original series, do not publish a cluster-bootstrap CI or
  pooled regression as domain-general confirmation. Show all point/seed results
  and leave-one-series descriptions, without pretending they form a power study.
- New contexts do not overlap within a series in the minimum because there is
  only one. Financial series can nevertheless be dependent across currencies;
  different IDs are not automatically independent data-generating processes.
- Retain the finding as a **replicated example** only if independent seed results
  agree in direction for both distances and same-token/profile diagnostics do
  not make the interpretation implausible. Otherwise call it unstable or
  metric-specific, not a failure to be fixed by extra unplanned samples.
- Even stable same-sign deltas are not proof of a practically important population
  asymmetry: finite-N bias/noise may remain. No universal minimum-effect threshold
  is invented from these three contexts. Report effect sizes; a practical threshold
  needs an explicit scientific interpretation before a stronger claim is made.

## 7. Optional Extensions, Priced Separately

### Position/Propagation Extension For RQ2

If B1 is eligible, add b16 on the **same T000005 historical window**, seeds1729
and2718, N50, identical prospective candidate rules. Two additional groups,
400 paths, L47, 18,800 float32 coordinates (~.072 MiB). New candidate IDs and
entropy may differ; never treat a different token as the same intervention.

Compare first47 strict downstream lags at both positions, plus the full b0
profile. Fix first10 and remaining37 for that common-support comparison before
running it. Prefix and future regions still differ, so it is not a pure causal
effect of position. Expected additional inference: **1.1-1.9 hours**, about
**1.7-2.9 hours with1.5 margin**, plus setup. This is optional, not included in
the five-group ceiling. Testing another ERCOT series would be a different priced
extension, not a silent substitution if T000005 fails.

### Within-Series Entropy Extension For RQ3

An informative but still exploratory next level would hold b0 fixed and use
four nonoverlapping context+forecast blocks per series: starts
0,576,1152,1728, each C512/H64. Proposed source identities:
ERCOT/SOUTHERN and WEST, Exchange Rate/currency_6 and currency_7. The local files
contain these series with sufficient length (ERCOT154872, currencies7588).
No new logits or outcomes were inspected to select them.

Four series x four windows x two seeds = **32 groups**, 6,400 sampled paths,
403,200 coordinates (~1.54 MiB uncompressed numeric suffixes). If B2 completes,
its two currency_6/start0 groups can be reused: **30 new groups**, 6,000 paths.
New-only expected inference: **22-38 hours**, roughly **33-57 hours with1.5 margin**,
plus preflight/setup. Price assumes all points eligible, not a promise of enough
entropy/jump variation. No eligibility-based replacement or widening without approval.

Why not simply reuse M4 at the same origins? The current local M4 Daily export
has **no series of length>=2304**, and T000005 has only1020 points. Four such
disjoint blocks do not fit. Shorter contexts or overlapping windows would be
protocol changes requiring separate justification, not an automatic fallback.

For RQ3, first summarize entropy **once per point**, not once per token/seed.
At fixed direction, retain the vector of W1 and ED seed estimates, p_sel,
signed/raw/IQR jump, IQR and covered mass. Show pooled, within-dataset and
within-series patterns separately. Stratify by predeclared jump/probability
bands only if populated; do not fit a large conditional regression to16 points.
With four points per series, four clusters and only two related domains, this
still supports limited within-series exploration, not simultaneous identification
of all listed confounders. Nonoverlap reduces mechanical dependence but does
not make origins or regional loads/currencies independent. An entropy law across
datasets would need a broader separately powered design.

**Recommendation:** defer this extension. Its cost is not justified until RQ1
replication and prospective eligibility/variation checks show that these
covariates can actually be disentangled. No within-series entropy publication
claim is promised by the five-group minimum or this four-series extension.

## 8. Current Hardware, Costs And Checkpoints

Read-only hardware check on2026-11-17: Intel Core Ultra7 265U,12 physical/14
logical cores;15.46 GiB visible RAM and approximately2.10 GiB free at inspection;
Intel integrated graphics. Current PyTorch is `2.11.0+cpu`;
`cuda.is_available()` is false. No supported GPU execution path was established.
A different GPU could help, but neither speed nor bitwise comparability has been
verified; do not switch device/precision or decoding without explicit approval.

Measured Phase 2 b0/N50 groups took44.0,76.1 and65.6 minutes (EAST, currency_3,
T000001). Use **44-76 minutes per b0 group** as an empirical planning band,
not a confidence interval. The b16 groups took25-51 minutes; for new b16 groups
we budget conservatively33-57 minutes from the47/63 work ratio, with an extra
planning margin. This is the same unoptimized one-model/one-thread CPU workflow,
not a performance-optimization task.

| Proposed stage | New groups | Paths | Expected inference | With1.5 planning margin |
| --- | --- | --- | --- | --- |
| A only: selected M4 seed repeat | 1 | 200 | .73-1.27 h; M4 precedent1.09 h | 1.1-1.9 h |
| B: two new series, two seeds each | 4 | 800 | 2.9-5.1 h | 4.4-7.6 h |
| Maximum minimum-design total | 5 | 1,000 | **3.7-6.3 h** | **5.5-9.5 h** |
| Optional T000005 b16 | 2 | 400 | 1.1-1.9 h | 1.7-2.9 h |
| RQ3 extension, reusing B2 | 30 | 6,000 | 22-38 h | 33-57 h |

Proposed ceilings:2 hours for A alone;10 hours cumulative for the five-group
design, including setup/preflight/analysis. These are approval requests, not
automatic budget extensions. Runtime checking remains between complete groups;
an in-progress group can overrun a boundary. System sleep/update and other
workloads can invalidate estimates; one-thread setting does not prevent paging.

Reuse atomic group checkpoints and trajectory manifests; reconstruct CSV exports
from validated groups on resume. Freeze selected windows, candidates, policy,
seeds and configuration; reject incompatible changes. Save each completed group
before proceeding; reference reused within its group. **There is no durable
mid-generation resume:** interruption before the reference/alternatives/null
group commits may require regenerating that group. Do not promise branch-level
or timestep-level saves that the current runner does not implement.
The Phase 2 Windows retry/explicit pending-group recovery remains applicable.

Use a new Phase 3 output folder only after approval; never append new scientific
cases to the immutable Phase 2 config. Log session start/end and interrupted-work
estimates so a crash does not silently reset the accounting. Stage A may reuse
old numeric ensembles in analysis but must not duplicate/regenerate them.

## 9. Morphological Interpretation: Minimal Added Descriptors

No automatic morphology detector existed in Phase 2, and none is introduced here.
The bounded addition computes per-path descriptors on existing strict suffixes:

```text
endpoint_i = (y_i[L-1] - y_i[0]) / context_IQR
beta_i = sum_t (t-t_bar)*y_i[t] / sum_t (t-t_bar)^2
slope_i = beta_i / context_IQR                  [IQR per forecast step]
residual_rms_i = sqrt(mean_t (y_i[t]-y_i_bar-beta_i*(t-t_bar))^2) / IQR
```

These are fitted linear slope and variability around that line, not a sustained
trend or plateau definition. No angle, prominence threshold, peak classifier,
topological framework or new FPA score is used. The interval is the full strict
suffix and is recorded by b/H, so OLS across oscillatory ERCOT forecasts must
not be called their local trend.

Sources: **O/path_descriptor_values.csv** (individual paths),
**O/path_descriptors.csv** (summaries). For the already-used endpoint>0 event,
give counts/fractions and pointwise95% Wilson intervals conditional on the fixed
context; they are not a multi-case discovery procedure or a CI for a difference
between ensembles. Wilson is a standard [binomial proportion interval](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html).

| Existing example | New descriptor check | Decision |
| --- | --- | --- |
| T000001 b0, reference2188/down2187/up2189 | Endpoint-positive counts29/50,29/50,28/50; individual Wilson intervals approximately[.442,.706], [.442,.706], [.423,.688]. Median slopes .003870,.001252,.002568 IQR/step; their q10-q90 spans both signs. | Distance asymmetry without a demonstrated trend reversal. Retain as RQ1 candidate, not a plateau-to-trend story. |
| EAST b0/token2228, both seeds | Reference/alternative endpoint-positive counts0/50;95% upper limit about.07135 for each, not zero population probability. Oscillatory shapes remain; localized W1 supports the temporal description instead. | Retain for localization and a negative morphology transformation example. |
| currency_3 b16/token2184 | Positive endpoints27/50 vs29/50; slope distributions straddle zero. One extreme suffix path remains a selected-tail caveat in the Phase 2 report. | Level/distribution separation, not a whole-ensemble direction reversal. |
| T000001 b0/token2187 | Nonzero W1/ED but large permutation p and unchanged endpoint fraction. | Keep as near-null counterexample, not evidence of equality of laws. |

**Inferred:** these examples justify the three minimal descriptors, not a general
detector. They do not justify adding peak/prominence/timing machinery before a
specific ensemble-level claim requires it. Plateau-to-trend and peak-creation
narratives remain unsupported. Reuse Phase 2 ensemble figures; polished atlas
selection belongs to Phase 4 and has not started.

## 10. Reproducibility, Verification And Approval Boundary

Script: `scripts/viz/analyze_chronos_phase3_controls.py`.
Tests: `tests/chronos_fpa/unit/test_phase3_controls.py`.
No dependency installation, model download, inference or production-decoder
change was needed. Output protocol records exact input file hashes, analyzer
and distance-source hashes, software versions, RNG, counts and limitations.
The reported bounded statistics took approximately4.64 seconds after imports;
this has no bearing on neural inference time.

Offline command, which always creates a separate result directory:

```powershell
.\.venv\Scripts\python.exe scripts\viz\analyze_chronos_phase3_controls.py result\phase2_controlled_pilot_20261116_195533
```

Defaults are999 permutations and100 subset repeats, with explicit upper bounds;
there is no hidden full-grid search. Exact arrays of permutation statistics are
saved in `permutation_distributions.npz`. Full output is about 1.19 MiB.

| Artifact in O/ | Contents |
| --- | --- |
| `permutation_tests.csv` | 42 distance tests: 28 alternative/metric plus14 control/metric rows. |
| `directional_asymmetry.csv` | Ten matched-direction contrast tests; signed effect sizes and separate Holm family. |
| `temporal_localization.csv` | Two ERCOT seed contrasts and their two same-token diagnostics. |
| `permutation_distributions.npz` | Actual randomized statistics, including joint-path and temporal tests. |
| `subsampling_draws.csv` | Repeated subsets with shared-reference pairing, raw and IQR values. |
| `subsampling_stability.csv`, `subsampling_rank_stability.csv` | Finite-pool ranges and within-point ranking stability, never population CIs. |
| `path_descriptor_values.csv`, `path_descriptors.csv` | Individual per-path descriptors and their summaries/endpoint Wilson intervals. |
| `protocol.json` | Hashes, conventions, RNG, counts and scoped limitations. |
| `proposed_data_selection.json` | Data-only future window checks; no new token probabilities or eligibility claims. |

Tests cover known W1/ED answers, unequal empirical sizes and unused pool rows,
joint path structure, plus-one/tie/two-sided tails, Holm arithmetic, shared-reference
subsampling, deterministic full-N handling, directional/temporal contrasts,
known linear slopes and Wilson boundaries, reproducible streams, source-output
isolation and multi-fork processing without source modification. Main pipeline
tests remain offline with no pretrained model.

Verification: **224 offline tests pass**, with one unrelated AnyIO/Pytest
deprecation warning. The source-hash check found no changed Phase 2 input files;
the final script matches its recorded protocol hash. Historical September summary
SHA256 remains `04a41da4b55ed353986796c1378ede65abe4d269e20a520ea2f344c75c75021e`.

**Deliverable A conclusion:** the expected value of **one M4 replication group**
is high enough to justify an approximately1-2 hour approval request. The extra
four groups add narrow external feasibility evidence at meaningful cost; they
should not be sold as a definitive foundational-paper experiment. The RQ3
extension is not currently recommended. Stronger general claims remain unpowered.

**STOP FOR USER APPROVAL:** choose A only or the explicitly staged maximum-five
design (and any separately priced extension), with the stated eligibility rules
and compute ceiling. No Phase 3 inference, further sampling, Phase 4 or manuscript
work follows automatically from this document.
