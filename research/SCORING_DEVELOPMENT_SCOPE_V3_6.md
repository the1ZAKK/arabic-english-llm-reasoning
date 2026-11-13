# v3.6 — prospective matched scoring instrument check

**Preparation only. No model/tokenizer load, forward pass, warm-up, generation,
scoring request, active budget or score is created.** This is not an executor or
an approved experiment. Reuse the [v3.1 scoring protocol](SCORING_DIAGNOSIS_V3_1.md)
and its existing `scoring_diagnosis_v3_1.py recorded` analyzer after actual records
exist; preserve all original inputs and outputs.

## Exact prepared scope

The [separate scope JSON](prm_arabic_english/prospective_scoring_scope_v3_6.json)
contains **160 actual retained candidate-language items**: 20 old problem IDs ×
four authored category tags × Arabic/English. Only IDs and exact problem/response
UTF-8 hashes are published, not copied texts. Existing AST-only readers extracted
the literals; legacy model runners were never imported. Category tags are historical
development tags, not independent human labels or generated solving outcomes.

Two proposed conditions, `base_nf4` and `adapter_nf4`, give **320 candidate-condition
scoring records**, with proposed batch size one. Every cell is `not_attempted`,
with null scores. These are scope arithmetic and a static order, not reservations,
HTTP generation requests or authorized forwards. Canonical scope identity
(`native_study_v1.digest` of the parsed JSON):

`55f463ade951437b357ab9c0be1a7a9a58a9e0542004cb941f5b252cc8fa4f7a`

Four successive retained-ID blocks of five problems use condition order **AB, BA,
BA, AB**, A=base NF4 and B=existing-adapter NF4. Within each problem/category,
language views are interleaved; ten problem IDs start Arabic, ten English. This
counterbalances a development instrument check, **not verified source families**.
Family IDs remain null; family independence and cluster intervals cannot be claimed
until a real family map exists. No outcome-based sorting or cherry-picking occurs.

## What must be bound before any separately authorized run

Actual base weights/tokenizer, original and adapted reward heads, existing adapter
bundle, input policy/extractor, software/determinism, hardware/device/compute dtype,
input IDs and Unicode offsets/reward anchors are still required. Missing hashes
and metadata remain null, never invented. Qwen/Ollama's translation-model digest
does not identify this PRM. NF4 feasibility on the laptop is unverified; a fit or
runtime claim cannot be inferred from a model name. No automatic model download,
installation, offload change, scheduling or execution launcher is prepared here.

Use the same raw item and tokenization policy for both conditions, matched NF4
settings and separately fresh model instances to avoid adapter contamination of
the base control. An eventual authorized operator must bind the actual runtime,
source-family map and finalized order before scoring. If feasibility/settings force
a change, version and re-review the scope; do not attribute a confounded runtime
comparison to adaptation alone. FP16 contrasts are deferred and outside these cells.

Compute all-position and nonempty-position aggregates from each **same recorded
score vector**, requiring no additional forwards. Retain blank lines and original
reasoning/numerals; excluding blank rewards afterward does not simulate removing
their input tokens. Actual human semantic-step maps remain separate from newline
anchors. Failed, truncated, unavailable and interrupted observations retain their
cells; no automatic replacement, retry or invented score is specified.

The preparation artifact intentionally has a different kind from recorded scoring
observations and fails that analyzer's input contract. It cannot supply missing
token/runtime identities or authorize a run. The exhausted pilot20 and inactive
diagnostic24 budgets cannot be reused. Any future model operation requires separate
explicit authorization of the final bound scope; none is requested or implied here.

## Scientific limits

The exposed student submission is excluded: one human Arabic attempt without an
English counterpart or independent labels cannot become a held-out model pool or
language-gap estimate. Likewise, the retained selected twenty-problem check cannot
establish native benchmark efficacy, human accuracy or downstream solving gains.
Use it only to diagnose matched-runtime/aggregation/alignment behavior. The larger
Arabic-native study and [fixed-candidate solving evaluation](RERANKING_OPERATIONS_V3_1.md)
still require authentic sources, qualified independent Arabic labels, separately
authorized candidates/scores and held-out final-answer outcomes.
