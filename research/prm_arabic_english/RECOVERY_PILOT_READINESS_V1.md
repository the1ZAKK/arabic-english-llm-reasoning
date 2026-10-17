# Recovery-v1 pilot readiness audit

Development and verification only. **No execution authorization, active approval, model generation, download, scheduled task, training or export is created by this workflow.**

## Verified uploaded plan

- Canonical prepared-plan identity: `446191b88e072c291ff34388a7fbb4166a6813639a63bb2ef54896431c6e7e4e` (independently recomputed, excluding its own `plan_sha256` field).
- Uploaded JSON file SHA256: `559ec98308f8912f1431d0366ed6536f15e0564a1b0f486f928bec96f3a27d0c`. This raw-file checksum is distinct from the canonical plan identity.
- Model: `qwen3:4b`; exact recorded digest: `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`. This value was read from the verified plan; installed laptop identity still requires metadata-only verification.
- All 2252 fields and source/slot hashes were checked against canonical frozen PRM800K queues. The plan has 1075 mechanically validated fields and 1177 unresolved fields / 2005 slots.
- Every unresolved slot records exactly nine historical attempts. No counters are refunded or reset.
- The serialized protected snapshot contains 814 files, including 51 checkpoint files; its identity is `2a86e8b2b230bd1fe096c87bf1a9fe2d1febadd235b7664223941ba9b4da854f`. The uploaded snapshot hash is verified; current laptop bytes cannot be verified from the cloud.
- The existing runner and all its plan-bound dependency bytes match the plan. They are left unchanged so this plan remains valid. Only new versioned preparation code, tests, documentation and CI wiring are added.

## Exact fresh initial dispatch

This is the first pass of a **fresh, uninterrupted** invocation with an empty recovery journal. Each row gets one new attempt. Ordinary English-only, mixed-language, math or boundary rejection consumes a reservation and advances to the next row; it does not immediately retry that row. A transport failure stops the invocation early.

| Request | Batch | Field | Slot | New attempt |
|---:|---:|---|---|---:|
| 1 | 09 | `dev:0:4` | `s1` | 1 |
| 2 | 09 | `dev:0:4` | `s2` | 1 |
| 3 | 10 | `train:0:0` | `s2` | 1 |
| 4 | 10 | `train:0:0` | `s3` | 1 |
| 5 | 10 | `train:0:4` | `s2` | 1 |
| 6 | 10 | `train:0:4` | `s4` | 1 |
| 7 | 10 | `train:0:5` | `s2` | 1 |
| 8 | 10 | `train:0:5` | `s3` | 1 |
| 9 | 10 | `train:0:7` | `s2` | 1 |
| 10 | 10 | `train:1:0` | `s0` | 1 |
| 11 | 10 | `train:1:0` | `s2` | 1 |
| 12 | 10 | `train:1:0` | `s3` | 1 |
| 13 | 10 | `train:1:7` | `s0` | 1 |
| 14 | 10 | `train:1:8` | `s0` | 1 |
| 15 | 10 | `train:1:11` | `s0` | 1 |
| 16 | 10 | `train:1:12` | `s0` | 1 |
| 17 | 10 | `train:1:14` | `s0` | 1 |
| 18 | 10 | `train:1:17` | `s0` | 1 |
| 19 | 10 | `train:1:18` | `s0` | 1 |
| 20 | 10 | `train:1:19` | `s0` | 1 |

With 2,005 pending jobs, the 20-reservation ceiling is reached during this first pass. There is no second pass in a fresh uninterrupted pilot, regardless of quality outcomes. The per-slot ceiling of two does not imply ten slots get two attempts.

On a restart, the runner reconstructs pending from the beginning of the original job list, excluding accepted slots and slots already at two attempts. Earlier failed or crash-reserved slots with one attempt can therefore be retried before untouched slots. Successful retries disappear from later pending lists; failed second attempts are exhausted. Every previous reservation still counts toward the same total of 20. Consequently, later choices after outages/restarts depend on actual outcomes; they are not promised as a fixed second list. The preparation report derives the next first pass from the actual immutable budget and journal.

## Pre-inference audit of the existing runner

| Gate | Verified behavior |
|---|---|
| Plan, branch and code | Canonical plan digest, exact research branch/origins and plan-bound code hashes are checked before client construction. |
| Frozen sources and existing checkpoint bytes | The original protected snapshot is checked at invocation start and before each new reservation. Preparation additionally regenerates frozen queues in a temporary directory and reconciles actual source, saved fields, partial slots, terminal supervisor, audit and historical counters against the complete plan. |
| Approval | `check_budget` runs before metadata or generation, and a separate canonical `run/approved_budget.json` is created-or-verified immutably. Changing caps or budget ID cannot renew the budget. The old zero-budget template is never activated. |
| Model | After approval validation, existing execution verifies `/api/tags` digest and `/api/version` via GET, once per invocation, before any `/api/chat`. There is no inference readiness probe or model pull. Preparation can perform only these GET routes and never execution. |
| New attempts | Hash-chained durable reservations are appended and flushed before generation. Crashes/outages consume reservations. Journal replay checks request/source/approval binding and counts, with caps 20 total and two per slot. |
| Output validation | Unchanged Arabic-only slot validation, exact source-owned math/numbers, reasoning boundaries and full-field assembly remain mandatory. Human semantic QC is still pending. |

“Immutable” here means create-or-verify approval bytes plus append-only, hash-checked journal handling. The local chain is not an external signed witness against deletion of all run state or rollback of a valid prefix. Preparation additionally fails closed if recovery artifacts exist without the expected approval/journal. It never repairs, deletes or resets such records.

## Safe Windows verification and inactive proposal

`install_pilot_preparation_windows_v1.ps1` installs a separate hash-verified Git-blob package under `recovery_artifacts/recovery-v1/pilot-preparation-v1/`. It leaves the old immutable runtime and plan untouched. It has no execution or approval activation parameter. The final CMD bootstrap will be pinned only after Windows and Linux CI pass. Its hash mismatch path must pass native Windows testing before delivery.

The default tool reads the exact local plan, verifies raw and canonical hashes, the entire current protected snapshot, all frozen sources/checkpoints and the exhausted terminal state. It checks the old zero-budget template remains inactive. It then queries the already-running local Ollama service using metadata-only GET requests. If Ollama is absent or the digest differs, it produces a blocked report; it never starts Ollama or downloads a model.

New output is an append-only verification folder containing `verification.json`, `review.html`, and `pilot20_proposal_NOT_APPROVED.json`. The proposal has a different schema/kind from a real approval, `approved: false`, zero requests authorized, and null approver/time/budget identity. Even changing only its approved flag cannot make it pass the actual runner validator. The original `budget_NOT_APPROVED.json` is compared byte-for-byte before/after and is never written.

Existing recovery budgets and ledgers, if present, are read and validated only. The tool never writes `approved_budget.json`, reserves an attempt or calls the generator. Unknown `--execute`/`--approval` flags are rejected.

## Reviewing an eventual authorized pilot

Rerun the same verification launcher to obtain a fresh HTML view of recorded outcomes, English source fragments, model candidates, reservation counts, remaining ceiling and the next eligible first pass. This performs no generation. Also inspect the original plan folder’s `run/attempts.jsonl`, `run/summary.json`, `run/fields/`, and, for fully complete batches, `run/review_artifacts/<batch>/review.html`. A partial or rejected slot is not a completed field. Existing human-QC decisions are never rewritten. Mechanical validation never constitutes semantic equivalence or human approval.

## Local checks still required

- The laptop must contain the exact plan at its fixed content-addressed path and the same 814 protected files. Current file bytes, terminal state and installed model/GPU cannot be inspected remotely.
- The already-running local Ollama service must report the exact plan-bound model digest; actual prompt quality and GPU behavior remain untested without explicit inference authorization.
- Windows/Linux CI uses synthetic model responses and disposable fixtures. Automatic CI does not run legacy scheduled-task installation tests; those are explicit manual opt-in and are not invoked for this pilot. Pure preservation, source, protocol, budget and Windows packaging checks remain active.

## Exact future decision — not granted by this report

> I authorize execution of the recovery-v1 pilot for plan 446191b88e072c291ff34388a7fbb4166a6813639a63bb2ef54896431c6e7e4e using qwen3:4b digest 359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7, only after local verification passes, with at most 20 total generation-request reservations, at most 2 new attempts per slot, and at most 512 generated tokens per request. Failures, outages and crashes consume budget; historical attempts are not refunded. Keep human QC pending; no export, training or scheduled task.

Only after the user gives that explicit execution consent should a separate active approval be created with the actual approver identity, actual consent time, chosen budget identity and verified local model digest. Those fields remain unset now. Selecting or preparing the 20/2/512 proposal grants **zero** requests. No inference execution launcher is included in this preparation deliverable.

## Launcher release pin

`verify_recovery_pilot20_windows_v1.cmd` was prepared only after commit `e1b96d656dac406a7af3abfae73637a3a1964653` passed 178 tests on both Windows and Linux, plus native pilot-package verification: [implementation CI](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39016475689). That is the pinned preparation runtime. The original recovery runner remains byte-for-byte identical to the plan-bound baseline. The checksum sidecar binds the exact CRLF launcher bytes; `.gitattributes` prevents checkout conversion. The final release CI also exercises the actual Windows CMD download and deliberate incorrect-installer-hash rejection. Hashing uses .NET directly, without reliance on PowerShell module discovery.
