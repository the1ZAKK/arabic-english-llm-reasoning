# Arabic-native benchmark and human annotation specification

Prospective specification supporting [the revised study](ARABIC_NATIVE_STUDY_V3.md).
No examples, annotations or approvals are created by this document.

## Origin, reasoning and labels are three separate requirements

**Problem origin.** Count a problem as `arabic_native` only with evidence it was
originally authored for Arabic readers: a traceable Arabic source edition/page or
an actual Arabic mathematics author's original materials with permission and
authorship statement. Arabic script, an Arabic website, fluent wording or an
Arabic-speaking translator does not prove native origin. Adaptations of English
questions remain translated/derived; uncertain lineages are excluded pending
review. Record sources, retrieval/version, permission, exact bytes, normalized
duplicate keys, domain/difficulty, source lineage and template family. Human
authorship is not inferred from AI detection software. No source is acquired here.

**Reasoning origin.** Arabic candidate solutions must be originally reasoned in
Arabic, with original prompt/output, generator identity, generation language and
trace provenance retained. Translating an English chain does not qualify.
Mathematical notation and variables are allowed; predominantly English prose is
a recorded language failure, not grounds to regenerate a better candidate.
This concerns the observable trace's provenance, not an unverifiable claim about
the language of a model's internal computation.
Translated-control questions may have originally Arabic candidate reasoning;
their **problem origin still remains translated**. Human-written reference
solutions must be distinguished from model candidates and not inserted into pools.

**Step-label origin.** All evaluation Arabic step labels must be newly assigned
by qualified Arabic-speaking mathematics humans. PRM800K English labels, model
labels, AI reviews, inherited translated labels and automated mechanical checks
cannot satisfy this requirement. A correctly translated English label is still
inherited supervision. The legacy ArabicPRM-T corpus stays separate.

Final composition is measured by unique Arabic-side canonical problem group,
not steps, responses or language mirrors. Target 80% native/20% translated;
require ≥50% native and ≤30% translated in every split and overall. With only
these two evidenced enrolled classes, the ceiling implies ≥70% native. Excluded
or unknown-origin items are counted separately, never relabeled to fill quotas.
The 500-problem split targets are prospective and subject to the power/resource
decision in the study; they are not fulfilled by the existing corpus.

## Leakage-resistant assembly

1. Assemble an evidence-backed candidate frame and correct reference answer
   **before** observing model outputs. Cover the five study domains and planned
   difficulty bands, documenting the source distribution and exclusions. Do not
   cherry-pick questions after seeing PRM errors or oracle availability.
2. Group original problems, translations, English mirrors, paraphrases, number
   substitutions, candidate variants and shared templates by source family and
   lineage. Split whole groups; never split individual responses or steps.
3. Check exact bytes and normalized math/text hashes against all known historical
   train/dev/evaluation and adaptation sources, including retained PRM800K
   identities. Review near duplicates and shared templates manually. Hashes alone
   cannot detect semantic duplicates or prove absence from model pretraining.
4. Freeze the eligible group manifest and a recorded split seed. Order families by
   SHA256 of version/seed/family ID and allocate whole families within preregistered
   origin/domain strata to train/dev/test targets. Record deterministic allocation
   code/version and any capacity deviations before outcomes. Keep native and
   translated ratios valid within each split; never divide a family to hit a count.
5. Lock test references and outcomes from anyone tuning prompts, aggregators,
   thresholds or adapters. Keep mirrors and paired observations in that same split.
   No test item may become an adaptation example. Dev-only probes are not test
   evidence; freeze decisions and any sample-size revision before test unlock.

The offline validator checks declared family/lineage separation and duplicate
normalized hashes. It does not perform step 4 allocation, authenticate provenance,
recognize all near duplicates or grant dataset approval. Record any later leakage
discovery transparently and retain originals; do not silently replace test items.

## Qualified human annotation, compact rubric

Use two independent Arabic-speaking reviewers with demonstrable mathematics
competence at the problem level. At least one must be comfortable judging Arabic
mathematical exposition; English mirror reviewers also need mathematical English.
A third qualified adjudicator resolves disagreements. Keep actual identity,
qualification evidence, conflicts, independence/exposure and dates in private
research records. Publish anonymized roles only with permission. Nobody is
assigned or attested by this document. Reviewers see the problem, checked
reference and full candidate reasoning, but not PRM scores, system names, another
reviewer's decisions or AI hints during independent assessment.
Reference authors and mirror translators cannot be the sole assessors of their
own work; disclose these roles and assign independent checks.

| Annotation | Operational meaning | Analysis use |
|---|---|---|
| `correct` step | Locally justified mathematical statement/transition given explicitly stated previous assertions and the problem | Positive supervised step |
| `incorrect` step | Invalid computation, unsupported inference, wrong entity/relation, missing condition or contradiction introduced in this step | Negative supervised step; mark actual first error separately |
| `neutral` step | No assessable mathematical claim: e.g. pure transition text | Mask from supervised metrics/loss |
| `uncertain` step | Evidence, ambiguity or expertise insufficient | Retain unresolved; adjudicate; never convert automatically to positive/neutral |
| Final answer | Correct / incorrect / unresolved against the checked mathematical reference, with accepted equivalent forms/units | Separate solving endpoint; not inferred from mean PRM or step labels |

Judge **local transition validity** and record **global consistency/dependency on
an earlier error** separately. After a wrong arithmetic step, a later locally
valid operation is not automatically negative; record its erroneous dependency.
Do not reflexively copy the first-error label over the remaining suffix. A
recovery/correction can restore valid reasoning; a correct final answer can still
follow invalid steps. Label the text actually produced, not a repaired version.

Use standard error tags: arithmetic/numerical; algebra/operation; logic/condition;
geometry/entity; notation/units; language/terminology; unsupported or missing
reasoning. Tags may co-occur; they are not automatic labels. Native annotations
measure mathematical validity. The separate shortened translation-QC protocol
measures fidelity; faithful translation of wrong reasoning can pass fidelity.

Illustrative rubric examples, **not collected annotations**:

- `7 + 5 = 13`: arithmetic error. `7 + 5 = 12` is valid.
- “Subtracting” rendered `الاستثناء`: translation operation/terminology error;
  `بطرح` can be appropriate in context. Mathematical correctness is a separate axis.
- “circle of radius r”: `دائرة نصف قطرها r`; substituting `كرة` changes the entity.
- “three digits”: `ثلاث خانات`; agreement depends on context, not keyword counts.
- An open interval `(a,b)` must not become a closed interval `[a,b]`.
- `x < -1` therefore `x² < 1`: invalid implication in the English reasoning if
  originally present. Preserve it in a fidelity translation; label the mathematical
  inference incorrect. Do not silently repair the frozen source or inherit its tag.

Calibrate the rubric on a separate small practice set, outside locked test, with
actual reviewers. Record rubric changes before independent annotation. Retain
both originals, first-error choices, uncertainty and error tags; compare raw
agreement, class counts, disagreement matrix and chance-corrected agreement with
appropriate caveats for class prevalence/clustering. Adjudication records a third
person's rationale; disagreement cannot become approval by majority software.
If the reference question is ambiguous or wrong, quarantine and investigate its
source independently of candidate performance. Never repair historical artifacts.

For the content-controlled language diagnosis, independently label both views
and inspect alignment. A changed claim or disagreeing label remains visible in
the audit; it does not enter the agreed aligned-step primary contrast. All such
exclusions and problems without both classes remain in coverage reports.

## Provenance record and release boundary

The metadata audit expects `problem_id`, `family_id`, `source_lineage_id`, `split`,
`origin`, `source_language`, `reasoning_origin`, `label_origin`, `training_overlap`,
`independent_review_complete`, plus SHA256 evidence references for source,
permission, reference check, annotations, Arabic mathematics qualifications,
contamination audit and normalized problem. These **declarations are not verified
human facts** merely because the validator accepts their syntax.

Private evidence must substantiate each assertion. A public report can disclose
only aggregate origin/split/domain counts, source permissions, annotation workload,
agreement and exclusions, with consent. Do not publish identities, copyrighted
problem text or unapproved data. Acquisition, annotation, new inference, training
and release each depend on actual scope and permission; no active allowance,
qualified-human endorsement or training eligibility is produced here.
