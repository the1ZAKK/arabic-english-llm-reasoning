# Run ArabicPRM-T v2 Batch09–32 with local Qwen (no OpenAI API credits)

This creates **AI Arabic drafts** only. Genuine bilingual human QC remains required.
Source IDs, train/dev splits, labels, masks, and steps are frozen. Never export
unreviewed records or run QLoRA using this output.

For **Windows 11 with the installed `qwen3:4b` and an existing Batch09
checkpoint**, use the [Windows Batch09-32 resume guide](WINDOWS_BATCH09_32.md).
Its launcher safely reuses completed batches and automatically creates pending
bilingual review artifacts. The older instructions below describe the Linux workflow.

## Hardware and cost

Ollama runs an open-weight Qwen2.5 7B Instruct model locally. You need an
appropriate machine, ideally a GPU with about 8–16 GB or more VRAM depending
on quantization/context; CPU inference is possible but much slower. Model
weights must be downloaded, and electricity/hosting are not free. The
local endpoint avoids **OpenAI API usage charges**, not all computing costs.

## Recommended: local shell

1. Install Ollama from https://ollama.com/download and start its service.
2. Download the model: `ollama pull qwen2.5:7b-instruct`.
3. In a clone of the repository, switch to `research/arabicprm-v2-production`.
4. Verify `curl http://127.0.0.1:11434/api/tags` returns available models.
5. Run from the repository root:

```bash
export PYTHONPATH=research/prm_arabic_english
python3 research/prm_arabic_english/stage_v2_remaining_batches.py --output-dir frozen_staging
python3 research/prm_arabic_english/bulk_draft_v2_translations.py \
  --staging-root frozen_staging --output-root translated_drafts \
  --start 9 --end 9 \
  --model qwen2.5:7b-instruct --base-url http://127.0.0.1:11434/v1
python3 research/prm_arabic_english/materialize_translation_batch.py \
  --queue-dir translated_drafts/prm800k_v2_batch09 \
  --assets-dir translated_drafts/prm800k_v2_batch09 \
  --output-dir batch09_review
```

For each successful batch, render its bilingual review using
`render_translation_review.py`, and create a pending QC template with
`export_reviewed_arabic.py --make-template`. Never set `human_review: true`
without genuine independent human decisions.

The translator refuses to overwrite an existing output batch. For later
batches, run `--start 10 --end 10`, then advance sequentially. For
long-running jobs, smaller ranges minimize lost work if an inference response
fails validation.

## Optional: GitHub Actions self-hosted runner

The workflow `.github/workflows/v2-qwen-local-draft.yml` is designed for a
**self-hosted Linux runner** with the label `arabicprm-translation`, an
already-running local Ollama service, and the model already pulled.
GitHub-hosted runners do not automatically provide the required local model or
GPU. Configure a trusted self-hosted runner in Repository Settings → Actions →
Runners, then enable the workflow for manual runs (the workflow must be
present on the repository default branch to appear for manual dispatch).
Select the research branch and run Batch09 first.

Security: do not expose a self-hosted runner to untrusted pull requests, and
keep Ollama bound to localhost. The workflow does not need `OPENAI_API_KEY`.

## Failure rules

- JSON mismatch, missing Arabic, reordered math placeholders, changed number
  sequences, or changed step counts: translation attempt must be revised.
- Repeated model errors: reduce the batch size or adjust the inference model.
- No generated file or successful materialization: do **not** claim a batch
  translated or accepted.
- Do not use `Global-MGSM` to tune translations, checkpoints, or thresholds.

## Scientific reporting

Document Ollama/Qwen model name and tag, hardware, decoding configuration,
source hash, review queue hash, validation results, and reviewer decisions.
The local-model drafts may differ from previous GPT-generated draft batches;
record this translation-provenance change as a potential confounder.
