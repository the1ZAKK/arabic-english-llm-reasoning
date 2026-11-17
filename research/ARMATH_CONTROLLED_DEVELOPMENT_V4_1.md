# v4.1 — controlled Arabic scoring and solving development

17 November 2026. **Offline preparation, zero new model observations.** The owner
has removed a full-6,000-record manual-review prerequisite for development work.
This does not validate the dataset, resolve its lineage, supply human step labels
or authorize a model operation. The published original folds, historical audits,
100-case selection, source partitions and earlier experiment releases are unchanged.

## Concrete scope and question

Use [the reproducible inactive proposal](armath_development_v4_1/proposal.json)
and [offline operations](armath_development_v4_1/README.md). The twelve cases are
source-tagged `novel`, already exposed in the v4 development panel. There are eight
word problems, four arithmetic controls, twelve canonical equation templates and
eight **legacy mathematical-similarity components**, not eight authenticated source
families. Selection was purposive for manageable exact quantities and operations;
there are no inclusion probabilities, new held-out splits or generalization claims.
Original Arabic problem authorship remains a source declaration; model-generated
Arabic solutions would not be qualified human reasoning-step annotations.

| Pinned source suffix | Development role / quantity | Automatic endpoint now |
|---|---|---|
| `fold0:0078` | Shared boat rental / payment per person | Excluded; source-only reference review pending |
| `fold0:0832` | Sum and price difference / first book | Excluded; reference review pending |
| `fold0:0675` | Arithmetic control / two products | Question-derived agreement, 76 |
| `fold1:0152` | Rate conversion / cans per minute | Excluded; time-unit reference review pending |
| `fold1:0528` | Weekly saving / weeks remaining | Narrow question-derived agreement, 5 |
| `fold2:0253` | Arithmetic control / product divided by two | Question-derived agreement, 18 |
| `fold2:0622` | Isosceles perimeter / leg length | Excluded; geometry reference review pending |
| `fold2:0798` | Capacity and volume / litres left | Excluded; unit reference review pending |
| `fold2:0307` | Arithmetic control / addition and subtraction | Question-derived agreement, 212 |
| `fold2:0836` | Banknotes / money shortfall | Excluded; reference review pending |
| `fold4:0735` | Square perimeter / area | Excluded; geometry/unit reference review pending |
| `fold4:0662` | Arithmetic control / negative result | Question-derived agreement, −10 |

Every suffix expands to `ARMATH:260850e0510e:<suffix>`. Proposal rows contain exact
upstream revision, source URL/JSON pointer, record/question/equation hashes,
grouping identities and quality flags. Private preparation reads the five published
folds, verifies their bytes and all nine old audit fingerprints, and checks membership
in the unchanged 32+68 panel. The frozen limited exact-project overlap check has
zero hits for these twelve against its explicitly documented inputs; paraphrase,
template and pretraining overlap are not ruled out. It does not copy private
student or human records.

**Five automatic reference proxies, seven excluded unresolved references, zero
human-approved problems** is the current endpoint frame. An evaluable source
equation alone is insufficient. Existing complete-question checks must independently
recognize the question and agree exactly with its equation. They remain fallible
technical checks. Four of the five are arithmetic controls; this denominator cannot
support a claim about Arabic word-problem solving. Prefer resolving the seven word
references before requesting the full generation experiment. Genuine later reference
decisions require a separately bound version; the replay rejects silent promotion.

Known discrepancies `fold3:0280`, `fold2:0366`, `fold4:0141` and discrete unresolved
`fold2:1019` are outside this scope. Irrational/pi, operator-scope, rounding, unit or
discrete-domain ambiguities do not acquire an automatic key from equation evaluation.
Raw sources and unresolved cases remain preserved in the original 100-case packet.
All six thousand published problems remain distinct from the future annotated benchmark.

## Fixed Arabic solving pool and fair selection

Propose **12 × 8 = 96** independent Arabic generation slots. All selectors see the
same recorded pool; no PRM generates or repairs its own candidates. Use local Ollama
`qwen3:4b`, required digest
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
This is a required identity from prior evidence, not a fresh laptop verification.

The private request roster fixes per-slot seeds, full Arabic prompt and JSON schema.
Only the original question reaches the generator: no source equation, computed
reference, source-quality flag or human outcome. Request `think:false`, `stream:false`,
`num_ctx:2048`, `num_predict:512`, temperature 0.8, top_p 0.9, top_k 40, min_p 0,
repeat_penalty 1 and repeat_last_n 64. Return 1–8 short Arabic solution steps and
one numeric final answer in the requested unit, without the unit text. These are
observable solution steps, not a request for hidden internal reasoning.

Dispatch one candidate per problem before the next position. Seeds derive from
the version seed, source ID and candidate position; all 96 are distinct. They bind
the proposed schedule, not bitwise determinism across Ollama versions/drivers.
No history/chat context is carried between requests. Failed transport, malformed,
English/mixed, token-limited and interrupted candidates retain their slots. No retry,
replacement, additional warm-up generation or budget refund. Raw responses survive
unchanged; schema/language flags are diagnostics, not linguistic correctness labels.
The current code creates request descriptions only and has **no HTTP/model client**.

The primary endpoint is **Arabic-protocol-compliant final-answer success** for
base-PRM selection versus the first sampled candidate at K=8, on the predeclared
reference-evaluable denominator. Also report numerical correctness at those same
selected positions, so an English response is not misdescribed as a mathematical
error. Exact rational keys accept Arabic-Indic digits, finite decimals and simple
fractions (0.6 = 3/5); reject prose, multiple answers, thousands ambiguity and
nonfinite/expression fields. Units are not opportunistically stripped or converted.
Source checking must establish the requested quantity/unit before an endpoint key.
Formatting failure is a protocol failure and cannot establish mathematical failure.

Secondary comparisons: existing-adapter PRM, exact-answer majority, analytical
uniform-random selection expectation, oracle availability and selection loss; nested
K=1/2/4/8 reuse prefixes with no additional generation. Majority ignores references;
ties choose the earliest position. Invalid Arabic candidates cannot receive primary
PRM scores or majority votes. Missing reward for any otherwise valid candidate makes
that PRM selector fall back to position zero, with the fallback reported. Failed
positions remain in K; numerical-only outcomes at selected positions remain visible.
Unattempted slots have unknown outcomes; reserved/crashed and failed slots consume
their positions and are unsuccessful protocol completions. Never replace missing
records with invented outputs or silently restrict to successful generations.

The offline replay binds the generation pool, reward-record manifest, decision
status and choices in a selection seal **before joining reference values**.
Choices in a prefix containing unattempted slots are explicitly provisional; PRM
and majority endpoint accuracy is withheld until that prefix is terminal. The
first-sample outcome can still be known. Both reward-cell status counts and pool
completion remain visible, so a missing-score fallback cannot be mistaken for an
observed PRM scoring result. It
reuses `selector_positions`, `outcome_summary` and `selection_loss` from v3. The old
held-out/human benchmark validator is unchanged; this separate development analysis
does not counterfeit test membership or human labels to satisfy that gate. It cannot
authenticate a declared runtime or human judgment. Report per-problem choices,
reference coverage, failures, available correct candidates and descriptive differences.
No population confidence interval or significance claim is justified by these twelve
exposed cases and unverified family groups.

## Matched scoring and language-gap diagnosis

The repository actually uses **Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B**. Compare
fresh base NF4 with fresh base + existing pilot adapter **and trained reward head**,
both NF4 double-quantized, FP16 compute, batch one, eval/no-gradient, same tokenizer,
input/extractor, device/environment and determinism settings. This contrast is the
existing adaptation bundle effect, not a LoRA-only effect. No further training.

Existing local artifacts expected by the retained scripts are
`research/prm_arabic_english/checkpoints/arabicprm_pilot/best_adapter` and
`.../best_v_head.pt`. Their presence, weights/tokenizer/head/adapter hashes and actual
software/hardware fingerprints are **unknown**, explicitly null in the proposal.
The Qwen generator digest does not identify this PRM. Reuse v3.1's actual-condition
and token/offset validation, including one newline reward anchor per source segment.
Capture Unicode-code-point offsets, exact token IDs, problem/candidate hashes and
all raw rewards. No truncation, OOM retry, silent CPU offload or precision substitution.
Counterbalance base/adapter order AB, BA, BA, AB across four dispatch blocks.
Run 30 cells with one resident condition, unload it, then 30 with the other: eight
fresh condition loads total, not one reload per candidate-condition cell. Within
each condition, run the eight diagnostic cells, then the other 22 Arabic canonical
cells. Language order is AR/EN, EN/AR, AR/EN, EN/AR; rendering order is
canonical/blank, canonical/blank, blank/canonical, blank/canonical across blocks.
These scheduling factors are pairwise counterbalanced, not independent source
families or a basis for population inference.

Canonical scoring has **96 × 2 = 192 cells**. A fixed subset—the first word problem
in each block, positions 0 and 1—provides up to eight Arabic traces. Prepare genuine
faithful English mirrors of those eight traces and four questions only after outputs
exist; preserve errors, quantities, formula/digit strings and boundaries. Translate
prose only: do not convert units or normalize digits in just one language. Keep the
final numeric string identical. Digit-normalization contrasts are outside this scope. Two languages × two renderings
× two PRMs × eight traces = 64 diagnostic cells, including 16 already counted Arabic
canonical cells: **48 additional, 240 unique cells total**. If a selected trace fails,
retain its missing cells; do not replace it with a later successful candidate.

Canonical rendering joins the recorded short steps and `الجواب النهائي: <raw number>`
with single newlines, no leading/trailing blanks. Blank-line rendering doubles those
separators, changing only whitespace. English mirrors retain the same step/answer
structure. Compare all-position and nonempty-position means **from the same vector**
at no extra scoring cost. Removing blank tokens is a different, explicitly budgeted
rendering contrast. Real bilingual human step maps are required before correctness
discrimination claims; line alignment alone is not semantic alignment. If available
traces lack both correct and incorrect labels, withhold the discrimination metric.
Do not plant artificial errors in the downstream pool to force class balance.

Existing evidence already tests aggregation and rounding: the retained base EN–AR
nonempty margin difference is 0.227700, rounding-only bounds [0.227500, 0.227900];
there are 160 blank reward positions per language. These are selected, rounded,
nominally labeled old observations, not new native accuracy. New matched scores
would investigate content-aligned language shifts and adaptation behavior. They do
not establish Arabic-vs-English **generation** ability, native benchmark generalization,
or a quantization cause. FP16-versus-NF4 would require a different authorized scope.

## Necessary humans and resource boundary

No full-dataset review is required. Use the existing concise problem/reference and
step/final rubrics and separate developer/A/B/adjudicator sheets; do not invent people.

| Claim or use | Minimum genuine evidence still needed |
|---|---|
| Full twelve-problem numeric endpoint | Resolve the seven currently excluded references from original questions, units and constraints. Recommend two qualified Arabic mathematics checks per case (14 judgments), independent initial answers, separate resolution of disagreements before results are read. Also sample-check the five automatic keys; retain any newly discovered exclusions. |
| Eight-trace scoring discrimination | Two independent qualified Arabic-speaking step/final assessors for each available diagnostic trace; maximum 128 step judgments at eight steps plus 16 final judgments, actual work unknown. A distinct adjudicator handles disagreements; developer self-assessment is separate. |
| AR/EN scoring interpretation | Four question and up to eight trace mirrors, with real author/exposure disclosure and independent bilingual fidelity/step-alignment checking. No generated English mirror exists now. |
| Human-audited primary downstream result | Independently check the sealed first/base selected answers, at most 24 distinct outputs (two reviewers: at most 48 judgments). Sampled checks alone support a sampled-check claim, not every-output human accuracy. |
| All selector and oracle/random human endpoints | First/base/adapter/majority can select at most 48 distinct outputs (96 double assessments). Complete human oracle/random outcomes need all 96 candidate finals checked twice (192 judgments), retaining unavailable outputs. No need for step labels on all 96 to evaluate numeric answer selection. |

Before any separately authorized execution, inventory local artifacts read-only,
bind real manifests, verify local Ollama version/capabilities (`think:false` and
structured JSON) and digest, and check prompt + output context capacity. Future
execution must retain actual options/seed/model identity, reservation IDs,
`eval_count`, `done_reason`, input counts, timings and transport/crash outcomes. Do not
download/replace models. The proposal caps PRM inputs at 1,024 tokens/cell:
**240 × 1,024 = 245,760 input token positions**, not measured elapsed time or GPU fit.
The retained wrapper requests all hidden states and upcasts full-vocabulary logits
to FP32. With the model config's 151,936 vocabulary, 1,024-token FP32 logits alone
are 622,329,856 bytes (~0.58 GiB), excluding source logits, weights, hidden states,
KV/activations and allocator overhead. Reported 4-GB VRAM is not a fit guarantee;
no scoring or fit probe was run. Load generator and each PRM stage sequentially;
verify generator unloading without an extra generation call. Device/time feasibility
and actual package versions remain unknown.

**Separate execution authorization would have to bind** this exact proposal and a
tested executor/runtime release, 96 generation reservations (one/slot), at most
512 generated tokens each (**49,152 total ceiling**), plus 240 single-attempt PRM
scoring cells with 1,024-token inputs, no unlisted warm-ups/retries/rescores, actual
artifact identities and the selected reference gate. A durable no-refund ledger,
interruption/resume guard and final local confirmation still need integration and
verification for this new scope before execution. The request roster is neither an
executor nor an approval/budget file. Earlier pilot20 remains exhausted and
diagnostic24 inactive; neither allowance is repurposed here. No execution consent
is requested or inferred in this milestone.

## Implementation evidence and limits

`armath_development_v4_1.py` builds source-bound proposed requests and replays supplied
recorded pools only. It rejects altered scopes/keys, incomplete rosters, corrupted raw
responses, unmatched NF4 runtime declarations, invented unavailable scores, invalid
token anchors and overlength inputs. A missing/malformed/English/mixed candidate
is retained, never auto-translated. Existing source-number preservation validators
remain untouched: a solver may produce an erroneous/new number without that being
a translation-preservation violation. Lexical Arabic/protocol checks do not certify
grammar, mathematical reasoning or human QC. Contract v1.1 explicitly permits
source-relevant SI unit tokens (`mm`, `cm`, `km`, `mL`, `ml`, `kg`) within Arabic
steps while continuing to flag English explanations; it rejects embedded Unicode
line separators as well as literal newlines. This offline false-positive repair
supersedes the initial v4.1 draft at `5e04f48` before any execution; source choices,
reference gates, seeds and resource caps are unchanged. The earlier drafts remain
in Git history, with no allowance or observations attached. The replay follow-up
also binds pool/reward identities and withholds unfinished-pool selector endpoints;
its grouped scoring schedule preserves the same cells and resource ceilings. Empty preparation reports 96
`not_attempted`, null accuracy, no observations and zero authorization.

Offline verification: the local complete suite passes 711 tests, including 34
development regressions. The earlier SI-policy implementation f2d9b568 passed 707
on Windows and Linux in [CI44084659229](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/44084659229);
this follow-up has its own commit-specific Actions checks. CI validates software
and reproducibility, not semantic translation quality, human judgments or model efficacy.

Official implementation references (checked 17 November 2026):
[Ollama generation API](https://docs.ollama.com/api/generate),
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
[thinking controls](https://docs.ollama.com/capabilities/thinking),
[generation parameters](https://docs.ollama.com/modelfile), and
[Skywork config at a reference revision](https://huggingface.co/Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B/blob/025915e3cab8c4f66837aeb531bfcf0bc19b9f4b/config.json).
That external config citation does not fabricate the identity of locally installed weights.
