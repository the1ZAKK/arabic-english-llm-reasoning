# Separate diagnostic24 runner — development and verification

This implements the fixed twelve-pair design from [the diagnostic decision](RECOVERY_V2_1_DIAGNOSTIC_DECISION.md). **The user's instruction authorizes building/testing, not generation.** No real diagnostic budget or approval identity/time has been created. The original pilot20 remains exhausted and untouched. The old frozen proposal remains historically `execution_implemented:false`; the new separate execution release records the implemented code without activating that proposal.

The proposed limits remain **24 generation reservations total, one per slot per arm, two across both arms per slot, 512 generated tokens per request**, on the exact original plan/model digest. All24 source/context/payload identities and counterbalanced dispatch order remain bound to proposal `4327d769e30fdf2324d0d8000b4c828d3d311917993987af23c98687f1e0aa6d`. A source-only offline check reconstructs2252 frozen fields and verifies all24 proposed payload hashes without the private original plan or a model.

## Fixed dispatch sequence

Each row has two reservations in the displayed order. Failures never reorder the remaining rows, replace observations or resend a reserved arm. After an interruption the next selection is the first reservation not yet charged, regardless of whether previous responses passed mechanical validation.

| Reservations | Frozen slot | Arm order |
|---|---|---|
| 1–2 | `10/train:0:0/s3` | control, contextual |
| 3–4 | `10/train:0:5/s3` | contextual, control |
| 5–6 | `10/train:1:0/s3` | control, contextual |
| 7–8 | `10/train:1:14/s0` | contextual, control |
| 9–10 | `10/train:1:17/s0` | control, contextual |
| 11–12 | `10/train:1:18/s0` | contextual, control |
| 13–14 | `10/train:1:19/s0` | control, contextual |
| 15–16 | `12/train:2:0/s5` | contextual, control |
| 17–18 | `17/train:4:7/s2` | control, contextual |
| 19–20 | `13/train:6:0/s4` | contextual, control |
| 21–22 | `21/train:2:3/s1` | control, contextual |
| 23–24 | `16/train:0:0/s0` | contextual, control |

## Separate actions

| Mode | Behavior |
|---|---|
| Default preparation | Read-only source/history checks, immutable experiment manifest and inactive `approval_request_NOT_APPROVED.json`; zero model requests and zero active approval |
| Budget approval only | Interactive actual identity, explicit design acknowledgment and exact `APPROVE DIAGNOSTIC24 BUDGET` phrase; actual laptop UTC recording time; creates one immutable separate budget, never generation |
| Execute/resume | Requires that existing exact budget and fresh `RUN DIAGNOSTIC24` confirmation each invocation; cancellation sends zero requests and makes no model probe |

The delivered preparation launcher uses the first mode only. Approval/execution must not be activated during development or CI. Do not treat the current build/test instruction, existing pilot consent, AI review or any template as a new inference grant. A later explicit budget decision and final local execution confirmation are still required. Approving this diagnostic design does not fabricate human translation QC: all dataset/human-review states remain pending.

## Budget, integrity and failure behavior

One fixed allowance exists per proposal under `recovery_artifacts/diagnostic-v2.1/<proposal>/`, shared across restarts and runtime versions. The approval binds the source plan, prepared spec, exact execution release/code fingerprints, model digest and24/2/1/512 limits. A runtime change cannot move the spent allowance to a new namespace. The separate guard root is `recovery_artifacts/diagnostic-v2.1-guards/<proposal>/`. Preserve both roots.

Every generation reservation is an immutable canonical-JSON record with a hash chain, exact slot/arm/payload binding, approval hash and recorded runtime hash. Its receipt is mirrored separately; a further independent dispatch witness is persisted before the single HTTP POST. There is no automatic retry, replacement request, token increase or refund. An interrupted arm stays spent, including a reservation interrupted before its POST. Resume advances to the next fixed arm; it never resends that reserved arm. Transport failures and malformed/English/mixed-language replies consume reservations.

Tail bookkeeping interrupted before dispatch or while publishing an outcome mirror may be completed append-only from its existing hash-verified record. This never changes an original charge/output or grants a request. Missing or changed historical records, primary records deleted beside independent witnesses, corrupted outcomes/receipts, approval/code/plan changes and corrupted previously published QC bundles block execution. Truncated/foreign/noncanonical ledger files are preserved and rejected. OS locks prevent concurrent runners on the same allowance.

Before every POST, the runner rechecks source/checkpoint/human-QC/history snapshots, source-bound manifest, code fingerprints, immutable approval/charge and GET-only model identity. It checks observed model identity again after the response; a mismatch quarantines that response and stops further dispatch. The unchanged client disables proxies and redirects and never starts Ollama or downloads a model. A reported generation-token overrun stops immediately. The original Arabic/math/numerical/reasoning-boundary validators remain unchanged; an additional literal-splice check preserves source-owned mathematics. No original field/checkpoint is materialized or overwritten by this experiment.

## Results and review

Every invocation publishes a new immutable report bundle and a latest-report pointer within the new diagnostic root. It reports reservations consumed, remaining **approved** requests, mechanical output count, per-slot charges, rejection/interruption categories, raw outcomes and artifacts requiring review. An unapproved preview explicitly reports zero authorized remaining requests and a separate unapproved proposed ceiling24. These are slot/arm fragments, not completed corpus fields or trajectories.

The blinded `blind_review.json`/HTML contains source context and candidate labels A/B, with no arm metadata or AI semantic suggestions. A private actual blinding key creates six control-A and six contextual-A displays independently of the counterbalanced dispatch order. The mapping remains stable across resumes. The operator's `unblinding_key.json` and accounting `report.json` stay separate: review the blind queue before opening them. Missing/failed outcomes remain unresolved and in the charged-request denominator; old pilot outputs never fill gaps.

GPT can review the resulting blind file as a separately identified AI assessor. That is not independent human QC or an accuracy measurement. No paired semantic wins/ties/losses, source-label adjudication or human approval is invented by software. Corrections remain separate proposals, original source reasoning and native labels stay unchanged, and training eligibility remains false.

## Verification and remaining local checks

Tests use disposable synthetic plan/proposal/model identities and fake responses; their active consent cannot validate against the real production bindings. Regression coverage includes caps, each arm's single attempt, cancellation, immutable identity/time, wrong model, interrupted reservation/POST/outcome publication, transport and metadata failures, source/output/report tampering, missing anchors, code upgrades, concurrent runners, English/mixed outputs, mathematics/numerals/boundaries, token overrun, balanced blind mapping and package/source fingerprints. Native Windows checks package the exact canonical blobs and verify all24 frozen payloads without approval, model access or scheduled tasks.

The initial diagnostic CI run [40168461707](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/40168461707) passed333 Linux tests but caught two Windows fingerprint failures. Fifteen existing runtime files lacked canonical-byte checkout attributes. The fix marks those paths `-text` and carries the same attributes into disposable packaging fixtures; it changes no runtime blob or frozen source bytes. A forced Windows/CRLF checkout regression checks every fingerprint and separately proves that manually changed CRLF bytes still fail. Hash validation is not normalized or relaxed.

The cloud can verify supplied source/plan bytes and construct a **static-only preparation**. It cannot replay private laptop history or confirm the currently installed model here. The laptop's default preparation must recheck its existing exhausted20 ledger, protected files and original9-attempt supervisor/checkpoints. Execution must later observe the exact installed model digest; no model needs to run for preparation.

Hash checks and independent local guard copies protect normal corruption, process interruptions and one-sided deletion/rollback. Complete coordinated rollback/deletion of every copy on the same machine cannot be proven absent without an external trusted monotonic service; preserve all evidence and never restore an older allowance. Model GET checks observe tag identity before/after requests; they do not provide an atomic server digest lock against an external process changing the tag in flight. Keep the installation stable; observed changes stop execution. These software limits do not establish translation quality. The diagnostic remains a small clustered development experiment, with all limitations in the original decision report.

No real generation, model download, scheduled task, training, unreviewed training-data export, main modification/merge or Global-MGSM access is authorized or performed by this development milestone.
