# Recovery-v1 pilot budget proposal — review only

**NOT AN APPROVAL. NO INFERENCE AUTHORIZED.**

The user agreed to prepare a proposal for review, **not** to approve or execute model requests. This file is documentation, not a recovery-runner approval JSON. It has no `approved: true` field and must not be passed as `--approval`.

## Plan binding

- Prepared local plan SHA256: `446191b88e072c291ff34388a7fbb4166a6813639a63bb2ef54896431c6e7e4e` (reported from uploaded local plan; runner must independently verify)
- Model: `qwen3:4b`
- Runtime must verify the **exact model digest stored in the local plan**, as well as branch, code hashes, and protected file snapshot
- Batch scope: 09–32; reported baseline 1,075/2,252 validated fields, 1,177 unresolved fields
- Recovery prompt: `msa-single-fragment-v1`

## Proposed ceiling (not yet granted)

| Control | Proposal |
|---|---|
| New HTTP generation requests, total | 20 |
| New attempts per unresolved slot | 2 |
| Maximum generated tokens per request | 512 |
| Historical attempts refunded | 0 |
| New requests authorized at present | **0** |
| Human QC | Pending |
| Training export | Forbidden |

Reservations happen before HTTP generation; failed requests, service outages and crashes consume budget. The budget is bound to one plan and cannot be renewed by reinstalling, rerunning, changing the budget ID, or editing old attempt counters.

## Exact separate approval required later

The immutable approval JSON, when separately authorized, must contain exactly the keys checked by `recover_v2.py:check_budget`: `schema_version`, `kind`, `version`, `plan_sha256`, `model_digest`, `budget_id`, `approved`, `approved_by`, `approved_at_utc`, `max_requests`, `max_attempts_per_slot`, `max_tokens_per_request`.

No such approved JSON is created by this proposal. Approver, time, budget ID and model digest must be populated from **actual user consent and local plan verification**, not guessed or taken from placeholder values. Do not edit `budget_NOT_APPROVED.json` or `state.json`.

## Review gates before any inference

1. Confirm the local prepared plan SHA, model digest, snapshot and installed immutable runner identity.
2. Inspect how the runner orders `plan["jobs"]` and what the 20-request pilot would attempt; don't promise a particular batch or sample without verifying selection.
3. Obtain a fresh, unambiguous user authorization explicitly covering **execution** and these hard caps.
4. Create the **separate** approved budget file bound to that one plan, then verify its immutable content.
5. Only then provide a consent-gated execution workflow. Never launch locally without the user's action.
6. Review generated bilingual artifacts and remaining rejections; no human QC is implied by mechanical validation.

**Important:** This document cannot itself start Ollama, install a scheduled task, authorize requests, or change frozen sources/checkpoints/attempt logs.
