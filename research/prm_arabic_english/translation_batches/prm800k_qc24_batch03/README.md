# QC24 Batch03: pending bilingual human QC

This is the third review batch, following QC12 and QC24 r1. **All 24 records
remain pending and ineligible for training.** Automated checks do not approve
translations or adjudicate source supervision.

| Split | Records | Correct / incorrect trajectories | Steps |
|---|---:|---:|---:|
| Train | 16 | 8 / 8 | 117 |
| Dev | 8 | 4 / 4 | 62 |
| Total | 24 | 12 / 12 | 179 |

There are 171 supervised steps and eight masked neutral steps. Selection inherits
the fixed source-problem splits from the 5,000-row staging prefix, excludes all
36 prior-batch source IDs and active quarantines, and limits this curated review
workload to 16 annotated steps per trajectory. Seed 42 and the existing categorical
coverage selector reproduce the chosen records exactly. This is a bounded-prefix
curated batch, not a representative corpus sample. Train covers early/middle/late
first-error bins; dev has early/middle errors and no late-error example.

## Frozen artifacts

- `source_lock.json` and `selection_manifest.json`: exact frozen source/selection evidence.
- `translations.json`: Arabic drafts and translation provenance; formulas and numbers use protected placeholders.
- `translation_report.json`: materialization preservation checks and exact queue hash.
- `automated_review_flags.json`: nonbinding observations for records 5, 7, 10, 13, 16 and 18.
- `human_qc_pending.json`: 24 pending decisions, `human_review=false`, no reviewer attestation.
- `batch_audit.json`: real-artifact preservation, selection replay, review-page and export-gate checks.
- `LICENSE.prm800k`: retained upstream attribution; source terms also apply.

| Artifact | SHA256 |
|---|---|
| Source lock | `330ce7f491b0ae162ea5b4a635abf8a14a0bf9cbe7ebd98a5eeda3e32e57f2b3` |
| Translation payload | `31c7b549dc213f5eb1e4f1cdcea8aa4128fbc665e16d7a7e24fbb7091caff721` |
| Review queue | `d79089e604cf842fe5e2306af31ae7370f01c040d09e4d05c0f5c6f436282413` |

Original source records and their hashes, pair IDs, labels, masks, step boundaries
and split assignments match staging exactly. Protected spans/numeric sequences
passed with zero source normalization exceptions. Intentional source errors are
preserved. Record 13 interprets the unambiguous prose typo “divisible so 3” as
“divisible by 3” in Arabic; the exact English typo remains in provenance and is
explicitly noted for human review. No source annotation was repaired or relabeled.

## Review required

Render and review **all 24 problems and every annotated step**, using Batch03's
new numbering. Earlier QC24 record numbers and decisions do not apply here.
Return ACCEPT, REVISE with exact Arabic corrections, or REJECT with reasons per
record. The six flagged records need particular scrutiny of source annotations;
the observations make no automatic rejection or quarantine decision.

The queue hash displayed on the HTML page must match the decision file. A real
export attempt against the pending template returned
`Explicit human-review attestation is required` (exit code 2). No Batch03 training
export directory was created. Existing four quarantines remain unchanged.

After human review, preserve the submitted decisions in a new file. Any revision
requires a separately versioned payload and queue followed by review of that
new hash. Export only when every record has a final accept/reject decision and
all automated preservation checks pass. Accepted additions belong to a future
corpus version, not an edit of approved corpus v1.

## Offline reconstruction commands

Run from the repository root with the pinned staging source available. Use a new
directory for each replay. Selection inherits existing splits without resampling.

```bat
.venv\Scripts\python.exe research\prm_arabic_english\prepare_translation_batch.py --source-dir research/prm_arabic_english/data/prm800k_staging_5000 --output-dir research/prm_arabic_english/data/prm800k_staging_5000/translation_batch_qc24_batch03_replay --train-count 16 --dev-count 8 --seed 42 --max-steps 16 --exclude-source-lock research/prm_arabic_english/translation_batches/prm800k_qc12/source_lock.json --exclude-source-lock research/prm_arabic_english/translation_batches/prm800k_qc24/source_lock.json
.venv\Scripts\python.exe research\prm_arabic_english\materialize_translation_batch.py --queue-dir research/prm_arabic_english/data/prm800k_staging_5000/translation_batch_qc24_batch03_replay --assets-dir research/prm_arabic_english/translation_batches/prm800k_qc24_batch03 --output-dir research/prm_arabic_english/data/prm800k_staging_5000/translation_batch_qc24_batch03_replay/arabic_draft
.venv\Scripts\python.exe research\prm_arabic_english\render_translation_review.py --input research/prm_arabic_english/data/prm800k_staging_5000/translation_batch_qc24_batch03_replay/arabic_draft/review_queue.jsonl --output research/prm_arabic_english/data/prm800k_staging_5000/translation_batch_qc24_batch03_replay/review.html --batch-id QC24-Batch03
```

The documented selection/materialization replay passed with the identical queue
SHA256; Windows `fc /b` returned `FC: no differences encountered`.

Generated queues and HTML remain local. Versioned JSON is protected from Git
newline conversion because approvals and provenance bind exact file hashes.
Exact decoding settings and deployment version were not independently recorded;
the payload records this limitation. No new training run was performed.
