# Offline native-study analysis tools

`research/prm_arabic_english/native_study_v1.py` is standard-library-only. It
reads an explicitly supplied JSON file and prints **aggregate analysis** plus
the input SHA256. It imports no historical model evaluator, contacts no service,
and writes no dataset, review record, approval, ledger or training artifact.
Use it on private recorded evidence once available; the tests use only disposable
synthetic metadata/scores. No synthetic test result is project performance.

```text
python -B research/prm_arabic_english/native_study_v1.py benchmark --input PRIVATE_METADATA.json
python -B research/prm_arabic_english/native_study_v1.py gap --input PRIVATE_PAIRED_SCORES.json
python -B research/prm_arabic_english/native_study_v1.py rerank --input PRIVATE_FIXED_POOLS.json
python -B research/prm_arabic_english/native_study_v1.py sample-size
```

The first three require authentic supplied evidence; no such native study inputs
exist yet. Keep private files outside the public checkout. These commands are
optional analysis interfaces, not laptop setup steps or inference launchers.

The separate retained-evidence auditor also reads the checked-in
`model_utils/io_utils.py` source, without importing it, and validates a rounded
blank-line aggregation sensitivity against the raw AST response literals. The
offline CI sparse checkout includes only that utility source directory in
addition to existing research code, with no model weights. Its static runtime
declarations are not authenticated historical run settings.

## Benchmark metadata

Input is a list of problem-group dictionaries with the fields in the
[benchmark specification](ARABIC_NATIVE_BENCHMARK_V1.md). One row means one
Arabic-side canonical problem, not a step/candidate/English mirror. Origins are
`arabic_native` or `translated` (the current translated controls are English-origin);
other origins stay unresolved outside the enrolled frame. The audit checks all
train/dev/test splits, native ≥50%, translated ≤30%, unique IDs/content hashes,
family/lineage separation, source language, originally Arabic reasoning, qualified
human-label declarations and required evidence hashes. It returns declarations
consistent **without** authenticating provenance, assigning human approvals or
granting training/export eligibility. Semantic near-duplicate review remains human.

## Paired language diagnosis

Input header `kind: paired_language_scores_v1` includes
`benchmark_manifest_sha256`, `annotation_manifest_sha256`, `scorer_fingerprint`,
`planned_observation_ids` and `rows`. Hash strings are lowercase SHA256.
Every planned observation must be present exactly once. Each row contains:

- `observation_id`, `problem_id`, `family_id`, `candidate_id`, `step_id`;
- Boolean `alignment_verified`;
- independent `ar_label`, `en_label`: `correct`, `incorrect`, `neutral`, `uncertain`;
- `ar_status`, `en_status`: `scored`, `missing`, `truncated`, `alignment_failure`,
  `transport_failure`; and respective `ar_score`, `en_score`.

Scores are numeric probabilities in [0,1] when scored, otherwise null. No
replacement scores, nonfinite values, duplicate candidate steps or incomplete
rosters are accepted. Missing, unaligned, disagreeing, neutral and uncertain rows
remain in total counts, with explicitly nonexclusive exclusion counts.

For agreed scored positive/negative steps, compute each problem's AR/EN
correct-minus-incorrect mean gap, then the equal-problem EN–AR contrast. Problems
without both classes remain in coverage. Confusion/balanced accuracy at the
**descriptive fixed threshold .5** and equal-problem Brier cover all agreed
supervised steps, including one-class problems. Report paired AR-minus-EN Brier
and gap contrasts with seeded 5,000-draw bootstrap intervals that resample whole
source families. With one family the interval is null. The point estimate is
equal-problem, not a step-pooled or equal-family estimate. This does not remove
selection bias, establish native provenance or authenticate supplied labels.

## Recorded fixed-pool reranking

Input header `kind: recorded_candidate_reranking_v1` includes benchmark and
annotation hashes, `evaluation_split: test`, `scorer_fingerprints` mapping names
to immutable identities, `base_scorer`, `planned_problem_ids`,
`candidate_pool_sha256`, and `problems`. Each problem has `problem_id`, `family_id`,
`origin`, `language: ar`, and eight `candidates` in original generation order.
Each candidate has `candidate_id`, `generation_status` (`generated`/`failed`),
`text_sha256`, `answer_key`, `outcome` and `scores` mapping **all** declared scorers
to probabilities or explicit nulls. No solution text is required in this input.

`answer_key` is an already human-checked canonical answer representation, or null
for abstention; the tool does not solve algebraic equivalence. `outcome` is an
actual supplied human Boolean or null for unresolved. A failed generation must
have null text/answer/scores and false final outcome: failure to produce a solution
counts against operational accuracy. Generated-but-unreviewed text remains an
unknown outcome, not an automatic failure or success.

`pool_identity(problems)` canonically hashes problem/family/origin/language and
ordered candidate ID/status/text hashes, independent of scores and labels. The
reader checks it against the supplied manifest identity. Fix this manifest before
scoring: recomputing both identity and input after alteration cannot establish
honesty. The full input SHA256 also binds recorded labels/scores for analysis.

The tool replays prefixes K=1,2,4,8 with earliest-position reward/vote ties,
first-position fallback for a scorer with any missing generated-candidate reward,
and failed-generation reward minus infinity. It reports first-candidate, exact
uniform-random expectation, answer majority, every declared PRM and oracle;
all/native/translated strata; failure/fallback counts; all-problem outcome bounds;
and base-minus-first / other-scorer-minus-base paired comparisons. Unknown selected
outcomes withhold the primary point comparison. Exact McNemar is suppressed when
problems share source families; family bootstrap handles complete paired outcomes.
The primary endpoint is Arabic-native base-versus-first accuracy at K=8.

This replay cannot prove candidate provenance, reviewer qualifications, scorer
identity truth or test-set independence. It cannot recover missing observations
not disclosed in a purported roster. Inspect underlying evidence independently.
English pools can be analyzed under a separately documented analogous replay;
this initial CLI deliberately reports the primary Arabic pools only.

## Planning and tests

The sample-size command prints hypothetical independent-pair requirements of
236 (10-point gain) and 942 (5-point gain), assuming discordance .30, alpha .05,
80% power; it is not a power simulation or realized evidence. Clustering and
missing outcomes increase requirements. There is no collection or allocation mode.

Run `python -B scripts/check_reproducibility.py` for the explicit offline suite.
Do not discover/import arbitrary legacy `test_*prm.py` modules: several load
models at import time. New regressions check provenance axes, quotas, leakage,
coverage, masks, calibration, whole-family resampling, pool tampering, tied scores,
transport/generation failures, unresolved human outcomes and paired inference.

## v3.1 additions

`benchmark --evaluation-only --input FILE.json` explicitly audits dev/test metadata
without a training split; default behavior still requires train/dev/test. Origin,
human-label and provenance requirements are identical. Unknown human judgments
remain unknown. The reranking reader rejects conflicting known final outcomes for
one canonical answer; it cannot adjudicate them. Selection diagnostics distinguish
known oracle absence from avoidable selection errors, retaining all problems in
primary accuracy and bounds. Conditional selection efficiency is secondary.

The [v3.1 feasibility planner](BENCHMARK_FEASIBILITY_V3_1.md) compares costs and exact
independent-pair power. No planning result authenticates people or activates runs.

The [v3.1 scoring analyzer](SCORING_DIAGNOSIS_V3_1.md) adds exact-input/offset and
matched precision/adaptation checks for supplied records only. The [operational
plan](RERANKING_OPERATIONS_V3_1.md) defines what selectors may see. The primary
selection hash excludes canonical voting; its separate hash may depend on human
answer equivalence work. The pure selector works before an annotation file exists.
Do not invent an annotation hash or human label to call the later full replay.
The answer-majority comparator is expert-assisted unless keys come from a pinned
reference-blind parser. No such automated parser is claimed here.
