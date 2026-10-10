# Windows execution: ArabicPRM-T v2 Batch09–32

Run these commands on the Windows laptop holding your existing
`translated_drafts`. The development environment cannot reach that laptop's
localhost Ollama or inspect its checkpoints. Python 3.11, Git, Ollama and the
installed `qwen3:4b` are sufficient; no Python packages or API credits are needed.
Keep Ollama running and the laptop awake during drafting.

## Update and execute

Stop any earlier translator before updating the checkout. The launcher refuses
concurrent translators, and the Python runner holds an OS file lock. Do not
delete checkpoints or use `git reset` or `git clean`.

In CMD, change to your existing repository directory, then run this setup and
offline preflight command. The `&&` operators stop at the first failed command:

```bat
git switch research/arabicprm-v2-production && git pull --ff-only origin research/arabicprm-v2-production && powershell -NoProfile -ExecutionPolicy Bypass -File research\prm_arabic_english\resume_v2_windows.ps1 -PreflightOnly
```

After preflight succeeds, start the unattended run:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File research\prm_arabic_english\resume_v2_windows.ps1
```

This processes Batch09 through Batch32 sequentially. It verifies and reuses valid
saved work and creates pending review artifacts for each complete draft. Repeat
the execution command after interruption; no cleanup is needed. A smaller range
can be selected with `-Start 9 -End 9`. `-ExecutionPolicy Bypass` applies only to
this PowerShell process.

The launcher verifies the exact research branch and repository origin. It never
changes branches or pulls code automatically. The Ollama preflight checks the
installed model digest and actual thinking-off behavior. It does not download
or change the model. Source or runtime provenance failures remain explicit.

## Preservation and recovery

The 256-record frozen selection is bound to pinned queue hashes. Selected record
hashes, canonical identity, lineage, splits, labels, masks, step counts and source
locks are checked. Staging is generated in a temporary directory and compared
byte for byte; only missing files are added.

The original `translation_checkpoint.json` remains byte-for-byte unchanged.
Valid fields are reused; an initial hash-named backup is also retained. New fields
use `validated_fields_checkpoint.json`, bound to the original checkpoint SHA256.
Rejected historical values remain in the original file and failure log; newly
validated candidates go into the separate resume file. Existing completed
payloads, frozen source copies and human-QC files are preserved.

Python owns every mathematical expression, number and structural boundary.
Ollama translates only prose fragments; it receives no math placeholders.
Python reconstructs fields from exact source literals and validates math, numeric
order, coverage and step boundaries. Malformed expressions and incorrect
reasoning remain as written. English inside protected LaTeX stays with the
expression. Pure math fields are copied exactly without inference or an invented
heading.

Generated math, numbers, Latin text, other scripts, control characters, new lines
and markup are rejected inside prose fragments. Each pending fragment receives
at most `-Retries 3` attempts per invocation by default. Small-group attempts
are followed by individual retries of failed fragments. Valid siblings remain
saved. Unresolved fields are logged and independent fields and batches continue.
An explicit rerun grants a new bounded budget; total attempt counters remain
auditable.

A complete AI draft requires every field to validate AND all review artifacts.
Incomplete batches receive no newly created `translations.json`. Any failed,
unresolved, interrupted or unattempted batch gives a nonzero exit. If Ollama is
unavailable, existing complete payloads can still receive review artifacts.

## Outputs and completion criteria

| Location | Evidence |
|---|---|
| `translated_drafts/preflight_latest.json` and `.md` | Offline source/checkpoint audit, outstanding field IDs and hashes |
| `translated_drafts/resume_summary_latest.json` and `.md` | Complete, incomplete, failed and unattempted batches; field/slot errors and attempt counts |
| `translated_drafts/prm800k_v2_batchNN/batch_status.json` | Validated/expected counts, unresolved and unattempted fields |
| `translation_checkpoint.json` | Original checkpoint, read-only |
| `validated_fields_checkpoint.json` | New validated fields bound to the legacy snapshot |
| `prose_checkpoint.json` | Validated fragments, source hashes, attempt/error ledger |
| `checkpoint_backups/` | Hash-named original checkpoint backup |
| `field_audit.jsonl`, `failures.jsonl`, `ollama_runtime.json` | Field validation, rejected values, request/response hashes, installed runtime evidence |
| `review_artifacts/prm800k_v2_batchNN/` | Bilingual HTML/queue, validation report, pending human-QC template |
| `translated_drafts/run_reports/`, `console_logs/` | Immutable invocation reports and Windows transcripts |

Batch-local filenames above live under
`translated_drafts/prm800k_v2_batchNN/`. Only
`ai_draft_validated_human_qc_pending` denotes a complete mechanical draft with
review artifacts. `source_audited_only` means no inference was performed.
`fields_validated` and `draft_payload_validated_pending_review_artifacts`
are intermediate states. Inspect the JSON reports after every run.

## Runtime and failures

Native `/api/chat` requests use exact-key JSON schemas, `think: false`,
`stream: false`, temperature 0, seed 42, `-NumCtx 4096`, `-NumPredict 2048`
and `-Timeout 600` seconds. One request runs at a time. Truncated or
thinking-bearing responses fail validation. Installed model digest, Ollama
version, OS/Python and available NVIDIA GPU information are recorded. Old
checkpoint fields retain explicitly unverified historical runtime details.

Defaults fit all actual source fragments under the conservative offline
request-size check. Actual speed, memory use and translation quality on the
16 GB RAM / RTX 2060 Max-Q 4 GB laptop are untested. If Ollama stops, restart it
and repeat the same command. Keep all checkpoint and report files. Do not bypass
source, digest or settings failures by deleting provenance or changing frozen
data.

## Required human review and verified checks

Every problem and step needs genuine bilingual review for meaning, fluency,
unchanged source errors and alignment with labels/masks. Mechanical checks do
not establish semantic equivalence. New templates have `human_review: false`,
`reviewer: null` and `decision: pending`; existing human decisions are
preserved. No training export or training runs.

```bat
python scripts\check_reproducibility.py
```

The offline suite covers actual Batch09 `train:6:6`, all 2,252 frozen fields,
request budgets, legacy bytes, bounded retries, interruptions, independent work,
provenance, local mock HTTP and pending-QC export blocking. Synthetic responses
are never saved as translations of actual source records. See
[the implementation audit](AUTOMATED_TRANSLATION_AUDIT.md) and
[machine-readable evidence](audits/unattended_pipeline_offline_validation.json).

API references: [chat](https://docs.ollama.com/api/chat),
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs) and
[thinking](https://docs.ollama.com/capabilities/thinking).
