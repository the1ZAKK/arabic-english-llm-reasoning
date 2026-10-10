# Local ArabicPRM-T v2 drafting: Batch09–32

The supported runner uses installed Ollama `qwen3:4b`, frozen PRM800K sources,
Python 3.11 and the standard library. It creates AI drafts and pending bilingual
review artifacts. Every problem and step needs genuine human QC before training
export. It does not run training or use Global-MGSM.

For Windows with existing Batch09 checkpoints, follow
[WINDOWS_BATCH09_32.md](WINDOWS_BATCH09_32.md). The
[implementation audit](AUTOMATED_TRANSLATION_AUDIT.md) identifies verified
mechanical checks and inference still requiring local execution.

## Translation method

Python partitions each field into immutable source literals and prose fragments.
Math, numbers, source errors, LaTeX, paragraph boundaries and Markdown structure
remain literal. Ollama receives only prose in small JSON objects. Python inserts
validated Arabic fragments between the exact source literals and runs field and
batch validation. The model never reconstructs equations or math placeholders.

English inside protected LaTeX remains unchanged with the math. Nonlinguistic
fields are copied exactly without inference or an invented heading. Human review
must assess translation meaning and fluency.

## Local Linux execution

From an existing checkout on `research/arabicprm-v2-production`, with Ollama
running on localhost and the model installed:

```bash
python3 research/prm_arabic_english/resume_v2_local.py --preflight-only
python3 research/prm_arabic_english/resume_v2_local.py
```

Both commands default to Batch09–32, `frozen_staging`, `translated_drafts`
and `review_artifacts`. Repeat the drafting command after interruption; saved
valid work is reused. `bulk_draft_v2_translations.py` delegates to this runner.

The original `translation_checkpoint.json` is read-only. New validated
fields use `validated_fields_checkpoint.json`, bound to the original
checkpoint SHA256. Partial fragments and counters use `prose_checkpoint.json`.
Existing completed payloads, sources and human decisions are never replaced.

Pending fragments receive at most three attempts per invocation. Unresolved
fields are logged while independent fields and batches continue. Any incomplete,
failed, interrupted or unattempted batch makes the command exit nonzero.
No incomplete batch receives a new completed payload.

## Optional self-hosted workflow

`.github/workflows/v2-qwen-local-draft.yml` is manual only and requires a
trusted self-hosted Linux runner labeled `arabicprm-translation`, with Ollama
and `qwen3:4b` already installed. Select the research branch. The workflow
preserves untracked checkpoints and uploads evidence even on failure. It is
separate from the Windows launcher. No inference workflow was dispatched during
development.

## Provenance and review

Keep the model tag, endpoint and settings fixed when resuming a batch. The runner
records model digest, Ollama version, settings, request/response hashes, source
hashes and pending review status. Historical fields retain their original
provenance and unverified historical runtime details. Read
`resume_summary_latest.json` and `.md` for completed batches and outstanding
field IDs, hashes and errors.

Do not delete checkpoints to bypass failures, repair frozen source mathematics,
or set human decisions programmatically. Resolve source or provenance failures
without silently mixing sources or runtimes.
