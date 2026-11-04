# Prospective probability audit of the early ArabicPRM-T drafts

**No groups have been drawn or reviewed for this audit.** This proposal concerns reviewer workload on existing drafts. It authorizes no generation, corpus approval, dataset export or training.

The [reproducible mechanical replay](CORPUS_QC_METHOD_V2_3.md) finds 64 early source problem groups and 757 field positions. The strata are 35 train whole-passing, 18 train blocked, 10 dev whole-passing and one dev blocked. Whole-record screening leaves 224 individually passing fields in blocked trajectories. A probability audit restricted to the 45 whole-passing trajectories would therefore answer a different question. Keep this early frame distinct from Batch09–32 recovery and the previously approved v1 corpus.

## Proposed estimand and unit

Estimate the fraction of **early source problem groups with at least one major or critical translation error in their original candidate-bearing fields**, using independently reviewed evidence and resolved adjudication. Review all available original fields in each drawn group, even if a different field failed mechanical checks. Count a confirmed major or critical error as a positive group finding; count no such error only if all relevant fields can be assessed and are resolved. Otherwise retain an unknown status. Mechanical rejection, unavailable text, English source reasoning errors and Arabic fidelity are separate. Never replace the original candidate with a proposed correction for this estimand. This is a source-group rate, not a field error rate or a measure of recovery quality in the later cohort.

## Compare reviewer capacity before a draw

The [aggregate planner](ARABICPRMT_EARLY_QC_SAMPLING_V2_4.json) proposes a census of all 11 dev groups and independent simple random sampling without replacement in both train strata. Train draws are near-proportional, with at least two groups in each stratum. Each group has inclusion probability n/N in its stratum. The expected field counts below use the actual field totals for each stratum and count each selected field position once; two independent reviewers each cover those positions. Neither person-hours nor actual counts for a future draw are known.

| Review capacity, groups | Train whole pass / blocked | Dev whole pass / blocked | Expected field positions | Worst-case chance of finding ≥1 if exactly 7 of 64 groups are affected |
|---:|---:|---:|---:|---:|
| 24 | 9 / 4 | 10 / 1 | 266.8 | 87.0% |
| 32 | 14 / 7 | 10 / 1 | 365.4 | 97.7% |
| 40 | 19 / 10 | 10 / 1 | 464.0 | 99.8% |

The detection calculation assumes the chosen groups can all be classified accurately. With N groups, n draws and D hypothetical affected groups in a stratum, the chance of a miss is C(N−D, n)/C(N, n): the count of unaffected draws divided by all possible draws. For each allocation of seven affected groups across strata, multiply the stratum miss probabilities, subtract from one, and take the least favorable detection probability. The scenario uses seven groups (10.9% of the frame) to compare designs; it is not an estimate of prevalence. The single-affected-group scenario is far less informative: worst-case detection is only 22.2%, 38.9%, or 54.3% across these capacities. Review uncertainty and unavailable evidence reduce what can be concluded.

**Recommendation for a future owner decision:** if staffing can cover about 731 independent field judgments plus adjudication, the 32-group option balances the three evaluated workloads while improving the seven-group scenario over 24. This does not select a capacity, start an audit, or imply enough precision to declare the corpus safe. Make the decision before viewing reviews.

## What the reviewer and analyst record

1. Freeze the cohort, severity definitions and strata. Record the selected capacity, draw seed, source-group identities and inclusion probabilities privately, before any reviews. Keep the two assessor records independent; adjudicate disagreements without replacing candidates.
2. Report the completed and missing review denominators by stratum. For resolved data use the stratum rates weighted by stratum population share, not the raw pooled sample proportion. The proposed dev census intentionally oversamples dev relative to its frame share.
3. For unresolved groups, report sensitivity using both extremes for those groups within each stratum. These bounds describe unresolved-review sensitivity of the weighted estimate, not its sampling error. Any sampling interval requires a separately justified design-based method; neither the bounds nor the hypothetical detection calculation is a confidence interval.
4. Present severity and disagreement counts and source-reasoning findings separately. Preserve split and native supervision masks, and do not use this audit to repair labels or automatically promote a record.

Reproduce the aggregate design with `python -B research/prm_arabic_english/early_qc_sampling_plan_v2_4.py`. It reads the existing public audit and writes no draw, candidate data, human record or authorization.
