# Human QC gate and Arabic export

The QC12 draft is still pending human review. `export_reviewed_arabic.py` creates
a decision template and exports only accepted records once all decisions have
been completed. No code or synthetic test fixture approves the actual batch.

Decision files bind to the SHA256 of the exact review queue. A reviewer must
record their identity, a reviewed-on ISO date, accept/reject decisions and notes
(mandatory rejection reasons), and explicitly attest `human_review=true` after
completing review. Pending or revise decisions block all exports. If a translation
needs revision, version its payload, rematerialize it, and review the new queue
hash. Never carry approvals onto edited text. Keep a previous decision history.

Accepted Arabic records retain the original source IDs, problem IDs, split,
ratings, binary/neutral labels, masks and first-error information. Original English
problem text is retained for grouping validation, not replaced by an Arabic hash.
The exporter rechecks numeric sequences and protected spans, writes separate
train_ar/dev_ar JSONL files, and records source-queue/decision/output hashes.
Rejected records are excluded with reasons; no accepted records means no export.

`training_supervision(record)` returns zero-based annotated-step positions and
binary targets only for mask=1. Neutral positions never enter those target lists.
For model training, align all translated steps with tokenizer reward positions,
then index the differentiable reward logits by these returned positions before
BCE. This helper is CPU/data validation only: it is not a new training run or a
tested replacement for the pilot trainer. Export manifests explicitly state that
the current pilot trainer is incompatible. This tiny curated batch remains QC
material, not a production training corpus or final held-out evaluation.

Example template command (no training export occurs):

```bat
.venv\Scripts\python.exe research\prm_arabic_english\export_reviewed_arabic.py --make-template --decisions qc12_decisions.json --output-dir research\prm_arabic_english\data\prm800k_staging_1000\reviewed_arabic
```

After genuine human review has filled the decision file, omit `--make-template`
to export. Existing template files/output directories are refused to prevent
overwriting decisions or artifacts. Keep generated data within ignored staging
directories; commit reviewed metadata deliberately after inspecting it for scope
and attribution. Global-MGSM is not used by this stage.
