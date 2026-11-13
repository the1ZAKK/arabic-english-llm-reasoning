# v3.2 feasibility finding and next scientific decision

**Historical v3.2 counts below:** the [v3.3 source-collection continuation](ARABIC_NATIVE_COLLECTION_V3_3.md)
expands the reused source register to eight leads and records a five-domain
shortlist. Actual question, trace and human-review counts remain zero.

**Decision: materials ready for human collection; actual feasibility unproven.**
The [twenty-slot plan](ARABIC_NATIVE_PILOT_V3_2.md) is development-only, four per
domain, with two introductory and two intermediate slots in each. Its target is
100% Arabic-native. No inference, model scoring, training or budget activation
has occurred in this milestone. Human source-worked/authored traces can support
an initial no-model annotation exercise; they cannot demonstrate a PRM solving gain.

## Evidence ledger

| Quantity | Actually available | Target / missing evidence |
|---|---:|---|
| Screened book/course leads | 4 | Three unresolved/item-review leads; one explicitly English-derived exclusion |
| Entered candidate problem records | 0 | 20 distinct, originally Arabic problems with actual source locators and reference answers |
| Item-level rights-cleared, source-ready problems | 0 | 20; book-level notices do not authorize unspecified items or all uses |
| Recorded item-screening decisions | 0 | Retain every proposed/rejected/pending candidate, not just eventual successes |
| Registered original-Arabic traces | 0 | 40, two distinct source/human traces per problem; authors separate from A/B/C |
| Assigned qualified assessors / adjudicator | 0 / 0 | Two independent Arabic-speaking mathematics assessors and a third adjudicator |
| Actual human judgments / timing sessions | 0 / 0 | Real independent records, evidence and observed work rates |
| Native pilot problems human-validated | 0 | Software preparation and documentary AI screening do not constitute validation |

The [source register](native_pilot_v3_2/source_register.json) contains actual
library/publisher/university pointers and limited observations. Historical
al-Khwarizmi material has documentary support at book level, but is not a
representative modern-Arabic sample or twenty approved items. KSU title/host
metadata does not establish native authorship; private-use permissions remain
unresolved. Hindawi's explicitly English-origin translation is excluded. Modern
original educational material, especially geometry/applied problems, remains a
collection gap. Do not fill it with translations or historical-only coverage.

No source holder or reviewer was contacted. Necessary next inputs are actual
item evidence/rights and real people, not another software authorization form.
The preferred fallback is commissioned original Arabic material from actual
mathematics educators with documented derivation history and intended-use rights.
Nothing in this report asserts permission or commits an author's/reviewer's time.

## Pilot workload and acceptance

Use the [Arabic/English instructions and worksheets](native_pilot_v3_2/HUMAN_ANNOTATION.md).
The forty traces have an **unknown** actual step count S. Two independent reviews
require 40 problem/reference decisions, **2S** step judgments and 80 final-answer
judgments, plus actual adjudication. For orientation only, eight steps/trace would
give S=320 and 640 step judgments; this is an assumption, not a measurement. Source
screening, rights work, any authorship/transcription and independent reference
verification are additional work and may dominate calendar feasibility.

An acceptable completed annotation pilot needs twenty valid native problems,
matching domain/difficulty targets and clear intended private-use rights; twenty
distinct canonical lineages, preferably twenty families and at most two items per
template family; original Arabic trace evidence; and A/B problem, reference,
every-step and final judgments. C resolves actual disagreements independently.
Uncertainty, mathematical defects, missing permissions and absent reviewers remain
visible. Validity and native provenance must be verified by humans against actual
evidence, not a hash-shaped placeholder. Correct-only material cannot establish
negative-step coverage. Neutral/uncertain judgments are never automatically positive.

Pilot families are permanently development-exposed and excluded from future locked
test, including mirrors, paraphrases and number substitutions. Record book/author,
register and template clustering. Hash checks do not establish absence from model
pretraining. No source text, populated private worksheet or unapproved corpus is
exported by this milestone. Broader publication/training/translation rights are
separate from private pilot use.

## Decide whether 100, 250 or 500 is realistic

Reuse the [v3.1 workload/power planner](BENCHMARK_FEASIBILITY_V3_1.md), rather than
creating a second cost model. Its native-only options remain **assumed**, not funded
or measured. They include K=8 eventual model candidates, two independently labeled
Arabic traces and limited English-mirror diagnosis; the present human pilot has
neither that model pool nor English mirrors.

| Native-core size | Existing assumed person-hours | Existing independent-pair power for +10 percentage points | Decision implication |
|---|---:|---:|---|
| 100 | 172–436 | 29.5% with 80 native test problems | Practical next collection stage if people and rights support it; limited efficacy evidence |
| 250 | 354–916 | 70.3% with 200 native test problems | Exploratory option; below the stated 80% power target |
| 500 | 655–1,715 | 95.1% with 400 native test problems | Only a candidate confirmatory scope; requires demonstrated staffing and family/power review |

Those powers assume discordance .30, independent problems, exact two-sided McNemar
alpha .05 and a true ten-point gain. They do not apply to the twenty-problem human
pilot; clustering, missing outcomes or a smaller gain weaken the case. The earlier
retained experiments do not supply observed native-benchmark discordance or gains.

Conduct the work in this order:

1. A coordinator obtains item-specific origin/permission evidence and records all
   screening outcomes privately. Confirm coverage of all five domains and a modern
   register; historical items must be explicitly stratified and limited by actual
   study purpose. If rights/native evidence cannot be obtained, report failure of
   that route rather than quietly enrolling uncertain material.
2. Recruit and verify actual A/B/C qualifications, independence and weekly person-hour
   availability; arrange distinct trace authors where needed. Confirm institutional
   requirements and intended-use rights with the responsible project people.
3. Use a small development calibration to clarify the rubric, retaining its original
   judgments. Version any changes before the remaining independent pilot assessments;
   never present calibration agreement as blinded test reliability.
4. Complete the twenty source-valid problems and forty original-Arabic traces without
   model generation. Obtain isolated A/B records, then C adjudication. Retain invalid,
   uncertain, absent and correct-only observations. Report raw agreement by unit
   type before adjudication and error-class coverage with denominators; do not treat
   multiple steps as independent problems or pool away source/register differences.
5. Measure all contributor time, rejection/permission yield, trace lengths, unresolved
   units and calendar delay. Do not infer total eligibility from selected successes.
   The timing tool supplies descriptive weighted rates only; no credible precision
   interval or guaranteed scaling follows from twenty purposively selected problems.
6. Replace relevant v3.1 assumptions in an explicit private planning copy after human
   review. Keep unmeasured English mirror/K=8 work as separate assumptions, add
   actual permission/recruitment delay and verify person-hours against actual staff
   availability. Compare conservative scenarios, not only average fast sessions.
7. Choose the smallest defensible scope that resources support, then freeze fresh
   source-family-separated dev/test plans and claims. If 500 cannot be staffed,
   narrow the thesis conclusions; do not weaken native provenance or human labels.
   Any model observation/scoring experiment requires separate authorization later.

The scientifically useful next activity is **real native-item collection and timed
independent Arabic review**. Software is ready to record that evidence. Native
performance-gap diagnosis and fixed-candidate PRM solving efficacy remain subsequent
studies with their existing controlled protocols; this preparation produces no new
performance results.

## Reproducibility and software limits

The collection checker reuses v3 source/hash primitives and the existing benchmark
auditor's explicit dev-only mode; its default full-benchmark requirements remain
intact. The review checker separates problem validity/origin/reference, local step
validity, global consistency, prior-error propagation and final-answer correctness.
It checks exact evidence identities, separate people, original records/adjudication,
missingness, first-error consistency and actual timing arithmetic. It never reads
private evidence files or authenticates identities, rights or human work.
Reports bind each parsed input worksheet by canonical digest; an unchanged count
does not imply unchanged original records. Keep populated reports private and
share only deliberately sanitized aggregate findings.

The public [collection status](native_pilot_v3_2/collection_status.json) and
[review status](native_pilot_v3_2/review_status.json) replay exactly in offline tests.
No future human decision, timestamp, annotation or cost observation is prefilled.
Frozen execution/source identities, pilot history and human-QC records are outside
the changed paths. Cross-platform CI establishes these software contracts only.
