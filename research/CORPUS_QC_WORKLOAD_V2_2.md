# Corpus completion and QC workload — 2026-11-03

Replayed the existing hash-bound original plan and derived pilot audit, including the exact companion Markdown, source contexts, recorded output hashes and original inventory. The [aggregate-only result](prm_arabic_english/corpus_workload_v2_2.json) is reproducible with `corpus_workload_v2_2.py` given those three private inputs. It contains no source rows, Arabic outputs, reviewer identities or local paths. This independently reproduces the earlier **derived** evidence, not the raw laptop reservation ledger.

| Batch09–32 split | Whole mechanically complete | Partial | No complete fields | Complete / total fields | Incomplete fields | Missing prose slots |
|---|---:|---:|---:|---:|---:|---:|
| Train | 10 / 151 | 136 | 5 | 867 / 1,746 | 879 | 1,503 |
| Dev | 1 / 41 | 38 | 2 | 222 / 506 | 284 | 482 |
| Total | 11 / 192 | 174 | 7 | 1,089 / 2,252 | 1,163 | 1,985 |

| Native field stratum | Train incomplete fields / missing slots | Dev incomplete fields / missing slots |
|---|---:|---:|
| Problem text | 121 / 300 | 34 / 79 |
| Supervised positive step | 646 / 1,027 | 216 / 351 |
| Supervised negative step | 43 / 73 | 16 / 25 |
| Neutral masked step | 69 / 103 | 18 / 27 |

The recorded pilot20 closed 14 fields and two whole trajectories. It did not create semantic approvals. Neutral steps remain present for context and masked in supervised metrics; do not count them as negative examples. All 2,005 original exhausted-slot counters remain at nine. These counts describe the prior verified evidence, not a fresh survey of an inaccessible laptop.

Batch01–08 is a separate queue: 45/64 whole records passed current strict screening over 757 fields, with 35 field/record check failures. Do not sum different screening regimes into one corpus success rate or pool the separate historical v1 cohort into v2. Keep the 19 early blocked records separate for classification of actual translation defects versus known mechanical parser false positives; no parser migration or automatic repair is implied. Even the 45 passing and 11 complete records require bilingual review before any new corpus approval.

### Early-batch failure triage

A read-only replay of the strict checker, using the same Batch01–08 inputs as `project_evidence_v2.collect()`, found the same exact-math fingerprint failure on all 35 blocked fields. Failures in Batch01 through Batch08 were 6, 1, 6, 2, 8, 4, 1 and 7. In each blocked source/candidate pair, the ordered sequences of decimal digit runs matched after mapping Unicode decimal digits to their ASCII values. That rules out a simple inserted, omitted or changed digit run in this comparison. It does not check signs, decimal points, fractions, operators, identifiers, or where a number attaches to the reasoning. All 35 remain blocked.

Review the parser-boundary and display-math annotation cases already identified in [strict revalidation notes](STRICT_REVALIDATION_NOTES_V2.md) first. For other cases, compare literal expressions and operators alongside the complete English and Arabic fields. Track a suspected parser artifact, an actual translation change, a source issue and an unresolved case separately; require evidence for each classification. Neither matching digits nor a parser suspicion clears the mechanical gate or supplies human QC.

For review planning, keep three lanes: complete records for full bilingual review; partial records for missing-fragment recovery planning; source reasoning/annotation disputes for a separate qualified adjudicator. Inspect negative and neutral contexts alongside positive steps, including the reasoning before and after the target. The apparently small dev negative subset is only 5/21 mechanically complete, and just one whole dev trajectory is mechanically complete. Evaluating only complete cases would select an unusual subset. Do not move any group across splits to improve counts. Record actual person, exposure, item dispositions and review time when genuine review occurs; this inventory measures fields and slots, not person-hours or QC accuracy.

## Future PRM study design (inactive)

1. Obtain authentic bilingual QC and explicit, separate export and training approvals. Freeze the eligible corpus version, inherited problem-group splits, source labels/masks, exclusions and evidence coverage. Record source disagreements separately. Neither the small prompt diagnostic nor the historical v1 corpus substitutes for this gate.
2. Before a resource pilot, pin base model/tokenizer revisions, exact templates, environment and seeds. Verify source/Arabic step alignment and reward-token positions on authorized reviewed examples; reject silent truncation and compare English/Arabic on identical source groups. Mask neutral labels in both the objective and scoring. The reported 4 GB VRAM is a planning constraint, not measured feasibility; no GPU/model load or training is performed by this milestone.
3. Compare a pinned, unadapted PRM with the future adapted model on the same eligible held-out groups and identical scoring rules. Report per-language coverage, group/trajectory and supervised-step denominators, both class recalls, balanced accuracy, Brier score and log loss. Prespecify threshold selection using training/validation only, then freeze it for final comparison. Distinguish source correctness from translation fidelity in exclusions and report the associated attrition.
4. Report within-source paired differences, first per problem group and then equally weighted across groups. Show sensitivity to disputed/missing cases; no step-level independence assumption or optimistic complete-case-only headline. If the verified held-out group count is inadequate, publish descriptive counts and defer population inference. Do not treat the 12 train-split diagnostic pairs as PRM held-out evaluation.

No inference, active budget, data export, training or human decision was created.
