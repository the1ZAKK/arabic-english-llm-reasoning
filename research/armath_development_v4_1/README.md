# Reproduce the inactive development scope

[Scientific scope, cases, endpoints and human/resource needs](../ARMATH_CONTROLLED_DEVELOPMENT_V4_1.md).
This reuses the existing source audit and v4 selection. No new model client,
installation, approval form, inference runner or launcher is introduced.

The public `proposal.json` contains source identities and proposed scheduling,
**not an active budget**. Proposed maxima: 96 Arabic generations, 512 output tokens
each; 240 unique PRM scoring cells, 1,024 input tokens each. Actual authorization,
observations, step labels and benchmark-eligible cases are zero. Five references
are narrow automatic agreement proxies; seven are excluded until resolved in a
separately bound reference policy. Do not rewrite the current proposal to add
human approval or numerical keys.

Pinned canonical proposal identity (`native_study_v1.digest`):
`6a9bfa0c3f323327385b625196b5843014e7dbfb77b6065f51d9f640f7e0924b`.
Exact `proposal.json` file SHA256:
`b55842079bea5103609609ddf24ec875186c09cc0d724f23c12a1cb662d6afbd`.

## Offline preparation

Use the existing reproduced `PRIVATE_AUDIT` (see [v4 instructions](../armath_v4_0/README.md)).
It must match all nine frozen audit fingerprints. Python 3.11+ standard library only:

```text
python -B research/prm_arabic_english/armath_development_v4_1.py prepare --audit-dir PRIVATE_AUDIT --output-dir NEW_PRIVATE_DEVELOPMENT
```

The destination must be new and outside **every** Git checkout. It receives:

- `proposal.json`: exactly matches the public scope, including policy hashes.
- `requests_proposed_NOT_APPROVED.jsonl`: 96 fixed question-only request descriptions;
  the tool cannot dispatch them. Each hash and seed matches the public roster.
- `references_private.json`: technical source/question comparisons, five usable
  proxy keys and seven null keys; no human assessment prefilled.
- `observations_empty.json`: all 96 slots and both reward statuses explicitly
  `not_attempted`, with null text/tokens/scores/conditions.
- `empty_replay_report.json`: choices, coverage, all unknown endpoint outcomes,
  null accuracy and zero new model operations. Empty report choices are fallback
  positions for software preparation, not observed selections or results.

CI regenerates this packet and verifies the exact public scope without uploading
private source/reference/request files. The five original data hashes, old audit
artifacts, v4 outputs, frozen42 and historical attempts are also checked by the
existing offline workflow. Source acquisition downloads dataset JSON only.

## Later offline replay of real records

Do not populate observations with illustrative translations or invented scores.
After separately authorized future execution, each of the 96 fixed `rows` must
retain its `candidate_id`; use `not_attempted`, `reserved` (crashed reservation),
`failed` or `generated`. Generated responses need exact raw UTF-8 text and SHA256;
unavailable rows have null text/hash. Keep transport/exception details in the real
immutable execution record, not in fabricated candidate text.

Both `rewards` roles have explicit v3.1 statuses and null unavailable `scores`.
Actual scored vectors require the real matched conditions, exact canonical
`input_item` including question hash, token IDs and character offsets/anchors, using
[the existing scoring record schema](../SCORING_DIAGNOSIS_V3_1.md). The `item_id`
is the candidate ID; `problem_sha256` binds the original question. This replay
analyzes the 192 Arabic canonical cells; use the existing v3.1 recorded analyzer
for the 64 bilingual/rendering diagnostic cells, sharing the same 16 canonical
observations. It must not trigger 16 duplicate scores.

```text
python -B research/prm_arabic_english/armath_development_v4_1.py replay --audit-dir PRIVATE_AUDIT --observations PRIVATE_RECORDED.json --output-dir NEW_PRIVATE_REPORT
```

A report checks internal consistency of supplied records; it does not independently
authenticate the hardware run, native authorship, reference correctness or humans.
Numerical/protocol proxies must be reported as such. Freeze selector choices before
outcome review, retain all missing/failed slots, and preserve populated human
evidence separately. Keep private raw outputs, identities and review records out of
public commits; publish sanitized results only when genuinely available.

No model operation, active allowance, human annotation, training, export or benchmark
eligibility follows from either command. Existing pilot20/diagnostic24 remain separate.
