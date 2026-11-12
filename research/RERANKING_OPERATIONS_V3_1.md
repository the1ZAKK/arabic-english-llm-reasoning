# v3.1: operational fixed-candidate solving evaluation

This makes the [v3 study](ARABIC_NATIVE_STUDY_V3.md) operational under the
[v3.1 resource plan](BENCHMARK_FEASIBILITY_V3_1.md). It prepares a future evaluation;
no candidates, human outcomes, scores or inference authorization are created.

## Fixed data flow

1. Enroll provenance/permission-cleared Arabic-native problems with independently
   checked references. Split whole lineages/families into dev/test and keep test
   inaccessible to tuning. Prefer a native-only core; any translated controls are
   separate strata within the origin limits. Reserve no new training split now.
2. After a separate actual authorization, produce exactly K=8 Arabic candidate
   positions/problem with one pinned generator/prompt/decoding configuration.
   Require observable reasoning originally in Arabic; do not generate English
   traces and translate them. Preserve raw outputs, source hashes, order and
   failures. Do not replace unsolved, mixed-language or inconvenient candidates.
   A generation failure remains an unsolved position. No such run occurs here.
3. Freeze the private pool manifest before PRM scoring and before final-answer
   review. All scorers receive identical candidate IDs/bytes and input policies.
   The core scorer is the frozen base PRM; the existing adaptation bundle is an
   optional secondary scorer at exactly matched NF4 settings. A future newly
   trained scorer requires separate training authorization, not this protocol.
4. Apply frozen selectors and record chosen IDs privately before joining human
   outcome labels. The pure `selector_positions` function reads only order,
   rewards and optional answer keys. It can run before an annotation file exists;
   do not invent an annotation hash to invoke the later full report. The report
   binds **first/PRM** choices by `selection_manifest_sha256` for each K. This hash
   is independent of human outcomes and answer keys. Canonical-vote choices have
   a separate hash because humans may supply those keys later. Neither hash proves
   when an operator froze decisions. Retain an actual dated private record.
5. Two qualified Arabic-speaking mathematics assessors independently judge every
   final answer against the checked reference, blind to PRM scores and selector
   identity. Randomize/hide original positions in review to avoid revealing the
   first-candidate baseline. Adjudicate disagreements independently and preserve
   originals/unresolved cases. No assessor identity or judgment is supplied here.
6. Join sealed outcomes and frozen selections using exact pool/scorer/manifest
   identities. Report all planned problems, including failures and missingness.
   The primary endpoint is native held-out final-answer accuracy, not PRM margins.

## Selectors and no label leakage

Primary: **base PRM versus first sampled candidate at K=8**. The first candidate
is not greedy decoding. Primary PRM aggregation is the mean of the deterministic
**nonempty newline reward positions**, with the versioned input/offset checks in
[the diagnosis procedure](SCORING_DIAGNOSIS_V3_1.md). Freeze that rule before test;
human correctness/neutral labels, reference answers and semantic-step maps are not
fed to the primary selector. New generation instructions can request one step per
line, but that does not prove human mathematical alignment. Report parser and
alignment limitations rather than silently removing difficult candidates.

Human-labeled mathematical steps on the two fixed traces/problem support scoring
diagnosis and class/mask metrics. Their neutral/uncertain labels remain excluded
from supervised quality metrics. A score aggregated using expert-only semantic
boundaries is a separate expert-assisted diagnostic, with additional annotation
cost; do not call it the automated operational selector.

Secondary: exact uniform-random expectation from the same pool, nested K=1/2/4/8
prefixes, existing-adaptation-versus-base, and oracle availability. Minimum-step
aggregation or alternative parsing can be explored on dev only and require a
separately fixed test comparison; do not select the most favorable test rule.

The current `answer_majority` uses supplied canonical answer keys. If humans
created those keys, label it an **expert-assisted answer-vote comparator**, not
an automatic deployable baseline. An automated-vote claim requires a pinned,
reference-blind answer extractor/canonicalizer frozen on dev, with its failures
reported. No such parser or efficacy claim is created in this milestone.
Canonical keys must include relevant units, sets and mathematical equivalences.
One key cannot have conflicting known final-answer outcomes within a problem;
the reader now rejects that case for human adjudication. Unknown outcomes remain
unknown even when another equivalent-key candidate has a known judgment.

Reward ties and answer-vote ties use original generation order, never correctness.
Missing reward for a generated candidate triggers the prespecified first-position
fallback for that scorer/problem. Failed generations have unavailable reward and
remain in the K denominator. Do not use human outcome labels to repair rewards,
rerank ties, replace a candidate or select which traces receive step annotation.

## Diagnosis versus solving results

Report native test n, family counts, exact source composition, complete/unknown
outcomes, failures and score fallbacks. Show per-selector accuracy with the same
problem denominator, absolute paired change, source-family bootstrap 95% interval
and wins/losses. Exact McNemar is used only under the declared independent-family
conditions. Unknown selected outcomes withhold the primary point comparison;
all-problem lower/upper bounds remain visible. Conditional success rates must not
silently exclude problems with no correct candidate from primary accuracy.

Also report **oracle availability versus avoidable selection loss**. Low oracle
means the pool lacks correct solutions; a better reward model cannot select what
is absent. Available correct solutions with wrong selections are a PRM/selector
failure. The offline replay now computes both, with conservative bounds for
unknowns. Selection success conditional on known oracle availability is secondary,
not the solver's overall accuracy. A correct final answer with invalid reasoning
still counts for the stated final-answer endpoint; report process validity on the
annotated subset separately. Never inherit it from the final answer or a PRM score.

All thresholds, secondary endpoints and size decisions are fixed before unlocking
test. Class coverage may be sparse with only two annotated traces; retain that
limitation. The limited English mirrors diagnose aligned scoring, while the full
Arabic pool supports solving evaluation. Claims about original-language generator
differences need independently generated English pools and their own authorization
and workload; they cannot be inferred from those mirrors.

## Private artifacts and review products

Keep the enrolled source/reference and permission evidence, split/family manifest,
original pool and availability manifest, tokenizer/weight/head/environment hashes,
scoring/offset records, frozen selections, independent raw human assessments,
adjudication and analysis inputs distinct and immutable. Reuse existing sealed
assessment practices where appropriate; no new reviewer interface is needed.
Private identities and copyrighted problem/solution text stay private. Public
outputs can be aggregate counts, uncertainty, source/role descriptions with
permission, analysis-code commits and nonidentifying artifact hashes.

The existing recorded-pool JSON contract and offline CLI are documented in
[NATIVE_STUDY_TOOLS_V1.md](NATIVE_STUDY_TOOLS_V1.md). These tools validate and replay
supplied records; they do not produce candidate solutions, approve human labels,
authenticate identity, schedule execution, activate budgets, train or export data.
At this milestone the actual native pool, independent annotations and downstream
performance outcomes remain missing.
