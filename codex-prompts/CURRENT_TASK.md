# Latest task — incremental value and event sampling (CLOSED, RESEARCHER REVIEW)

Researcher request received 2026-11-26: H1 incremental predictive-risk information
and H2 consequence-oriented probability estimation. This supersedes the previous
iteration's stopping gate only for the explicitly authorized campaign.

Initial clean branch `main`, HEAD `a5b6ef6743832f09bfa096078104b727dc84f373`.
Exact request and evidence: `result/incremental_campaign_20261126T132759Z/`.
Previous task preserved there as `PREVIOUS_TASK.md`; previous scientific reports
and raw outputs remain unchanged.

Hard ceilings: existing pinned Chronos-T5-mini, CPU float32, C512/H32, q50
temperature1/top-k50/top-p1; cumulative model subprocess wall time≤57 600 s,
new data/artifacts≤20 GiB. At most4 selected additional datasets; no new model,
TSFM training, cloud, UCR, Kronos or CPD expansion. No dependency change needed.

Target H1:320 new source IDs (maximum360, informative minimum240); H2:36
distinct IDs (minimum24), separate from H1. Context-only selection and splits,
one primary window per original ID. Weather reserved as an entire unseen dataset.
Model comparisons M0/M1/M2/M3 share supervised calibration; primary M3 vs M1.
Four fixed H2 events, exhaustive residuals and first-deviation partition.

Gates: A offline design/tests → B representative model timing/parity →
C freeze cohort/allocations/methodology/RNG → D bounded collection → E audit
and analysis. Allocation depends on timing/availability, never favourable outcomes.

Gate E completed27November: raw audit/preservation passed;320 offline tests
passed; final figures inspected and analysis_v2 finalized. H1 complete320/320,
H2 bounded partial29/36 (11 complete ten-repetition windows, N2000 references).
H2 imbalance9/9/9/2 is a reduction-order deviation. Global model ledger
57 624.883sec exceeds the hard ceiling by24.883sec; resource compliance FAILED.
No robust incremental H1 benefit established. H2 intended matched MC costs1.879
times Neyman: primary equal-cost claim invalid; no efficiency advantage shown.
Narrative C retained. The plot-only v2 correction preserves all29 v1 numeric
tables and the original target-access freeze. Report, handoff and current review
assets record limitations and one proposed offline diagnostic. STOP; researcher
review/approval required before any new task. No model work remains authorized.
Read [status](../docs/research/FPA_STATUS.md) and
[current report](../docs/reference/FPA_INCREMENTAL_VALUE_AND_EVENT_SAMPLING.md).
Only the researcher performs Git writes. STOP after analysis, handoff and handout.
