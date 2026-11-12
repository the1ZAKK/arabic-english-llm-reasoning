# ArabicPRM-T v3.1 scientific progress

**Milestone:** benchmark feasibility and performance-gap diagnosis, offline only.
The technical plans and analyzers are prepared. A staffed benchmark, independent
human labels, new scoring observations and downstream efficacy evidence are not.

- [Collection feasibility](BENCHMARK_FEASIBILITY_V3_1.md) now compares 100, 250 and
  500 problems, each at 100% native or 80/20 native/translated origin. A native-only
  dev/test core preserves more native test information for similar effort and
  satisfies the supervisor's origin requirements. No training split is reserved.
- Human effort is explicit: preferred newly authored native material, permissions
  screening, independent reference checks, two qualified assessors of two fixed
  Arabic traces/problem and all eight final answers, limited bilingual mirrors,
  adjudication and reserve. Under **unmeasured** rates, native-only options need
  roughly 172–436, 354–916 and 655–1,715 combined person-hours. No staff are assigned.
- Exact independent-pair power for a ten-point selection gain, q=.30 and alpha .05
  is approximately 30%, 70% and 95% at 80/200/400 native test problems. At five
  points even the largest option is about 41%. Clustering/missingness reduce
  information; the effective-n scenario is only a heuristic. The smallest option
  is a feasibility pilot, not evidence supporting broad efficacy claims.
- The [retained-score replay](PERFORMANCE_GAP_DIAGNOSIS_V3_1.json) preserves the old
  results and sources. After blank-reward exclusion, nominal EN–AR gap difference
  is 0.227700, with rounding-only bounds [0.227500, 0.227900]. The correct-category
  ranking is robust to that recording precision: Arabic 13/20 versus English
  20/20. This rules out a narrow rounding-only explanation, not label error,
  content mismatch, source bias or all causes of language weakness.
- The [controlled scoring procedure](SCORING_DIAGNOSIS_V3_1.md) separates same-score
  aggregation sensitivity from new input rendering, matched-NF4 adaptation from
  quantization, and lexical reward anchors from qualified mathematical-step maps.
  The analyzer requires complete planned cells, exact input identities, proper
  Unicode offsets and compatible runtime declarations. Optional four-cell
  interactions use the same complete items. It has no scoring execution path.
- The [operational reranking plan](RERANKING_OPERATIONS_V3_1.md) fixes Arabic K=8
  pools, first/PRM choices before outcome review, and a deterministic aggregation
  rule that does not read human correctness or neutral labels. It separates
  automated selection hashes from human-assisted answer voting, rejects
  contradictory canonical-answer outcomes, and distinguishes missing correct
  solutions from avoidable selector failures. Unknown judgments remain unknown.

**Verification:** feasibility milestone
[`90a8208`](https://github.com/the1ZAKK/arabic-english-llm-reasoning/commit/90a820860dbdc513350eb168a1ff92efdd77bde5)
passed **573 tests on Windows and Linux** in
[CI 43218101318](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/43218101318),
including native guards. The scoring continuation has its own full offline suite
and per-commit [Actions evidence](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions?query=branch%3Aresearch%2Farabicprm-v2-production).
All **590 local offline tests** passed (63.608 s); a cross-platform claim additionally
requires both matrix jobs for the exact published continuation commit.
Software consistency, synthetic tests and bootstrap arithmetic are not semantic
validation, human approval or an executed experiment.

**Recommended next step:** verify qualified staffing and time a small dev-only
collection/rubric calibration; choose a defensible size and scoped claims using
actual capacity. Obtain real source/permission evidence and human annotations.
Any subsequent model scoring/generation needs separate explicit authorization;
no existing allowance can be reused. Diagnose before further fine-tuning.

No new model outputs, training, active budget, unapproved dataset export or human
approval was created. Frozen sources, original scores/checkpoints, historical
attempts, genuine QC, protected execution identities and `main` remain untouched.
