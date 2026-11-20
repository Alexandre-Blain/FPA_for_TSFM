# Scientific test matrix and critical alternatives

**Integration annotation - 2026-11-19:** H1-H9 are **hypotheses** and their tests
are **suggested**. F1-F6 are **observed (historical reports)**, with artifact
integrity checked but statistics not recomputed. See
[verified status](FPA_STATUS.md) and [audit](FPA_IMPLEMENTATION_AUDIT.md).

**2026-11-19 | hypotheses, NOT results.** To be updated from evidence after each experimental milestone. This is not a grant of inference budget.

| ID | Hypothesis / question | Primary measurement | Serious alternative / confounder | Most informative test | Claim threshold |
|---|---|---|---|---|---|
| H1 | Plausible local tokens cause nontrivial distributional separation beyond Monte Carlo noise | W1_fixed22/ED_fixed22 vs independent same-token | Finite-N noise, candidate selection, shared baseline ensembles | Prospective representative branch sample, whole-path permutations, seed replication | Effect sizes + null controls + across-series evidence |
| H2 | Downstream impact is not reducible to immediate numeric jump | sensitivity conditional on signed/abs J, bin size, p and context | Quantization, nonlinear numeric autoregression, autocorrelation, scale | Matched |J| contrasts across *independent* windows plus simple numeric propagation baseline | Prospective evidence, not one selected M4 example |
| H3 | Sensitivity has heterogeneous relation with local uncertainty | within-series conditional dependence on entropy, p, coverage | Dataset mix, original-series identity, J, no within-series variation | Stratify/block by original series, include controls and uncertainty | No global entropy-independence from pooled correlation |
| H4 | Some forks are localized rather than persistent | per-horizon W1 profile; first10 vs later; fixed22/full | Changes in denominator/support, pointwise MC noise, post hoc split | Predeclared early/late on new windows, path-level uncertainty | Replicate beyond ERCOT selected example |
| H5 | Forks create interpretable temporal outcomes | conditional distributions of direction/trend/extrema/threshold | Single-path cherry-picking, quantized ties, changes in level only | Predeclared descriptors and null cases; ensemble-based evidence | Concrete outcomes with measured uncertainty |
| H6 | Generative outcome distributions undergo reproducible drift/regime changes as greedy prefix grows | `P_t(E_delta)` t0..15; `D(P_0,P_t)` and adjacent changes | Deterministic endpoint collapse, finite N, mix/direct estimator boundary, CPD overfitting 16 points | Per-window variance bands + overlap calibration; only then CPD | No structural break claim from isolated BEAST output |
| H7 | Dense reference permits reliable cost-vs-information comparison of sparse schemes | recall@position-budget / error vs dense paths | N20 noisy targets, selection leakage, dependence and baseline costs | Hold out series, simulate sparse after masked observations, independent confirm subset | Compare at matched real computational cost |
| H8 | Internal representations contain additional signal about future sensitivity | cross-validated predictive performance from layers/attentions vs logits/p/J | Encoder input leak, memorization, sample size, overfitting, architectural confounding | Grouped held-out series, ablation, before/after-fork encoding | Incremental *out-of-sample* value, not correlation alone |
| H9 | Caching, batching, pooling materially improve FPA efficiency without bias | exact logits policy/parity; throughput vs baseline; statistical error | Decoder changes, attention implementation, memory overhead, pooling bias | Paired deterministic microbench plus statistical drift controls | Measured reduction in cost at controlled estimator error |

## Evidence ledger from existing reports (do not promote without rechecking)

- **F1 - Sampling noise:** Phase 2 7 executed groups, 1,400 sampled paths, only 3 original series. Independent greedy-token controls showed some alternative differences comparable to MC noise. Phase 3 explored whole-trajectory permutation / finite-pool subsampling.
- **F2 - M4 asymmetry:** M4 Daily T000001 b0, reference token2188, down2187, up2189; |J|/context IQR ~0.2046 for both, W1/IQR ~0.112 vs ~0.308, ED/IQR ~0.017 vs ~0.119 at seed1729. **Selected one context, one seed**, probabilities and signs confounded. Stage A planned, never launched as of user report 2026-11-19.
- **F3 - ERCOT localization:** EAST b0/token2228 early/later difference observed on two seeds at one context; time split chosen after seeing data.
- **F4 - Exchange Rate:** currency_3 b16 alternative divergence and unstable ranking.
- **F5 - Entropy:** old legacy-composite cross-dataset correlations heterogeneous, Phase 2 pooled new-distance correlations confounded by between-series effects. No general entropy-law evidence.
- **F6 - Morphology:** saved ensemble plots and simple descriptors; no broad confirmed motif transformation or automated detector.

## Key negative / falsification outcomes to preserve

1. After conditioning on J/p/series, FPA outcomes may be predictable from simple baselines; then high-cost branching may bring little incremental interpretative value in that domain.
2. CPD curves may be mostly smooth/uncertain for 16 points; then formal CPD contributes little beyond descriptive drift.
3. Hidden states or attentions may add no reliable held-out predictive information beyond logits and J; this limits white-box claims.
4. Pooling across positions can erase genuine rare forks; test underestimating risk rather than automatically calling it efficient.
5. Classifier attribution on UCR targets a different estimand, so its disagreement with token FPA would not demonstrate utility.

## Paper 1 narrative (conditional on evidence)

Act 1: numerically rigorous conditional FPA. Act 2: distribution and mechanisms of consequential decisions, including negative findings and competing numerical explanations. Act 3: how effects propagate and transform forecast trajectories; optional distributional drift and internal-state predictability. Efficient screening is a possible methodological side contribution, not proof of FPA validity by definition.

Explicitly separate *what experiments show*, *what they suggest*, and *what we hypothesize* in every handoff.
