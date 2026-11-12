# Arabic-native PRM study: diagnosis and downstream evaluation

**Prospective v3.1 revision:** see the [costed native-only/dev-test plan](BENCHMARK_FEASIBILITY_V3_1.md). The original size/split/mirror targets below are retained as the earlier proposal; no protected execution identity is changed.

**Status: prospective scientific design, not an executed experiment.** This
replaces the translation-first priorities of the earlier protocol. The
[retained-evidence audit](RETAINED_EVIDENCE_AUDIT_V3.md) reproduces the historical
results and their limitations. There is no new native benchmark, human annotation,
diagnostic inference, fine-tuning or downstream result in this revision.

## Questions and falsifiable explanations

The thesis question is whether a process reward model can select better
mathematical solutions **originally reasoned in Arabic**. The existing selected
twenty-problem score gap motivates investigation; it does not explain its cause.

| Competing explanation | Controlled comparison / evidence to collect | What would weaken that explanation? |
|---|---|---|
| Arabic candidates contain more actual reasoning errors | Independent AR/EN generations on matched problems; human final outcomes, first errors and oracle@8 | Similar candidate/oracle quality but worse Arabic reward selection |
| PRM scoring is less reliable on Arabic content | Score the same human-aligned reasoning content in Arabic-original and English mirror form with the frozen base PRM | Gap disappears on aligned content, while independently generated pools still differ |
| Reward-token, newline or step segmentation is wrong | Inspect token offsets, reward positions, count alignment and the same mathematical step boundaries; record missing reward outputs | Validated alignment with unchanged gap; parser fixes alone do not help |
| Tokenization/length truncates Arabic disproportionately | Record actual token counts, maximum context, truncation and last scored step; compare untruncated length-matched strata | Similar completeness/length with persistent errors |
| A score calibration shift is mistaken for poor discrimination | Compare raw ranking/AUROC, balanced accuracy, Brier and dev-only calibration; transfer the frozen dev rule to test | Worse within-problem ordering after calibration, not just lower mean scores |
| Terminology, numerals or logical relations are specific weaknesses | Human error categories and dev-only, content-preserving numeral/notation probes with aligned labels | Errors are not concentrated in those categories; probes leave scores unchanged |
| Translated/handcrafted data caused the apparent gap | Separate proven Arabic-native problems from translated controls and synthetic pilot examples | Discrepancy persists on native, human-labeled held-out problems |

These are hypotheses. CI and existing margins do not select a winning explanation.
Several causes may coexist. A source reasoning error, translation change, scoring
alignment failure and generator mistake must remain separate observations.

One diagnosis is possible from existing scores: the nominal correct category is
uniquely highest on 12/20 Arabic base problems versus 20/20 English, and 16/20
Arabic after adaptation. A strictly monotonic recalibration cannot fix ordering
in that selected set. Unverified tags, bilingual equivalence and alignment remain
confounds; this is not a real generated-pool solving result.

The [pipeline audit](RETAINED_EVIDENCE_AUDIT_V3.md#scoring-pipeline-and-precision-audit)
also identifies empty-line rewards (160 per language) and different declared
quantization configurations in old base/adapted runners. Excluding empty positions
from rounded recorded scores leaves a base EN–AR gap difference about 0.2277,
so that measurement issue does not explain the full discrepancy. A future
unadapted-base control at the adapter's exact quantization/extraction settings
is needed before attributing changes to adaptation. No old output is rewritten.

## Two complementary comparisons

**Content-controlled scoring diagnosis.** Use Arabic-original traces from the
new benchmark, selected by fixed candidate positions 1–4 before labels/scores.
Qualified bilingual mathematics reviewers make English mirrors preserving every
reasoning step and intentional error. Independently assign Arabic and English
step labels; align steps explicitly. Keep disagreements, neutral/uncertain labels,
truncation and missing scores visible. Do not inherit English labels or force
agreement to manufacture aligned supervision. English mirrors are comparison
views of the same source group, not additional native benchmark problems.

Use the frozen base PRM and identical mathematical boundaries/reward extraction.
Report per-problem correct-minus-incorrect gaps, the EN–AR paired difference,
class coverage, fixed-threshold confusion, Brier, and source-family bootstrap
intervals. Problems without both classes stay in the coverage denominator; their
Brier scores can still contribute. AUROC, first-error localization and calibrated
metrics are planned extensions requiring actual aligned observations; the new
offline tool does not claim to implement those extensions. Estimate calibration
only on dev. Report annotation disagreement and fidelity issues independently.

**Operational generation and reranking.** Independently generate Arabic and
English reasoning for the matched problem views in a future authorized run.
Arabic reasoning must originate in Arabic, not be translated from an English
trace. Use the same pinned generator, decoding settings, candidate count and
recorded seeds/order. These independent candidate sets are **not content-matched
solutions**, so their language contrast includes generator differences. Compare
all rerankers on exactly the same Arabic pool within each problem, and separately
on the same English pool. This distinguishes available correct solutions from
the PRM's ability to select them.

The Arabic-native specification and real human rubric are in
[ARABIC_NATIVE_BENCHMARK_V1.md](ARABIC_NATIVE_BENCHMARK_V1.md). The translated
PRM800K corpus remains a separate potential adaptation source, never a substitute
for this evaluation benchmark.

## Size, scope and resources

Propose **500 unique source problem groups**, target 400 native Arabic/100
translated (80%/20%), across arithmetic/number theory, algebra, geometry,
probability/combinatorics, and applied word problems. This is a bounded
school-to-introductory-university study, not a claim about all Arabic mathematics.

| Split | Arabic-native target | Translated control target | Total |
|---|---:|---:|---:|
| Train, reserved for possible later authorized research | 80 | 20 | 100 |
| Development / diagnosis and calibration | 80 | 20 | 100 |
| Locked final test | 240 | 60 | 300 |
| Planned frame | 400 | 100 | 500 |

These are **targets, not collected data**. Enforce native ≥50% and translated
≤30% overall and within each split; target 80/20 provides margin. Only evidenced
native or translated origins enter the finalized frame, so the translated ceiling
actually implies ≥70% native with these two classes. Unknown/adapted origins
cannot fill a quota. Report counts of independent source families as well as
problems; clustering can make 240 problems less informative than 240 independent
pairs. Domain/difficulty/source quotas must be fixed before seeing model outcomes.

For an illustrative discordant-pair fraction of 0.30, two-sided alpha .05 and
80% power, the conservative normal approximation
`n = ceil((z(.975)+z(.8))² * 0.30 / delta²)` gives **236 independent pairs for a
10 percentage-point gain**, versus **942 for a 5-point gain**. The offline tool
reproduces these calculations. These are planning assumptions, not achieved power
or a guarantee. Inflate for clustering/unresolved outcomes and use dev discordance
to revise sample size **before unlocking test**, without selecting for a desired
test result. The 240-native test target is unsuitable for ruling out small gains.
Worst-case binomial precision at n=240 is approximately ±6.3 points before
clustering; twenty problems give approximately ±21.9 points by the same rough
normal calculation.

Feasibility matters. K=8 in two languages on 300 test problems would require
4,800 generation positions; adding the dev split would add 1,600, and optional
train generation another 1,600. None is authorized or scheduled. Four Arabic
traces on each of 240 native test problems, eight steps/trace and two independent
assessors would require about **15,360 Arabic step judgments**, plus English
mirror assessment, all-eight-candidate final outcomes and adjudication. Eight
steps is a workload assumption, not an observed average. Resolve staffing and
the size/power tradeoff with the supervisor before collecting this study.

## Controlled downstream endpoint

Freeze the problem roster, reference outcomes, candidate manifest and scoring
policy before test analysis. For each problem retain all eight generation
positions, including failures, in their original order. All PRMs score those
same candidate IDs/bytes; prohibit score-dependent regeneration, candidate
replacement or test-set tuning. Analyze nested K=1,2,4,8 prefixes; K=8 is primary.

Compare these prespecified selectors:

1. First sampled candidate. This is **not** a greedy decoding baseline.
2. Uniform random selection: exact expected accuracy of the fixed pool.
3. Majority canonical final answer, with ties resolved by generation order.
4. Frozen base PRM selection, with its mean-step aggregation fixed on dev.
5. Existing pilot adapter as a secondary exploratory scorer only if a separate
   authorized scoring run and immutable model/tokenizer/reward-head pins exist.
   Any later newly trained scorer requires its own prior training authorization.
6. Oracle@K: whether the recorded pool contains any correct final answer. This
   is an availability ceiling, not an implementable selection method.

The primary endpoint is **final-answer accuracy on the 240 held-out Arabic-native
problems, base PRM versus first candidate at K=8**. Report absolute percentage-point
change, family-cluster bootstrap 95% interval, paired wins/losses, and coverage.
Use exact McNemar only if independent source families have one problem each;
otherwise retain the clustered interval and do not attach an independence-based
p-value. English and translated controls, other K, aggregation alternatives and
adapted-versus-base are secondary; label multiple comparisons exploratory.

Qualified humans determine mathematical final-answer equivalence against a
separately checked reference, blinded to PRM scores and selector identities.
Canonical answer keys support majority voting; string mismatch alone cannot
classify fractions, equivalent expressions, units or answer sets. Correct final
answers with flawed reasoning count for the stated final-answer endpoint, with
reasoning validity reported separately. The PRM may not use reference outcomes.

Resolve reward-score ties by original generation position, never correctness.
Failed generation remains a failed position with unavailable reward; it is not
removed from K or replaced. A missing reward for a generated candidate triggers
the recorded first-position fallback for that problem/scorer. A human outcome
still unresolved stays unknown: show all-problem best/worst bounds and withhold
the primary paired estimate until complete. Do not silently discard hard cases.

Report oracle availability minus selected accuracy to diagnose selection loss.
If oracle is low, improving the reward model alone cannot fix absent solutions.
Report generation/reward failure and truncation rates, token budgets, scoring
latency and peak memory from actual future logs. Matched pools isolate selection
benefit under a common generation cost; they do not show faster end-to-end solving.

## Run reproducibility and evidence still missing

Before any future run, pin generator and PRM weights/revisions, tokenizer,
adapter/reward head, prompt bytes, seeds, temperature/top-p/top-k, repetition
penalty, token ceilings/context, reward extraction and package/device environment.
The local Qwen digest reported earlier is only evidence about that old laptop
setup; a model name is insufficient. No new run identity or authorization is
created here. Equal token caps may truncate Arabic more; retain this as an
operational outcome and use an untruncated sensitivity analysis, not silent retries.

The implementation now checks metadata composition/provenance declarations,
split leakage, recorded paired scores and deterministic fixed-pool replay. It has
no inference/training/export path. [Tool documentation](NATIVE_STUDY_TOOLS_V1.md)
lists implemented analyses and their limits. No hash authenticates an annotator's
qualifications, and CI does not establish semantic accuracy.

**Next scientific work:** source acquisition with permission and original-language
evidence; qualified Arabic mathematics annotator capacity and pilot rubric
calibration; family-based split review; model/runtime pins and an adequately
resourced protocol. These require real human evidence. Any later scoring or
generation requires separate explicit authorization. Further fine-tuning follows
the diagnosis, not the other way round. The old exhausted pilot20 stays closed;
the optional translation diagnostic24 remains inactive and deferred.

**Thesis wording:** “On twenty selected bilingual problems, the original PRM
showed a lower Arabic score separation. A small synthetic development pilot
improved score separation after adaptation. These findings motivate a larger
native-Arabic, human-labeled diagnosis and fixed-pool solving evaluation; they do
not establish the cause of the language gap or downstream solver improvement.”

Methodological context: [Lightman et al., Let's Verify Step by Step (2023)](https://arxiv.org/abs/2305.20050)
motivates evaluating process supervision through solution selection. This project
must supply its own Arabic evidence; published results are not its outcomes.
