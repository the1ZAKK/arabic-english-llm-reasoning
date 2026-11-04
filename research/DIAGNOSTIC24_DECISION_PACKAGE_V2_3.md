# Diagnostic24: decision and analysis plan

**Status: prospective and pending genuine human design review.** The frozen 12-pair proposal, 24-request limit, prompts, release, source-only review ZIP and blind materials are unchanged. There are no new outputs or human judgments. This is a companion to the [verified identities and execution limits](DIAGNOSTIC24_REVIEW_READINESS_V2_2.md), [12-slot source audit](DIAGNOSTIC24_REVIEWER_BRIEF_V2_2.md), and [editable bilingual design form](DIAGNOSTIC24_DESIGN_REVIEW_V2_1.md).

## What the comparison would measure

The proposed endpoint is **operational usability of the recorded original first dispatch** for each arm: a durable, unchanged, mechanically accepted fragment judged faithful under resolved bilingual review. The analysis treats concordant blinded decisions as determinate for this endpoint and bounds unresolved decisions. It cannot quantify error in concordant judgments, approve human QC or substitute for adjudication. A faithful rendering of incorrect English reasoning still counts as faithful. A supported correction never replaces the original candidate in this analysis.

| Original output and review evidence | Usability value | Separate accounting |
|---|---:|---|
| Accepted; both assessors say faithful | 1 | Agreement is recorded, not approval. |
| Accepted; both say translation error | 0 | Preserve severity and category disagreements and proposed corrections. |
| Accepted; decisions disagree, are incomplete or uncertain | 0 to 1 | Keep unresolved; do not replace with majority vote. |
| Rejected or charged with no outcome | 0 | Mechanical/transport failure is not a human semantic judgment. |
| Not attempted | Unknown | Keep the position in the record; the new tool blocks partial-run unblinding. |

For each pair subtract the control usability from the contextual usability. If the two values are only known to lie in intervals, the exact difference interval runs from contextual lower minus control upper to contextual upper minus control lower. Report:

- The mean over **all 12 planned pairs**, plus all **24 planned positions** with separate mechanical, review and uncertainty counts.
- The mean of the **seven equally weighted source-group means**. Also show each group and repeat the group-weighted mean leaving one group out at a time.
- Both endpoints of every bound. Conditional on concordant decisions, bounds show how unresolved decisions could change the conclusion on this fixed sample. They are not confidence intervals. Report English source concerns, error detail disagreements and proposed corrections separately.

The [reproducible source-only audit](DIAGNOSTIC24_PROSPECTIVE_DESIGN_V2_3.json) finds groups of size 5, 2, 1, 1, 1, 1 and 1. The circle group contributes 5/12 by pair weighting and 1/7 by group weighting. The two reused groups together contribute 7/12 or 2/7. Six pairs dispatch each arm first. All slots come from train. **Synthetic example only:** if the contextual policy wins all seven reused pairs and loses the five other pairs, the pair-weighted difference is +1/6 and the equal-group difference is −3/7. A direction change like this is evidence of dependence on sample weighting, not a result to average away.

The [analysis code](prm_arabic_english/diagnostic_decision_analysis_v2_3.py) emits that design audit by default. The future `--post-terminal LEFT_SEAL RIGHT_SEAL OPERATOR_BUNDLE` option requires two distinct, validated, asserted-human assessment seals for the same queue, rejects unattempted positions before opening the mapping, and checks the original bundle and all 24 reservations. It prints a text-free operator summary; keep it private until separately reviewed. The tool validates bundle consistency; it cannot establish reviewer independence or replay the private laptop ledger. It does not apply corrections or pass any human gate.

## Neutral calibration before looking at outputs

Use only invented practice items unrelated to the selected source problems. Each assessor first records a private practice judgment with a rationale; discuss the practice rubric before any real blind materials are opened. The table provides a calibration key, not human labels or experimental outcomes. Do not share the design package, known pilot failure examples or arm mapping with outcome assessors.

| Invented English source | Arabic rendering | Practice distinction |
|---|---|---|
| At most two of the five entries are zero. | لا يزيد عدد الأصفار بين المدخلات الخمسة على اثنين. | Faithful; replacing the bound with «أقل من اثنين» excludes the endpoint and changes the relation. |
| Each row contains at least one zero. | يوجد صفّ يحتوي على صفر واحد على الأقل. | Translation error: existence replaces a universal claim. |
| The length is 3/8 of the original length. | الطول يساوي 8/3 من الطول الأصلي. | Translation error: inverting the fraction changes the quantity. |
| Since x² = 9, x = 3. | بما أن x² = 9، فإن x = 3. | Faithful to the stated step. Separately flag the missing negative solution if no domain restriction was supplied. |
| The two lines intersect. | يتقاطع المستقيمان. | Faithful. «تتقاطع المستقيمان» has an agreement error, but the geometry may still be clear. |

Judge meaning in context. A synonym or valid Arabic construction is not a defect. A minor error leaves the mathematical claim recoverable without guessing; major changes alter an operation, scope, relation, entity or substantive inference. Reserve critical for changes that reverse or invalidate the task/answer or introduce unsupported reasoning that materially changes evaluation. If context cannot decide, record uncertainty and why. Never silently repair an English claim or a native source label.

## Remaining decision and next evidence

| Responsible person | What to record or decide |
|---|---|
| Qualified design reviewer | Personally inspect the exact 12 targets and both prompts in the bilingual form. Review the scoring rule, weighting sensitivity, failure handling and limits on generalization. Record real identity, qualifications, exposure/conflicts, time and **approve design only**, **request changes**, or **defer** with rationale. |
| Project owner | Record whether the analysis plan is accepted or revised before seeing outputs; preserve the version and rationale. Assign two fresh independent Arabic–English mathematics assessors and a separate adjudicator. Verify their qualifications, conflicts and exposure outside the software. |
| Outcome assessors and adjudicator, after any separately authorized run | Assess independently using only the neutral blind queue. Seal both assessments; preserve disagreements and corrections for independent adjudication. Do not treat agreement as final QC. |
| Project owner, separately | Any later execution requires its own explicit authorization for the unchanged 24/2/1/512 limits and model/plan/release, plus local integrity checks and final confirmation. No execution decision is requested here. |

If the bounds include zero, the direction changes with weighting or group omission, or material errors or unresolved corrections remain, report the diagnostic as inconclusive or risk-bearing for wider recovery. A favorable pattern across both weightings would support designing a larger independent study, never automatic recovery, corpus promotion or training. Do not pool this selected, clustered, train-only comparison into held-out PRM results. No outcome, review, role, authorization or date has been filled in.

**Thesis-ready methods statement.** We prespecified an operational endpoint based on the unchanged recorded first response, mechanical acceptance, and two independently recorded blinded fidelity assessments. The plan retains all positions and separates missing or rejected responses from human translation errors and source-reasoning concerns. Paired descriptive differences are reported by selected slot and by source problem, with logical bounds for unresolved judgments conditional on agreement elsewhere. Because the comparison uses a small purposive training subset and contrasts two bundled prompt policies, the evidence is intended for failure analysis and study design, not population inference or component-level attribution.
