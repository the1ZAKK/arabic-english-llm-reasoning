# Activate unattended Batch09–32 execution

The Windows supervisor is implemented; **its installation and real inference
on the user's laptop have not been verified**. The existing “ArabicPRM
execution” automation reads published reports. It cannot install software or
start the laptop's Ollama. Missing reports are not evidence of running or
completed translations.

## One local activation

Download `activate_v2_unattended_windows.cmd` and double-click it once on the
Windows laptop. It already targets
`C:\Users\brimz\Documents\arabic-english-llm-reasoning`. No CMD commands,
manual Git pull, Python packages, repeated retries or pasted logs are required
for ordinary operation. Complete a Git Credential Manager sign-in if setup
opens one. The laptop must remain powered on and signed in; the screen may
lock. After a restart, ordinary Windows sign-in lets the task resume.

The launcher downloads the installer over HTTPS from the exact research commit
`38bc9e759d8c71315281d42ae5c0e4371ca748bd` and checks SHA256
`84b30b5869588fc79f93ec064f0e44a259fb3200e19e8191f1275e2feb70e719`
before executing it. A failed download or hash check executes nothing. The
PowerShell execution-policy override applies to this process only.

Before activating, review what this permits:

1. Verify the existing checkout's exact research branch and both fetch/push
   origins. Fetch only that branch and verify the pinned runtime belongs to it.
   A different branch or repository stops installation without switching it.
2. Use installed Python 3.11 or newer, Git and Ollama. Verify GitHub push
   authentication using a dry run; no token is read, requested or stored by the
   supervisor. Git uses the user's existing credential helper.
3. Install a hash-verified immutable runtime under
   `translated_drafts/unattended_agent/runtimes/<commit>/`. This copies only a
   fixed allowlist of pipeline scripts, selected source queues and source locks.
   It does not replace the checkout, existing checkpoints or model files.
   The earlier runtime from a failed installation is retained. Retry ledgers
   and terminal run states are not reset when the pinned runtime is updated.
4. Run frozen-source/checkpoint preflight before inference. If an earlier
   translator is running, wait for it and defer preflight until it exits.
   Global source/runtime integrity failures stop inference. Batch-specific
   failures remain explicit while independently verified batches continue.
   Use a separately pinned `frozen_staging_unattended/<commit>/` cache instead
   of regenerating into the existing `frozen_staging` directory. Every active
   cache byte is compared with the trusted deterministic source generation.
5. Register and start `ArabicPRM-v2-Batch09-32` for the current Windows user,
   with `Interactive` logon and `Limited` privileges. No administrator elevation
   or Windows password is requested. The task checks recovery every five
   minutes and after sign-in, with concurrent instances suppressed.
6. Query only localhost Ollama. If necessary, start the existing Ollama
   executable with a loopback binding and one parallel request. Require the
   installed `qwen3:4b`; never download or replace the model automatically.
7. Resume valid Batch09 checkpoints, then continue through Batch32. Preserve
   mathematical and structural source literals in Python; translate prose only.
   Apply at most nine lifetime attempts per saved prose slot and three completed
   translation passes. Counters survive process failures and restarts. Runtime
   recovery has a separate six-failure limit. Exhausted work is recorded as
   unresolved, never invented or silently accepted.
8. Save checkpoints, failure evidence, logs and bilingual review artifacts.
   Publish compact audit JSON/Markdown only under
   `research/prm_arabic_english/audits/windows_execution/` on the research
   branch. These Git commits use a temporary index and preserve local staged
   changes and the checkout's HEAD. No force push, replacement branch or main
   update occurs. Raw rejected model responses and translation text remain
   local. The existing ChatGPT monitor checks published terminal results.

Only the fixed installed runtime runs; later branch code updates do not grant a
remote shell or execute arbitrary GitHub commands. Original
`translation_checkpoint.json` files remain unchanged. New validated fields use
separate checkpoints. Source hashes, mathematical validation and boundaries are
enforced. Human-QC records are preserved; new decisions remain pending. No
training export, training or Global-MGSM access occurs.

The Windows installation regression reproduces the earlier global failure when
legacy staging metadata or JSONL file separators use CRLF and the generator
produces LF. That defect is verified in a disposable fixture; the exact cause
on the user's laptop is still unconfirmed without a local preflight report.
The old staging is preserved and unused by the supervisor. Existing draft
source copies are accepted only if they match the exact canonical bytes or
their exact CRLF outer file envelope. Both SHA256 values are recorded. JSON
string contents, including escaped reasoning newlines and mathematical
expressions, cannot change. Mixed endings, BOMs, whitespace edits, source-lock
value changes and checkpoint hash/provenance changes are rejected. Frozen
queue validation still requires its original canonical raw-byte hashes; no
normalization or hash alias is applied to checkpoints or frozen sources.
Runtime validation hashes the exact Python-read file bytes through Git's stdin
interface, so long Windows filenames cannot bypass or break blob comparison.
Git long-path support is command-local; Windows registry and user Git settings
are not changed. Configuration roots use resolved physical paths, including
Windows short-name aliases.

If installation preflight remains blocked, the installer displays the actual
underlying error and attempts to publish a sanitized diagnostic to
`audits/windows_execution/runs/`. It does not overwrite the execution
`latest.json`/`.md`, change the monitor, expose model output or reset retry
counters. GitHub authentication/network failures can prevent publication; local
evidence remains saved.

## Automatic evidence

| Location | Contents |
|---|---|
| `translated_drafts/unattended_agent/latest_audit.json` | Latest supervisor status, pass budget, model digest and completion coverage |
| `translated_drafts/unattended_agent/state.json` | Restart ledger and report-publication errors |
| `translated_drafts/unattended_agent/logs/` | Timestamped preflight/translation logs and Ollama service output |
| `translated_drafts/unattended_agent/installation_preflight_diagnostic.json` | Underlying installation blocker, scope and hashes; never claims local inference |
| `frozen_staging_unattended/<commit>/` | Canonical source cache for this verified pinned runtime; original staging remains untouched |
| `translated_drafts/resume_summary_latest.json` and `.md` | Completed, failed, interrupted and unresolved batches/fields |
| `translated_drafts/prm800k_v2_batchNN/` | Original checkpoint, separate validated/prose checkpoints, slot request/response hashes, runtime evidence and batch status |
| `review_artifacts/prm800k_v2_batchNN/` | Complete bilingual draft HTML, queue, validation hashes and pending human-review template |
| Research branch `audits/windows_execution/latest.json` and `.md` | Automatically published compact audit; the monitor reads this |
| Research branch `audits/windows_execution/runs/` | Immutable timestamped audit history |

A successful task launch is distinct from real inference. A model being listed
in Ollama is also insufficient. New validated slot evidence records request and
response SHA256 values and available evaluation counts; batch runtime evidence
binds the installed model digest and settings. Complete batches additionally
require every field and review artifact to validate. Reused historical fields
retain explicitly unverified historical runtime details.

The supervisor can report `completed` only with all 24 batches and all 2,252
expected fields mechanically complete. `completed_with_unresolved` means the
automatic pass budget finished with work outstanding. `needs_attention` means
an integrity/runtime blocker or a recovery budget prevented further safe work.
None of these statuses completes human semantic review. Every problem and step
still needs bilingual human review for meaning, fluency and preserved source
mistakes.

To pause execution, disable `ArabicPRM-v2-Batch09-32` in Windows Task Scheduler.
Keep checkpoint and review files. Publication/authentication errors stay in the
local ledger and are retried separately without granting further model attempts.

## Verification and access limits

The supervisor's 126 offline tests passed on Linux and Windows. GitHub Windows
CI installed and executed a native scheduled task running frozen-source
preflight across all 24 batches. It performed no Ollama inference and no report
publication. The additional native installation regression used legacy CRLF
staging and draft source copies, the unchanged real Batch09 nonlinguistic
`train:1:5` field, a read-only checkpoint, the actual `train:6:6` source with an
exhausted test retry ledger, a prior-installation sentinel and a QC preservation
sentinel. All 24 batches / 2,252 fields passed preflight and protected fixture
bytes remained identical. This is offline fixture evidence, not the user's
checkpoint contents or real Qwen translations.
See [verified fix evidence](audits/windows_preflight_fix_validation.json) and
[previous activation evidence](audits/windows_activation_verified.json).
The replacement launcher and its exact pinned installer passed the
[final Linux/Windows checks](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/38909957473)
on 16 October 2026, including correct/incorrect hash checks, both native task
fixtures and a 281-character runtime path.
Actual laptop speed, GPU memory behavior and Qwen translation quality remain
untested until local execution is observed.

This session has no connection to the laptop's Windows shell or local Ollama.
The single launcher performs the authorized local installation; this session
verifies published reports after the laptop runs it.
