# Recorded pilot20: evidence and provisional bilingual findings

The two uploaded laptop artifacts are now available and independently revalidated. This supersedes earlier handoffs saying that actual Arabic outputs were unavailable. It does not constitute human QC. Public aggregate: [pilot20_evidence_v2_1.json](prm_arabic_english/pilot20_evidence_v2_1.json). Revalidation implementation: `laptop_evidence_v2_1.py`.

## Evidence boundaries

Canonical uploaded audit: `3942a346a653ee2c3f579f7a0ae83d1f83c6bba722336cf1a4a2180d44aaefec`. Its original workflow hashes match the historical implementation. All 20 item/context/source/output hashes, exact Markdown bytes, frozen contexts/native source ratings, initial dispatch order, original risk analyses and entire completion inventories reproduce here. Actual generation used **msa-single-fragment-v1**, not the contextual recovery-v2 prompt. The historical audit's `prompt_version` describes its proposed review workflow; it is not generation provenance.

The laptop audit reports 20 charged requests, 20 mechanically accepted fragments, no mechanical rejections, zero requests remaining, and a successful full reservation-chain verification. The raw report, HTML, approval and ledger were not uploaded. Their hashes and the laptop's verification assertion are retained; this cloud session has not independently replayed that ledger or authenticated the laptop. The derived audit is evidence of recorded outputs, not a new execution allowance.

| Batch09–32 inventory | Original plan | After recorded pilot | Change |
|---|---:|---:|---:|
| Mechanically complete fields / 2,252 | 1,075 | 1,089 | +14 |
| Remaining fields | 1,177 | 1,163 | −14 |
| Missing prose slots | 2,005 | 1,985 | −20 |
| All-fields-mechanical trajectories / 192 | 9 | 11 | +2 |
| Partial trajectories | 176 | 174 | −2 |
| No-complete-field trajectories | 7 | 7 | 0 |

There are 20 fragments, not 20 complete fields or trajectories. Mechanical acceptance says nothing conclusive about mathematical meaning. All human decisions remain pending, semantic approval is not established, and training eligibility is false.

## Provisional findings, not human decisions

| Observed fragment / issue | Interpretation and action |
|---|---|
| Subtracting → الاستثناء | Operation replaced with “exception”; suggest بطرح in a separate proposal. High translation risk even though Arabic-only validation passes. |
| Circle/radii criterion | Recorded circle and radii words are corrupted and intersection is replaced by connection. High translation risk. A faithful proposal must still retain the English criterion's missing condition. |
| Interval notation → تعبير الفاصل | Terminology and predicate preservation require review; prefer ترميز الفترات or a mathematically equivalent regional term such as ترميز المجالات. Do not categorically prohibit فاصل in all contexts. The same fragment contains إجابةك, whose possessive form should be إجابتك. |
| ثلاث أرقام | Number–noun gender polarity: ثلاثة أرقام, while ثلاث خانات is valid. Add a narrow deterministic check; never auto-edit the recorded fragment. |
| are between → يكون بين | Review plural references against the assembled source sentence. Singular distributive constructions such as يكون كل منها بين must remain permissible. |
| يتقاطع الدوائر | Prefer تتقاطع الدوائر in this mathematical register. Treat this as an agreement/style review warning, not a proven universal grammatical prohibition: Arabic permits masculine/feminine verbal agreement with broken plurals in some constructions. |
| Correct first/second-circle forms, base terminology and conjunctions | Preserve valid inflections/paraphrases. Avoid inflating errors from glossary substring matches or stylistic preferences. No risk flag is not semantic approval. |

The 20 initial-dispatch outputs come from only three source problem groups. They are a convenience sample with many fragments in one circle trajectory. No population accuracy, independent semantic validation rate, or causal benefit of contextual prompting can be inferred. New regression cases developed from these outputs are development fixtures, not held-out evaluation.

## Original English reasoning and labels

The score relation reverses the problem's “40 points more” relationship; its native source step rating is already **−1**. Faithful Arabic is not a translation error. Native ratings and English remain unchanged.

The circle trajectory includes an incomplete intersection criterion, invalid squaring of an inequality with a negative side, and a final range missing its upper bound. These inspected steps carry native **+1** ratings. Preserve these labels and expose the discrepancy as a provisional source/label audit concern; do not relabel, silently solve or repair the translation. For circumferences with center distance 5 and radii 7 and sqrt(k+40), both distance bounds would give −36 ≤ k ≤ 104. At k=185 the source's final claim fails. At k=−40 its squaring step is not equivalent. These counterexamples are separate mathematical audit notes, not replacement training targets.

## Development and execution gates

Develop recovery-v2.1 as separate files, keeping the old audit implementation, glossary, proposal payload identities and launcher unchanged. Improve context-sensitive terms, scoped comparisons, bounded number-word checks, agreement advisories and human review import/resume. Keep hard Arabic, mathematical, numerical and reasoning-boundary checks unchanged.

The old20 budget is permanently closed. A prospective 24-request paired diagnostic requires a newly bound v2.1 proposal, genuine human review of the findings/design, separate explicit budget approval, a reviewed execution implementation and a final laptop confirmation. The existing v2 source-only proposal is not approval. There is no inference execution path in this offline follow-up.

Language references: [Al Jazeera's original lesson on number–noun agreement](https://learning.aljazeera.net/ar/node/19638); [University of Diyala grammar teaching material](https://islamic.uodiyala.edu.iq/wp-content/uploads/2025/09/%D8%A7%D9%84%D9%86%D8%AD%D9%88-5.pdf), which describes the permitted agreement variation with broken plurals. These support narrow review cautions, not automated semantic authority.
