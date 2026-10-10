# Windows Ollama resume: ArabicPRM-T v2 Batch09-32

Run this on the Windows laptop that holds `translated_drafts`. ChatGPT's cloud
terminal is a different machine and cannot reach that laptop's localhost.
The runner uses the already-installed `qwen3:4b`; it does not download a model.
Python 3.11 or newer is sufficient; the runner uses only the standard library.

## Start after the existing translation process exits

If the original Batch09 command is still printing record/step progress, let it
finish first. Do not run two translators against the same checkpoint. The
PowerShell launcher also refuses to start while either translator is running.

In CMD, from the existing checkout:

```bat
cd /d C:\Users\brimz\Documents\arabic-english-llm-reasoning
git switch research/arabicprm-v2-production
git pull --ff-only origin research/arabicprm-v2-production
powershell -NoProfile -ExecutionPolicy Bypass -File research\prm_arabic_english\resume_v2_windows.ps1 -PreflightOnly
powershell -NoProfile -ExecutionPolicy Bypass -File research\prm_arabic_english\resume_v2_windows.ps1
```

Stop if Git reports an error or the offline preflight exits with an error. No
reset, clean, checkpoint deletion, or training command is needed. Use your actual
checkout path if it differs. `-ExecutionPolicy Bypass` applies to this one
PowerShell process; it does not change the machine's persistent policy.

The final command runs Batch09 through Batch32 sequentially. Batch09 is reused
if its completed payload passes the checks. Otherwise its valid checkpoint fields
are reused. For a smaller range, pass `-Start 9 -End 9`, then advance the range.
Repeat the same command after an interruption: successful batches are verified
and reused; failed batches retain their saved work and are attempted again.
The new runner holds an OS file lock that releases automatically on process exit.

## What is checked and preserved

- The 256-record frozen PRM800K selection is bound to pinned train/dev queue
  SHA256 values. Each source record's canonical SHA256, source revision/file,
  lock record identity, order, and split are checked. Staging is regenerated in a
  temporary directory, compared byte for byte, and only missing files are added.
- Legacy schema-1 checkpoints retain their existing model, endpoint, batch, and
  source-hash provenance. A changed provenance fails closed. Valid fields are
  retained. The initial checkpoint is backed up by SHA256 before any update;
  rejected old fields are logged with their text, and only replaced after a new
  candidate passes. No completed translation or review file is overwritten.
- Delimited math, inline LaTeX, complete LaTeX environments, nested command
  arguments (including incomplete source fragments), numeric sequences,
  mixed math/number token order, and bare operator
  sequences are checked. The runner rejects empty or predominantly untranslated
  Latin prose, unexpected CJK/Hangul, injected thinking/role markers, added
  headings/list boundaries, and changed step counts. It preserves source errors,
  ratings, labels, masks, and train/dev assignments.
- Ollama's native `/api/chat` uses a JSON schema, `think: false`, `stream: false`,
  temperature 0, seed 42, a 4096-token context, a 2048-token output budget, and one
  request at a time. Truncated responses fail validation. The exact installed
  model digest, Ollama version, runtime options, OS/Python version, and available
  NVIDIA GPU information are recorded. Original checkpoint fields created before
  this audit have **unverified historical runtime details**; they are not
  retroactively attributed to the newly recorded settings.

These are conservative mechanical checks. They do not establish translation
equivalence, Arabic fluency, or mathematical correctness. Genuine bilingual
human review remains necessary, including checking that deliberately incorrect
source reasoning was not repaired. A flagged completed payload is preserved and
reported as failed; it is not silently replaced.

## Outputs

| Location | Contents |
|---|---|
| `translated_drafts/prm800k_v2_batchNN/` | Frozen source copies, resumable checkpoint, completed AI payload, runtime evidence, checkpoint backups, per-field failure log |
| `review_artifacts/prm800k_v2_batchNN/` | Bilingual `review.html`, `review_queue.jsonl`, hash-bound `validation_report.json`, pending `human_qc_pending.json` |
| `translated_drafts/resume_summary_latest.json` | Latest per-batch result; failed batches remain explicit |
| `translated_drafts/run_reports/` | Immutable report for every invocation |
| `translated_drafts/failures.jsonl` | Run/batch failures, including source or checkpoint validation failures |
| `translated_drafts/console_logs/` | Windows console transcripts |

Every successful batch receives its review artifacts immediately. Existing QC
templates with the matching queue hash are preserved verbatim. New templates
always have `human_review: false`, `reviewer: null`, and `decision: pending`.
The runner never invokes a training exporter or trainer, and never accesses
Global-MGSM. A successful exit means AI drafting and mechanical validation only.
Failures in one batch are logged while later batches continue; any failure makes
the overall command exit nonzero. A run-level frozen-selection failure stops the
run before inference. Ctrl+C saves a run report and leaves previous checkpoints.

## Diagnose a failure

Read the latest summary and that batch's `failures.jsonl`. Keep all checkpoint,
backup, and payload files. Do not delete `translated_drafts` to restart. Use the
same model tag and endpoint as the checkpoint. A model digest/settings mismatch
needs a deliberate provenance decision, rather than mixing runtimes silently.
If the conservative context-budget check fails, explicitly use `-NumCtx 8192`;
changing settings after the new runner has already saved fields will fail its
runtime guard. Start with the intended settings and keep them fixed per batch.

## Verification on the development workspace

```bat
python -m unittest discover -s research\prm_arabic_english -p test_resume_v2_local.py -v
```

Tests use temporary synthetic fixtures and a local mock HTTP server. They check
checkpoint preservation, failed-step recovery, completed-payload reuse, frozen
source mutations, token/math/language/boundary guards, pending-QC export blocking,
hash-bound idempotent artifacts, runtime-digest guards, concurrent-run locking,
and the native Ollama request format. They do not run Qwen3, train a model, or
claim that the actual Windows batches have finished.

The [frozen-source audit](audits/batch09_32_frozen_source.json) verifies the
Batch09-32 source queues: **192 trajectories, 151 train / 41 dev, 2,060 reasoning
steps, and 2,252 fields including problems**. It records no execution or inspection
of the laptop's checkpoint. The full upstream shard checksum is a frozen lineage
reference; this audit rehashes the versioned selected queues and canonical records.

API reference: [Ollama chat](https://docs.ollama.com/api/chat) and
[thinking controls](https://docs.ollama.com/capabilities/thinking).
