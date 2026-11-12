# v3.1: benchmark feasibility and collection plan

**Decision:** the collection design is prepared; actual feasibility is unverified
until qualified people time the work and commit capacity. No source items or new
human labels have been collected. No model run or budget is authorized. The
[reproducible planning table](BENCHMARK_FEASIBILITY_V3_1.json) contains assumptions,
not measured effort or experiment results.

## Scope that saves work without weakening Arabic requirements

Prefer a **100% Arabic-native core** with a 20% development / 80% locked-test
split. Do not reserve a training split before the diagnosis. The earlier v3
500-problem, 80/20-origin, train/dev/test plan remains a historical proposal;
this is an explicit prospective revision, not a change to frozen experiments.

Zero translated Arabic problems satisfies the supervisor's ≥50% native and ≤30%
translated limits. Compare an optional 80% native / 20% translated alternative
below, but do not require translated controls at the cost of native test power.
English mirrors of native Arabic problems are comparison views of those same
source groups, not new translated-Arabic benchmark items or extra independent n.
Previously retained translated/handcrafted examples remain a separate development
mechanism check, with no native-benchmark eligibility inferred.

Keep K=8 Arabic candidate positions and **two fixed Arabic traces per problem**
(positions 1 and 2) for independent step annotation. All eight final answers get
two independent mathematical assessments. All step labels are newly assigned by
qualified Arabic-speaking humans; none is inherited from English. Two assessors
and an independent third adjudicator remain required at every size. Compared
with v3's four-trace/full-bilingual proposal, fewer prespecified traces reduce
step-class coverage; report it, never replace missing classes with invented errors.

For content-controlled scoring diagnosis, prepare English mirrors and independent
English labels for those same two traces on up to 20 native dev and 60 native
test problems. Select whole source families before labels or scores; cap/target
changes caused by families must be recorded before outcomes. The table assumes
one problem per family for its exact counts. Do not claim the bilingual subset
is the whole benchmark. Independently generated English pools are a separately
costed extension, not required for the core Arabic solving endpoint.

## Size comparison

Exact paired-test power below assumes independent native problems, a true 10-point
accuracy gain, discordance q=.30, and two-sided exact McNemar alpha .05. It is not
power of a completed study. Hours include all roles, original native authoring,
two human assessments, English mirror work, assumed adjudication and 15% reserve.

| Total problems | Dev/test | Native test, 100% native core | Exact power for +10 points | Assumed person-hours, native core | Appropriate role |
|---|---|---:|---:|---:|---|
| 100 | 20 / 80 | 80 | 29.5% | 172–436 | Feasibility and rubric/work-rate pilot; no broad efficacy conclusion |
| 250 | 50 / 200 | 200 | 70.3% | 354–916 | Bounded exploratory evaluation; underpowered for the stated 80% target |
| 500 | 100 / 400 | 400 | 95.1% | 655–1,715 | Candidate confirmatory scope only with real staffing and family/power review |

At 80/20 native/translated origin, native test n becomes 64/160/320 and exact
10-point power becomes 23.6%/59.6%/89.5%, for about 167–423 / 347–897 / 642–1,676
assumed person-hours. Translation controls save little work and reduce the primary
native denominator. A native-only core therefore has the better initial tradeoff.

For a **5-point** gain, even the native-only 500-problem option has about 41.2%
independent-pair power. With hypothetical 10% unresolved outcomes and design
effect 1.2, the native-only 500 option has heuristic effective n=300 and about
87.4% power for +10 points. This reduced-n calculation is **not exact clustered
power**. Actual source-family structure and disagreement/availability rates are
unknown; do not translate these numbers into a guarantee or a population claim.
Exact finite-sample power also differs from the old normal planning approximation
(236 pairs for +10 points); retain the distinction rather than claiming exact
80% power from that approximation.

## Collection routes, provenance and permissions

1. **Preferred: commissioned original Arabic problems.** Recruit actual Arabic
   mathematics educators across the five v3 domains. Keep original Arabic drafts,
   author/source evidence, creation history, source-family/template IDs and
   written permission for the intended research use. Ask about prior publication
   or adaptation of another-language problem. An Arabic rewrite of an English
   source remains derived/translated, not native. No author is recruited here.
2. **Alternative: evidenced original Arabic educational sources.** Record the
   exact edition/page/item, original-language evidence and applicable permission
   or licence before enrollment. Public availability and Arabic script alone do
   not establish permission or original authorship. Permission to inspect/store,
   translate for private comparison, publish benchmark text and release labels
   are separate scopes. Unresolved permission means do not enroll or redistribute.
   This is an operational evidence requirement, not a legal ruling.
3. **Optional translated controls.** Use only permission-cleared English sources,
   record the derivation and independently review the Arabic question. Generate
   any future Arabic reasoning originally in Arabic and assign fresh human labels.
   These controls may not displace the required native fraction in either split.

Screen origin, rights, exact/near duplicates and source families before locking
items. At an assumed 80% eligibility rate, screen 125/313/625 candidates for the
three target sizes. Reference validity is independently checked twice. Ambiguous,
incorrect or insufficiently sourced questions remain quarantined with reasons;
do not repair frozen historical sources or select exclusions after PRM results.
The estimates do not include calendar delay for permissions, recruitment or
institutional arrangements. Mathematical-reference rejections may add effort.

Split whole canonical problem lineages/template families before generation.
Keep English mirrors, candidate variants and derivations together. Stratify the
five domains and difficulty/source mix, freeze the manifest and split seed, and
audit against retained training/evaluation identities. Shared authors/books can
create additional clustering beyond template IDs; report it. Exact hashes and
new authorship cannot prove absence from model pretraining. Test stays sealed
from anyone tuning score aggregation, thresholds or prompts.

## Workload assumptions and staffing

The planner assumes eight steps/trace, two Arabic traces/problem, two assessors,
and the limited native English-mirror subset above. Default native authoring is
100% newly commissioned, 15–40 minutes per screened native candidate. Reuse can
be explored by changing `native_authoring_fraction` after actual source evidence;
this removes authoring time, not independent human annotation or permissions.

Other **unmeasured** ranges: source screening 3–8 minutes/candidate; reference
checking 5–12 minutes/check; step assessment .5–1 minute; final answer .75–2
minutes; English problem mirror 4–8 minutes; trace mirror 3–6 minutes; independent
mirror fidelity check 2–4 minutes. Adjudication assumes 10–25% of underlying
units need 1–3 minutes each. The fraction applies to units, not twice-counted
assessor judgments. Complex disagreements can take longer than these ranges.

The 100-native option already entails 3,200 Arabic step judgments, 2,560 English
mirror step judgments and 1,600 Arabic final-outcome judgments. Person-hours sum
across original authors, reference checkers, two independent Arabic assessors,
English mirror authors/assessors, and the third adjudicator. They are not elapsed
weeks and cannot be divided by nominal staff count without actual availability.
Native-speaker status alone does not demonstrate mathematical qualification.

**Practical staging:** time a small dev-only source/rubric calibration before
committing a full size. Use real qualified people and record actual work time,
eligibility, disagreements and step lengths. Existing texts can be practice
material without being promoted to native benchmark data. Do not expose locked
test outcomes while revising sample size. If only a feasibility-size study can be
staffed, explicitly narrow thesis claims; do not replace humans with inherited
English labels, AI labels, single-person review or extra responses per problem.

## Reproduce without a model

`benchmark_feasibility_v3_1.py` prints the table, all per-task quantities/ranges,
future generation positions and separate scoring-record counts. The core has
800/2,000/4,000 prospective Arabic generation positions, **zero authorized now**;
no independently generated English positions are included. Human English mirrors
are not model generations. Batch size does not turn scoring records into HTTP
generation requests or an approved budget.

The exact-power implementation sums `P(D=d) P(reject | d)` with
`D~Bin(n,q)` and `wins|D~Bin(D,(q+gain)/(2q))`. Tests compare exhaustive small
joint-outcome enumeration, closed-form edge cases, binomial probabilities and
null rejection rates. The published JSON is regenerated exactly in CI. Custom
assumptions are explicit JSON; they cannot remove two-person review, violate the
native/translated limits, or silently round origin/split quotas.

The metadata auditor now has an explicit `--evaluation-only` mode for dev/test
frames. Default v3 train/dev/test behavior is unchanged; provenance, permissions,
human-label declarations and leakage checks remain mandatory. Metadata acceptance
does not authenticate humans or approve a benchmark. Actual collection, scoring,
generation, training and release remain outside this offline implementation.
