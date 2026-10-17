# Bounded recovery-v1 laptop execution

This separate `pilot-execution-v1` workflow implements the user's explicit 20/2/512 pilot approval, with an additional affirmative confirmation on the Windows laptop. Engineering and CI use synthetic responses only. No approval identity or approval timestamp is shipped in the repository. The older preparation workflow and its non-authorizing proposal remain unchanged.

## Fixed scope

| Binding | Exact value |
|---|---|
| Branch | `research/arabicprm-v2-production` |
| Plan SHA256 | `446191b88e072c291ff34388a7fbb4166a6813639a63bb2ef54896431c6e7e4e` |
| Raw original plan file SHA256 | `559ec98308f8912f1431d0366ed6536f15e0564a1b0f486f928bec96f3a27d0c` |
| Model | `qwen3:4b` |
| Model digest | `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7` |
| Total lifetime pilot reservations | **20**, shared by every restart |
| New attempts per unresolved slot | **2**, shared by every restart |
| Generated tokens per request | **512** |

The original `recover_v2.py` and all 13 plan-bound code hashes are unchanged. The 814-file protected snapshot, 2252 frozen source fields, 1075 validated fields, 1177 unresolved fields / 2005 slots, source locks, original checkpoint bytes, exhausted terminal supervisor, nine historical attempts per slot and existing human-QC records are verified by the original preparation audit. The original `budget_NOT_APPROVED.json` stays inactive and byte-preserved.

## One double-click workflow

Download the final pinned `execute_recovery_pilot20_windows_v1.cmd` release. Keep the existing research branch and prepared plan on the laptop. The existing Git/Python 3.11+ installation and already-running Ollama service are required. The default repository path is `C:\Users\brimz\Documents\arabic-english-llm-reasoning`.

1. Double-click the CMD file. Its .NET SHA256 check authenticates the exact downloaded installer before it runs. The installer fetches Git objects without checking out files or switching branches. It verifies the exact pinned research commit and helper SHA256 values, then installs a separate canonical Git-blob runtime. Existing runtime folders must match exactly and are never repaired in place.
2. The complete laptop source/checkpoint/plan/history audit runs again. Model verification uses only `/api/tags` and `/api/version` GETs. Missing Ollama, a wrong model digest or changed protected bytes blocks execution; the launcher never starts or downloads Ollama/model files.
3. Review the displayed plan, digest, total cap, per-slot cap, token cap, already consumed reservations and remaining allowance. On first use, enter your actual name/approval identity. It is recorded as entered, with the laptop account and actual UTC confirmation time from the laptop clock; the repository supplies neither.
4. Type **`EXECUTE PILOT20`** exactly to execute. A blank response, any other text, EOF or cancellation before this confirmation causes zero new generation requests and creates no new active approval. On a resumed run, the existing identity/time/budget are preserved, displayed, and the same affirmative phrase is required again.
5. Leave the window open. Each result and the final HTML/JSON report location is printed. The CMD window pauses on completion or failure. If stopped or interrupted, reopen this same launcher. A report shows spent reservations and accepted fragments; no counters are reset. If no requests or eligible slots remain, it reports results without asking to generate.

There is no unattended/`--yes` mode or environment-variable consent bypass. A real interactive console is required by the execution entry point. CI's `PackageOnly` and bootstrap verification modes cannot reach the execution entry point. No scheduled task, model replacement/download, remote inference, training or training export is included.

## Immutable consent and safe resume

`control/consent.json` contains the exact existing `arabicprm_recovery_budget` schema nested inside a separate evidence record. The actual approver and UTC timestamp are created only after the affirmative laptop response. The fixed budget ID is deterministically derived from this plan; changing an ID cannot create another allowance. The identical budget bytes are installed at the original fixed `run/approved_budget.json` location with create-or-verify semantics.

Before every HTTP generation request, the unchanged runner durably appends a hash-chained reservation. The wrapper verifies the original journal, strict aggregate/per-slot caps, original protected snapshot, immutable consent/approval, exact request hash and installed model identity. It then appends and fsyncs a separate dispatch witness and atomically persists its journal/witness prefix checkpoint **before** POST. A transport failure, quality rejection, crash before POST or termination during POST consumes that reservation. Requests are never automatically reissued or refunded. English-only and mixed-script output still fails the unchanged Arabic-only validation; source-owned math/numbers and reasoning boundaries are retained by the unchanged assembly/validation code.

Resume verifies journal source/request/approval bindings, dispatch witness hash chains and persisted journal prefixes. Deletion, truncation, alteration or rollback of a recorded prefix blocks inference. Accepted artifact hashes and rebuilt expected artifacts are checked before further dispatch; accepted field bytes are never overwritten. Missing consent beside existing run files cannot silently become a new allowance. An empty journal is created only for the newly confirmed, unspent budget so interruption between metadata GETs and the first reservation remains resumable.

The witnesses/checkpoints are local files, not an external signed service. They detect corruption and rollback while surviving evidence remains. Deliberate deletion or coordinated rollback of **all** local evidence cannot be proved absent by local hashing alone. Preserve the entire recovery folder and reports; never delete records to fix an error. Integrity errors stop execution and require investigation, without an automated reset path.

## Dispatch order

The exact fresh first-pass list remains in [the preparation readiness audit](RECOVERY_PILOT_READINESS_V1.md#exact-fresh-initial-dispatch). A fresh uninterrupted pilot attempts its first 20 distinct jobs once, starting `09/dev:0:4/s1`, then `09/dev:0:4/s2`. Quality failures advance to the next job. Transport outages stop the invocation. On restart, pending jobs are rebuilt in original plan order; accepted slots and two-attempt slots are skipped. Earlier failures with one attempt may therefore get their second attempt before untouched slots. Every old reservation still counts toward the same ceiling of 20.

## Reports and human review

All paths below are relative to the laptop repository. Replace `<plan>` with the plan SHA256 above.

| Artifact | Location |
|---|---|
| Latest HTML report pointer | `recovery_artifacts/recovery-v1/pilot-execution-v1/<plan>/LATEST_REPORT.txt` |
| HTML and machine-readable results | `recovery_artifacts/recovery-v1/pilot-execution-v1/<plan>/reports/<report-sha>/pilot_review.html` and `report.json` |
| Immutable actual laptop consent | `recovery_artifacts/recovery-v1/pilot-execution-v1/<plan>/control/consent.json` |
| Dispatch witnesses and resume checkpoint | Same `control/` folder: `dispatch_witness.jsonl`, `checkpoint.json` |
| Original recovery journal and budget | `recovery_artifacts/recovery-v1/<plan>/run/attempts.jsonl`, `approved_budget.json` |
| Completed new fields, when available | Same `run/` folder: `fields/`, `summary.json` |
| Fully recovered batch review, when available | Same `run/` folder: `review_artifacts/<batch>/review.html`, `human_qc_pending.json` |

Reports show cumulative attempts consumed, remaining allowance, per-slot counters, mechanically accepted Arabic fragments, original English, model candidates, rejection categories, and crash-reserved requests with no outcome. Accepted partial fragments remain in the journal/report even if a whole field cannot yet be assembled. The HTML/JSON report is available after ordinary completion, transport stops and handled interruption. A hard process kill can prevent a final report; reopening the launcher replays durable records before any new confirmation. Cancellation of that prompt produces a fresh report without generation.

Human semantic QC remains **pending** for every automatic draft. Bilingual review must check each completed field and its full reasoning context against the frozen English, including any literal source mistakes. Automatic validation and CI do not establish translation quality or completed human QC. No draft becomes training eligible through this launcher.

## Validation and release

The test suite covers synthetic approval identities/timestamps, exact caps and request ordering, zero-request cancellation, wrong model digest (including drift between requests), tampered plans/checkpoints, corrupted/deleted/rolled-back ledgers and witnesses, immutable approval, transport failures, hard termination, safe resume, accepted artifact preservation, English/mixed script rejection, mathematics/numbers/boundaries and human-QC status. Windows additionally parses the installer and installs the separate package from canonical blobs without reaching consent or inference. The final launcher is pinned only after implementation CI passes, followed by positive and negative native CMD download/hash checks.

The first implementation CI ([39019880026](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39019880026)) passed Linux and exposed two Windows issues: a test hashed checkout CRLF instead of canonical Git bytes, and native backslashes prevented recognition of the mutable timestamped `batch_status.json`. The fix normalizes only new workflow receipt paths, compares all substantive batch-status fields, and continues to hash accepted artifacts and QC records. An explicit Windows-path regression and wrong-branch regression were added. No historical file or original validation rule was changed.

Release commit, CI links and launcher SHA256 are published with the tested launcher. The final confirmation is performed personally on the laptop; development and CI do not execute any real Ollama generation.
