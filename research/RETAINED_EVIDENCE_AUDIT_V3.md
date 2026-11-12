# Retained evidence audit: supervisor-directed scientific revision

Audit baseline: research branch `cd0e2c2880b0010ff7ba8645f508b2e4578a171a`.
The [aggregate replay](RETAINED_EVIDENCE_AUDIT_V3.json) hashes thirteen retained
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

One of the eighty AR/EN candidate pairs has different recorded step counts:
problem ID `6`, category `correct`, has seven Arabic steps and six English steps.
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

## Additional recorded-score diagnosis

The retained nominally correct category is uniquely highest on **12/20 Arabic
base**, **16/20 Arabic adapted**, **20/20 English base** and **20/20 English adapted**
problems; there are no highest-score ties in these sets. Against the individual
arithmetic/logic/completely-wrong categories, Arabic base wins 18/20, 16/20 and
16/20 respectively; the adapted scorer wins 18/20, 18/20 and 19/20. All English
comparisons win 20/20. These counts are reproduced in the aggregate artifact.

This demonstrates a **nominal ordering weakness as well as an absolute-score
shift** within the selected set: a strictly monotonic score recalibration alone
cannot change the within-problem ordering. It does not determine whether the
underlying cause is language representation, label error, bilingual content
mismatch, segmentation or another confound. The category labels remain
unverified, and the four candidates were authored with a correct category by
construction. Do not call these counts generated-solution accuracy or downstream
solver improvement. They motivate the native, human-labeled fixed-pool experiment.

## Scoring-pipeline and precision audit

Static inspection of the retained runners and `model_utils/io_utils.py` found
that `prepare_input` splits the untrimmed literal response on every newline and
flags **every segment**, including empty first/last segments, for a reward. Each
of the eighty candidates in each language has two such empty boundary lines.
The recorded counts exactly match raw newline segments: **160/547 Arabic** and
**160/546 English** reward positions are blank. A deterministic test executes only
the extracted input-preparation function with a synthetic tokenizer; it imports
neither the helper's torch/numpy imports nor a model. No helper or source is fixed.

A read-only sensitivity analysis excludes those empty positions **only from a
new aggregate of the retained four-decimal CSV scores**. It does not remove any
tokens from the original model input, regenerate scores or replace original
results. Rounding and the lack of a fresh controlled run limit its interpretation.

| Recorded set | All-position gap, rounded CSV | Nonempty-position gap, rounded CSV | Nominal correct uniquely highest after exclusion |
|---|---:|---:|---:|
| Arabic base | 0.108042 | 0.107055 | 13/20 |
| English base | 0.356175 | 0.334755 | 20/20 |
| Arabic adapted | 0.190226 | 0.194221 | 16/20 |
| English adapted | 0.356277 | 0.332643 | 20/20 |

The base EN–AR gap difference remains about **0.227700** after this aggregation
sensitivity. Empty-line inclusion changes measured scores and one Arabic ranking,
but does not remove the selected-set ordering/gap discrepancy. This is evidence
for a concrete measurement issue, not a complete explanation of Arabic weakness.
Future diagnosis must explicitly verify mathematical step/reward alignment and
mask nonreasoning steps under a frozen policy; retain the old results unchanged.

The checked-in base runners load `PRM_MODEL.from_pretrained` without an explicit
4-bit configuration, whereas adapted retention/generalization runners explicitly
declare NF4 4-bit quantization and float16 compute. Both use the same model name
without an immutable revision pin. Base extraction uses `derive_step_rewards`;
adapted extraction directly indexes reward flags. Those single-batch masks appear
equivalent in the inspected source, but the historical execution environment is
not authenticated by source code alone. Consequently **adapter-only attribution
of these old twenty-problem adapted-versus-base changes is not established**. A future controlled
comparison must include an unadapted base at the same quantization/runtime,
tokenizer, step extraction and aggregation as the adapter. It requires separately
authorized scoring; no new training is needed to perform that eventual diagnosis.
