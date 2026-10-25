# Separate diagnostic24 runner — development and verification

This implements the fixed twelve-pair design from [the diagnostic decision](RECOVERY_V2_1_DIAGNOSTIC_DECISION.md). **The user's instruction authorizes building/testing, not generation.** No real diagnostic budget or approval identity/time has been created. The original pilot20 remains exhausted and untouched. The old frozen proposal remains historically `execution_implemented:false`; the new separate execution release records the implemented code without activating that proposal.

The proposed limits remain **24 generation reservations total, one per slot per arm, two across both arms per slot, 512 generated tokens per request**, on the exact original plan/model digest. All 24 source/context/payload identities and counterbalanced dispatch order remain bound to proposal `4327d769e30fdf2324d0d8000b4c828d3d311917993987af23c98687f1e0aa6d`. A source-only offline check reconstructs 2252 frozen fields and verifies all 24 proposed payload hashes without the private original plan or a model.

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

## Tested release and Windows preparation

Publication `9b002e3665ab4100336ba1cd0e78015676bbcb2f` passed [CI40169998501](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/40169998501): **335 tests each**, Windows527.371s / Linux72.018s, native diagnostic package, exact CMD hash, wrong-hash rejection and both forbidden CI modes. Scheduled-task integration was skipped. The preparation launcher remains unchanged.

Core commit `e26fdbfb84c8381a4cef400ed2f8969841157ccc` passed [Windows/Linux CI40169169137](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/40169169137): 334 tests per platform (Windows 484.814s, Linux 71.391s), native Windows canonical packaging and all 24 frozen payload checks. Both scheduled-task integration steps were skipped. This verifies software behavior, not translation quality or completed human QC.

| Item | SHA256 |
|---|---|
| Separate execution release, canonical JSON | `4ab6aca826555d7e0583840a0edcefd3606d796adc9727870ab0340f6facbb85` |
| Fingerprinted 42 code/data files, canonical hash map | `3688b2566717dec7de7ae07c8ca645bff80260bed22257965877c87c763e24c2` |
| Pinned Windows installer, exact bytes | `d93a59541a4764d61106add3522aa3df83f849df1415c072292e1c1c7f45fb75` |
| Windows preparation CMD, exact CRLF bytes | `3f11e87658bddfd6d59612c1dbe16e3e142dd97be581bb0b066627c68717db6f` |

Save [prepare_diagnostic24_windows_v2_1.cmd](prm_arabic_english/prepare_diagnostic24_windows_v2_1.cmd) as a `.cmd` file and double-click it. It uses the existing research checkout at `%USERPROFILE%\Documents\arabic-english-llm-reasoning`, fetches verified Git objects without checking out or modifying the branch, verifies the pinned installer and bootstrap helpers, installs immutable canonical runtime blobs and performs offline preparation. Its only mode is `prepare`: it has no automatic approval or execution route. The adjacent `.cmd.sha256` records the download checksum. Publication adds native CMD verification, wrong-hash rejection and explicit rejection of CI approve/execute modes.

Successful preparation prints `offline_preparation_zero_requests`, zero consumed reservations and zero remaining **approved** requests. The browser opens an empty blinded review preview; this is not a translation result or an approval form. The printed report directory contains `report.json` and `diagnostic_results.html` with accounting and `local_history_verified`. The cloud's static preparation explicitly sets that flag false; only your laptop can verify its private exhausted 20-request budget ledger and original supervisor/checkpoints.

Before future generation, the explicit decision must approve this separate proposal and tested release, original plan `446191b88e072c291ff34388a7fbb4166a6813639a63bb2ef54896431c6e7e4e`, `qwen3:4b` digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`, twelve pairs, fixed payload/order identities, at most 24 reservations total, two per slot/one per arm, at most 512 generated tokens, and no refunds after failure or interruption. **That decision has not been made by the build/test instruction.** The later local approval action records the person's actual identity and laptop UTC time, then a distinct execution action still requires `RUN DIAGNOSTIC24`. The preparation CMD cannot perform either action. Installed model identity is checked before generation, not asserted from this offline preparation.

## Budget, integrity and failure behavior

One fixed allowance exists per proposal under `recovery_artifacts/diagnostic-v2.1/<proposal>/`, shared across restarts and runtime versions. The approval binds the source plan, prepared spec, exact execution release/code fingerprints, model digest and 24/2/1/512 limits. A runtime change cannot move the spent allowance to a new namespace. The separate guard root is `recovery_artifacts/diagnostic-v2.1-guards/<proposal>/`. Preserve both roots.

Every generation reservation is an immutable canonical-JSON record with a hash chain, exact slot/arm/payload binding, approval hash and recorded runtime hash. Its receipt is mirrored separately; a further independent dispatch witness is persisted before the single HTTP POST. There is no automatic retry, replacement request, token increase or refund. An interrupted arm stays spent, including a reservation interrupted before its POST. Resume advances to the next fixed arm; it never resends that reserved arm. Transport failures and malformed/English/mixed-language replies consume reservations.

Tail bookkeeping interrupted before dispatch or while publishing an outcome mirror may be completed append-only from its existing hash-verified record. This never changes an original charge/output or grants a request. Missing or changed historical records, primary records deleted beside independent witnesses, corrupted outcomes/receipts, approval/code/plan changes and corrupted previously published QC bundles block execution. Truncated/foreign/noncanonical ledger files are preserved and rejected. OS locks prevent concurrent runners on the same allowance.

Before every POST, the runner rechecks source/checkpoint/human-QC/history snapshots, source-bound manifest, code fingerprints, immutable approval/charge and GET-only model identity. It checks observed model identity again after the response; a mismatch quarantines that response and stops further dispatch. The unchanged client disables proxies and redirects and never starts Ollama or downloads a model. A reported generation-token overrun stops immediately. The original Arabic/math/numerical/reasoning-boundary validators remain unchanged; an additional literal-splice check preserves source-owned mathematics. No original field/checkpoint is materialized or overwritten by this experiment.

## Results and review

Every invocation publishes a new immutable report bundle and a latest-report pointer within the new diagnostic root. It reports reservations consumed, remaining **approved** requests, mechanical output count, per-slot charges, rejection/interruption categories, raw outcomes and artifacts requiring review. An unapproved preview explicitly reports zero authorized remaining requests and a separate unapproved proposed ceiling 24. These are slot/arm fragments, not completed corpus fields or trajectories.

The blinded `blind_review.json`/HTML contains source context and candidate labels A/B, with no arm metadata or AI semantic suggestions. A private actual blinding key creates six control-A and six contextual-A displays independently of the counterbalanced dispatch order. The mapping remains stable across resumes. The operator's `unblinding_key.json` and accounting `report.json` stay separate: review the blind queue before opening them. Missing/failed outcomes remain unresolved and in the charged-request denominator; old pilot outputs never fill gaps.

GPT can review the resulting blind file as a separately identified AI assessor. That is not independent human QC or an accuracy measurement. No paired semantic wins/ties/losses, source-label adjudication or human approval is invented by software. Corrections remain separate proposals, original source reasoning and native labels stay unchanged, and training eligibility remains false.

After any eventual authorized run, use `LATEST_REPORT.txt` to locate the newest immutable bundle. Supply only `blind_review.json` to the initial assessor; retain `report.json` and `unblinding_key.json` privately until those assessments are recorded. GPT may complete an explicitly AI-only assessment, avoiding another manual pilot20 form. Save decisions/corrections in a new separate file with the assessor's actual status; never edit the immutable report bundle or impersonate a human reviewer. Genuine human review, source-error adjudication and wider-recovery approval remain separate gates.

The [separate offline assessment importer](DIAGNOSTIC24_ASSESSMENT_V2_1.md) now validates and seals those records before operator analysis. It is outside this pinned execution runtime; all existing runtime fingerprints and launcher bytes remain unchanged. No diagnostic data or actual assessor decisions have been produced by developing it.

## Verification and remaining local checks

Tests use disposable synthetic plan/proposal/model identities and fake responses; their active consent cannot validate against the real production bindings. Regression coverage includes caps, each arm's single attempt, cancellation, immutable identity/time, wrong model, interrupted reservation/POST/outcome publication, transport and metadata failures, source/output/report tampering, missing anchors, code upgrades, concurrent runners, English/mixed outputs, mathematics/numerals/boundaries, token overrun, balanced blind mapping and package/source fingerprints. Native Windows checks package the exact canonical blobs and verify all 24 frozen payloads without approval, model access or scheduled tasks.

The initial diagnostic CI run [40168461707](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/40168461707) passed 333 Linux tests but caught two Windows fingerprint failures. Fifteen existing runtime files lacked canonical-byte checkout attributes. The fix marks those paths `-text` and carries the same attributes into disposable packaging fixtures; it changes no runtime blob or frozen source bytes. A forced Windows/CRLF checkout regression checks every fingerprint and separately proves that manually changed CRLF bytes still fail. Hash validation is not normalized or relaxed.

The cloud can verify supplied source/plan bytes and construct a **static-only preparation**. It cannot replay private laptop history or confirm the currently installed model here. The laptop's default preparation must recheck its existing exhausted 20-request budget ledger, protected files and original supervisor, nine-attempt counters and checkpoints. Execution must later observe the exact installed model digest; no model needs to run for preparation.

Hash checks and independent local guard copies protect normal corruption, process interruptions and one-sided deletion/rollback. Complete coordinated rollback/deletion of every copy on the same machine cannot be proven absent without an external trusted monotonic service; preserve all evidence and never restore an older allowance. Model GET checks observe tag identity before/after requests; they do not provide an atomic server digest lock against an external process changing the tag in flight. Keep the installation stable; observed changes stop execution. These software limits do not establish translation quality. The diagnostic remains a small clustered development experiment, with all limitations in the original decision report.

No real generation, model download, scheduled task, training, unreviewed training-data export, main modification/merge or Global-MGSM access is authorized or performed by this development milestone.
