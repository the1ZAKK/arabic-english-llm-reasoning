# Corpus QC methodology: separate work triage from quality estimation

The [verified workload](CORPUS_QC_WORKLOAD_V2_2.md) shows where effort is needed, not corpus accuracy. Keep three cohorts separate: the previously approved historical v1 set (32 trajectories); the 64 early v2 drafts (45 whole trajectories pass current mechanical checks); and the 192 later v2 trajectories (11 mechanically complete, 1,985 missing prose slots). Do not add those numerators or call passing fields human-approved.

| Lane | Unit and ordering | What to record |
|---|---|---|
| Mechanical failure triage | Review the 35 blocked early fields in their 19 complete source contexts. Start with the two delimited failures, two interleaving failures and observed parser-boundary cases. | Exact span and context, candidate issue vs parser artifact vs source problem vs unresolved, proposed action and evidence. Do not alter old parser, files or labels. |
| Bilingual eligibility | Review each whole trajectory independently by two qualified reviewers; include all context, even masked neutral steps. Prioritize scarce development and supervised negative coverage for review effort, without moving groups across splits. | Original candidate disposition by field, proposed correction separately, blinded comparison and genuine independent adjudication. Preserve source reasoning and annotation questions as separate records. |
| Optional quality-estimation study | Freeze the eligible candidate frame and sample **source problem groups**, not individual surviving fragments. Stratify by cohort, split and initial mechanical status before drawing. | Record frame size, exclusions, group inclusion probability, design seed, missing reviews and denominators. If estimating a weighted rate, account for inclusion probabilities and clustering. The risk-prioritized work queue is not a probability sample. |

## Measured selection attrition in the early drafts

The [aggregate-only replay](ARABICPRMT_EARLY_QC_ATTRITION_V2_3.json) uses the original strict audit, frozen locks and native masks. Among 757 early fields, 722 pass individually, but only 498 belong to the 45 whole mechanically passing trajectories. Limiting review to those 45 would leave **224 individually passing fields** outside that work queue (31.0% of the 722). This is record-level screening attrition, not an estimate of translation errors.

| Early split and native role | Screened | Individually passing | In whole passing trajectories | Passing but in blocked trajectories |
|---|---:|---:|---:|---:|
| Train: problem | 53 | 48 | 35 | 13 |
| Train: positive | 509 | 486 | 301 | 185 |
| Train: negative | 27 | 27 | 21 | 6 |
| Train: neutral masked | 59 | 53 | 37 | 16 |
| Dev: problem | 11 | 10 | 10 | 0 |
| Dev: positive | 79 | 79 | 75 | 4 |
| Dev: negative | 5 | 5 | 5 | 0 |
| Dev: neutral masked | 14 | 14 | 14 | 0 |
| **Total** | **757** | **722** | **498** | **224** |

Whole passing coverage is **35/53 train** and **10/11 dev** trajectories. All 32 negative fields pass individually, yet six train negatives are in blocked trajectories; none may be promoted by this calculation. Track the blocked trajectories and their passing fields separately so the review queue neither loses supervision coverage silently nor treats an individual pass as eligibility. These are early drafts only, separate from the later recovery cohort.

Reproduce with `python -B research/prm_arabic_english/early_qc_attrition_v2_3.py`. No candidate text, source rows or reviewer records are written; the program prints aggregate counts and input hashes.

## Training and reporting boundary

A usable training record would require verified original provenance, approved bilingual fidelity, preserved masks and labels, and separately authorized export and training. A negative or erroneous English step can have a faithful Arabic translation; an Arabic correction of the underlying mathematics would alter the object being scored. Put native source rating disagreements in adjudication without silently changing labels. Unavailable and unresolved fields stay visible. Treat neutral steps as context and exclude them from supervised scoring. Any held-out experiment must use disjoint source groups and show label/coverage attrition, including exclusions due to translation or source disputes.

The 12-pair diagnostic is a development exercise for failure modes. Its [analysis plan](DIAGNOSTIC24_DECISION_PACKAGE_V2_3.md) and calibration are not a corpus audit, and no new corpus decision, export or training is made here.
