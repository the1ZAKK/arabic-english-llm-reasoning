# v3.1: controlled performance-gap diagnosis

This is a scoring protocol and an offline recorded-observation analyzer, **not a
scoring runner or execution authorization**. It loads no tokenizer/model and
creates no requests or budget. Frozen v1/v2 sources, outputs, labels, checkpoints,
retry ledgers and the 42 execution fingerprints remain unchanged.

## What existing evidence can establish

The [v3 audit](RETAINED_EVIDENCE_AUDIT_V3.md) is preserved. The separate
[v3.1 replay](PERFORMANCE_GAP_DIAGNOSIS_V3_1.json) rechecks its thirteen input
hashes and adds precision bounds for the nonempty-line aggregation sensitivity.

| Hypothesis | Evidence possible now | Evidence still required |
|---|---|---|
| Empty lines affect the reported aggregate | Confirmed: 160 blank reward positions/language; recompute means of retained four-decimal scores without those positions | New scoring is needed to test changing the input rendering, not to recalculate an existing aggregate |
| Recorded four-decimal precision explains the discrepancy | Nonempty base EN–AR gap difference 0.227700; deterministic rounding-only bounds [0.227500, 0.227900] | No new scores needed to reject this narrow rounding-only explanation, conditional on the original category tags |
| A purely monotone score recalibration fixes ordering | Nominal correct is robustly uniquely highest on 13/20 Arabic versus 20/20 English after blank exclusion; no rounding-ambiguous top cases | Qualified assessment of label truth and bilingual fidelity; calibration alone cannot reverse those retained orderings |
| Quantization explains language weakness | Only a difference in checked-in runtime declarations is known | Same-base FP16/NF4 observations on the same device, inputs, tokenizer, head and extraction |
| Adaptation itself caused the recorded improvement | Old source-config differences confound this attribution | Unadapted base and existing adaptation bundle at matched NF4 runtime; no further fine-tuning needed |
| Reward positions match mathematical steps | Raw newline counts reproduce; one AR/EN candidate has 7 versus 6 positions | Actual tokenizer offsets/reward anchors and qualified human mathematical-step maps; counts alone do not prove this |
| Native Arabic scoring/generalization is weaker | Existing twenty problems are selected and their native/human-label provenance is unverified | Permission-backed native source frame, original Arabic traces and independent qualified Arabic labels |
| Arabic generation quality is worse | No suitable shared-budget original-language generation comparison in this audit | Separately authorized independent AR/EN pools and human outcomes; English mirrors do not answer this question |
| PRM selection improves solving | Authored correct-category ranking is a development diagnostic only | Fixed real candidate pools, frozen selectors and genuine final-answer judgments |

The nonempty gap's descriptive, problem-ID bootstrap 95% interval is approximately
[0.182271, 0.275078]. It conditions on the twenty selected IDs and does not resolve
unrecorded family clustering, category errors or selection bias. **Rounding bounds
are not confidence intervals.** Neither result identifies a full causal explanation
of Arabic weakness. Nominal category tags are not qualified human annotations.

## Minimum matched scoring comparison

Use existing retained candidates first as **development-only instrument checks**,
not as a new native benchmark. They provide 160 candidate-language items: twenty
problem IDs × four authored categories × two languages. Preserve original text,
including errors and whitespace, and original outputs. No new generation is
necessary for this future scoring check, but model forward passes still require
separate explicit authorization. The exhausted pilot20 and inactive diagnostic24
allowances cannot fund it.

| Role | Weights / adaptation | Runtime | Question answered |
|---|---|---|---|
| `base_nf4` | Exact base weights and original reward head | NF4, pinned compute dtype/device/software | Required common baseline |
| `adapter_nf4` | Same base plus the exact existing LoRA/reward-head bundle | Identical NF4 settings | Adaptation-bundle effect at fixed runtime |
| `base_fp16` | Same base and original head | FP16 on the same hardware with matched compute/extraction settings | Optional base precision contrast |
| `adapter_fp16` | Same existing adaptation bundle/head | Matched FP16 | Optional adaptation-by-precision interaction |

The core has 320 prospective **candidate scoring records**, not 320 Ollama
generation requests. Three/four conditions would have 480/640 records. These are
scope arithmetic, not an active allowance; no scoring records have been generated.
All four matched cells are required for the interaction
`(adapter_nf4-base_nf4) - (adapter_fp16-base_fp16)` on the **same complete items**.
Do not subtract effects estimated from different available-case sets.

Use one freshly loaded condition at a time if memory is limited. Do not merge an
adapter into a base instance and reuse that contaminated instance as a control.
Predeclare source-family blocks and counterbalance condition order across blocks;
interleave language views within each block. Keep evaluation/no-gradient mode,
input order/batching, determinism settings and score extraction pinned. Record
actual device/package/precision identities and missing outputs. There is no claim
that both precisions fit the reported laptop. If FP16 requires a different device,
offload policy or compute setup, it is a **runtime-bundle comparison**, not an
identified quantization effect; the tool blocks the precision attribution. The
matched NF4 comparison can remain useful if genuinely supported locally.

Required real fingerprints include base weights, tokenizer files, input policy,
extractor/scorer code, software environment, determinism settings, hardware,
reward head, and any adaptation bundle. A model name or old Qwen/Ollama digest
does not pin this PRM. No missing fingerprint is supplied or invented here.
Weight/head/bundle identities refer to canonical source checkpoint manifests
before numerical casting or quantization. Actual runtime settings are recorded
separately; different in-memory precision representations are not identical blobs.

## Blank rewards, input identity and alignment

1. Preserve the raw candidate UTF-8 hash. Reconstruct the **versioned** legacy
   input using the actual pinned tokenizer and per-segment preparation, including
   prompt/special tokens. Log exact input IDs and their canonical JSON SHA256.
   Retokenizing the entire response differently is a new input policy, even if
   the printed text looks identical. Never change the old helper or frozen text.
2. Record response offsets in **Unicode code points, not UTF-8 bytes or UTF-16
   units**, mapped back from the actual tokenization. Prompt/special tokens have
   null response offsets. Legacy newline splitting appends a newline marker to
   each segment, so offsets refer to `source_text + "\n"`. It includes the
   synthetic final marker, without altering the stored source.
3. Check complete nonwhitespace source coverage, ordered offset ranges and one
   distinct reward anchor per raw segment at its following newline. Raw Arabic
   numerals, mathematical operators and source text hashes must match exactly.
   The new tool checks this **lexical** contract from recorded metadata. It cannot
   authenticate that an operator actually used the declared tokenizer or device.
4. Compute all-position and nonempty-position means from the **same score vector**.
   This tests aggregation with zero extra forward passes. Excluding blank rewards
   after scoring does not simulate removing their tokens from the model input.
   Input/rendering changes need a separately declared contrast and new observations.
5. Independently map mathematical steps on the annotation subset. A nonempty line
   may be neutral prose, multiple mathematical steps or part of another step.
   If mathematical labels do not align with reward anchors, retain the discrepancy
   and withhold that step-quality comparison. A human-map hash is evidence binding,
   not automatic verification. Alternative semantic segmentation is an explicit
   development intervention, never a silent repair of frozen reasoning boundaries.

Human correctness/neutral labels and references are for evaluation, not inputs to
the primary automated selector. The operational policy is described in the
[reranking plan](RERANKING_OPERATIONS_V3_1.md). An expert-assisted semantic-step
score diagnostic must be labeled separately from automated solving performance.

## Recorded analyzer and missingness

`scoring_diagnosis_v3_1.py existing` reproduces the aggregate replay above.
`recorded --input PRIVATE.json` analyzes actually supplied records only. Its header
kind is `recorded_scoring_diagnosis_v3_1`; `conditions` maps the role names above
to their fingerprints/settings, `items` contains source/token/offset manifests,
and `observations` contains every planned item × declared condition exactly once.

Each item has `item_id`, `problem_id`, `family_id`, `language`, `source_text`,
`source_sha256`, `input_ids`, `input_sha256`, `response_offsets`, ordered
`reward_positions`, and `human_step_map_sha256` (actual hash or null). Each condition
has the fingerprint names shown in the tool's `COMMON` tuple plus explicit
`device`, `compute_dtype`, `precision`, `quantization`, `reward_head_sha256` and
`adapter_bundle_sha256` (null for base). Quantization is exact: NF4 bits=4,
type=nf4,double_quant=true; FP16 bits=16,type=none,double_quant=false. Actual
load/head/compute implementation must additionally be bound by the code/environment
fingerprints. The validator does not perform a weight conversion.

Each observation has `item_id`, `condition`, `status`, `input_sha256`, and `scores`.
Statuses are `scored`, `not_attempted`, `unavailable`, `failed`, `truncated`, or
`alignment_failure`. Only scored cells carry complete numeric probabilities;
other cells have null scores. Reject omitted/duplicate cells, changed inputs,
wrong score/anchor counts and invalid offsets. Count every missing cell; no
automatic retry, replacement or imputation is provided. If declared comparison
settings differ, report the mismatch and no numeric attribution for that contrast.

Complete comparable items contribute equal-item means within problem, then
equal-problem effects and whole-family bootstrap intervals, separately by language.
Report coverage beside every contrast. Four-cell interactions use complete
four-cell items, not mismatched pairwise subsets. These are **numeric score
contrasts**, not evidence of improved correctness discrimination. Once real human
labels/semantic alignment exist, use the v3 paired gap/Brier tool for reliability,
and the fixed-pool tool for solving. Missingness and uncertain human labels remain
visible; configuration consistency is not authenticated execution or human QC.
