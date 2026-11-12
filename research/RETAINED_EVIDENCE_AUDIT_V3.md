# Retained evidence audit: supervisor-directed scientific revision

Audit baseline: research branch `cd0e2c2880b0010ff7ba8645f508b2e4578a171a`.
The [aggregate replay](RETAINED_EVIDENCE_AUDIT_V3.json) hashes twelve retained
inputs and recomputes their metrics without importing legacy model runners.
No new model evaluation, annotation or inference took place.

| Retained experiment | Actual denominator and reproduced result | Defensible interpretation |
|---|---|---|
| Original AR/EN discrimination | Same 20 IDs, 4 authored categories each: 80 responses/language. Correct-minus-mean-wrong score: AR 0.108043, EN 0.356174; paired difference 0.248131. | Evidence of a scoring difference on these selected examples; neither 80 independent problems nor an Arabic population estimate. |
| Arabic adaptation pilot | `synthetic_pilot`: 80 train rows/40 problem pairs, 20 dev rows/10 pairs; no pair-ID or exact normalized problem-text overlap. Dev: 59 positive and 20 negative steps. Reloaded step gap 0.240758 → 0.669094; trajectory gap 0.082271 → 0.279188. | A small synthetic development experiment. Dev was used for model selection; these are not final held-out test results. No qualified Arabic annotator provenance is established by these files. |
| Recorded “Arabic generalization” | All 20 embedded Arabic examples and retained response texts are identical to the original baseline set. Adapted score gap 0.190227; paired change +0.082184. | Transfer from the synthetic adaptation set to the earlier handcrafted set. Withdraw claims of a new independent benchmark or broad Arabic generalization. |
| English retention | Reuses all 20 original English examples. Gap 0.356174 → 0.356280. | No observed gap deterioration on this small reused set; not an equivalence/non-inferiority test or proof of general English retention. |
| Translated ArabicPRM-T | Historical approved v1: 32 trajectories/298 steps; expansion v2: 256 trajectories with incomplete translation/QC. | English-origin translated material, with inherited PRM800K supervision. It cannot satisfy an Arabic-native, independently human-labeled evaluation requirement. No new corpus approval is implied. |
| Downstream mathematical solving | No retained fixed-candidate reranking experiment identified in this audit. | PRM margins, step classification and checkpoint reload consistency do not show improved final-answer success. This is missing evidence. |

The seeded 5,000-draw paired **problem-ID** bootstrap gives descriptive 95%
intervals of [0.199705, 0.297541] for the original EN–AR gap difference,
[0.061656, 0.102324] for the Arabic adapted-minus-base gap change, and
[−0.007558, 0.008644] for English retention change. These intervals condition on
the selected twenty problems. They do not remedy purposive selection, possible
related templates, uncertain bilingual equivalence or missing annotator evidence.
The rows are not eighty independent experimental units. Native source-family
clustering cannot be reconstructed from their IDs alone.

One of the eighty AR/EN candidate pairs has different recorded step counts.
Whole-response averages remain reproducible, but a stepwise language comparison
needs an explicit bilingual alignment audit. The retained CSV step scores are
rounded to four decimals; this audit uses their original `average_score`, not
means reconstructed from rounded entries. Immutable model/tokenizer revisions,
full environment and independent per-step Arabic human labels are absent from
the score CSVs. Source correctness and category correctness need separate review.

## Claim changes

The thesis may report a **small, selected-set language discrepancy** and an
**exploratory synthetic-pilot adaptation result**. It must not claim that Arabic
inferiority is explained, that translated PRM800K is an Arabic-native benchmark,
that broad generalization or English retention is established, or that solver
accuracy improved. Historical results and their filenames remain unchanged.

The supervisor-directed next study must diagnose scoring versus generation
effects before further fine-tuning, prioritize originally Arabic problems and
reasoning with qualified human Arabic step labels, and measure held-out
final-answer success using a fixed candidate pool shared by all rerankers.
Translation QC becomes a supporting, sampled fidelity audit; further recovery
or reviewer-interface development is not the critical scientific path.

## Reproduce offline

From a checkout containing the explicit retained inputs:

```text
python -B research/prm_arabic_english/evidence_audit_v3.py
python -B -m unittest discover -s research/prm_arabic_english -p test_evidence_audit_v3.py -v
```

Output is aggregate JSON on stdout, with no problem/response export and no
model-client imports. Exact original bytes are preserved on Windows using
targeted Git attributes. The new tests reject missing categories, duplicates,
invalid scores and misaligned steps. CI proves this replay, not annotation
quality or the validity of the historical category assignments.
