# QC24: expanded-source Arabic translation review

Current status: **16 ACCEPT, four REVISE, four REJECT/quarantine; no Arabic
training export**. Zakaria Brim reviewed this exact original queue. The requested
eight wording edits are in `../prm800k_qc24_r1/`; those four revised records await
final human acceptance. Original prose and source locks remain unchanged.
QC12 r1 remains the only exported Arabic batch. This batch adds 24 nonoverlapping trajectories (16 train,
8 dev), 201 annotated steps, and nine neutral/masked positions. Each split has
equal correct/incorrect trajectory quotas. Source errors and labels are preserved.

The expanded ingestion scanned a bounded 5,000-row phase2_train prefix at pinned
PRM800K revision `7ecc794703b2877f63226f2477a49b34f9b25163`: 21,531,669 downloaded
bytes, 4,890 eligible trajectories. A 500-problem staging set contains 454 train
and 122 dev trajectories. All 100 problem assignments from the prior 1,000-row
staging set are anchored, and its source records were verified unchanged before
expansion. New groups use an independent seeded SHA256 threshold. There is no
train/dev problem overlap. `problem_split_lock.json` records all 500 assignments.

This is still a bounded prefix, not a representative sample. Selected source
generations are 8 (473 records) and 9 (103 records); most trajectories are labeled
correct. QC24 is deliberately balanced and excludes the 12 IDs in QC12's source
lock. Its explicit 16-step ceiling is a review-budget choice and introduces length
selection bias; it does not truncate source trajectories. Both splits cover all
requested length/error-position/neutral-presence bins. The full 456,135,365-byte
source shard was not downloaded or checksum-verified. Prefix and output hashes
are recorded. Global-MGSM was not accessed.

## Versioned evidence

- `ingestion_manifest.json`: acquisition budget, eligibility/exclusions and hashes.
- `selection_manifest.json`: quotas, coverage, prior-ID exclusion and source hashes.
- `source_lock.json`: exact 24 source IDs, canonical hashes and inherited splits.
- `translations.json`: MSA prose using ordered per-string protected placeholders;
  translator identity, instruction and generation-setting limitations recorded.
- `translation_report.json`: all formulas/numbers match exactly; no normalization
  exceptions used; source supervision unchanged; human QC pending.
- `batch_audit.json`: compares every complete source record with the input queue,
  checks old-ID exclusion, complete HTML rendering, and absence of Arabic export.
- `replay_verification.json`: offline replay matched raw prefix, both staging
  files, both source queues and the materialized review queue byte for byte.
- `human_qc_pending.json`: exact-queue-bound decisions, all pending, human_review=false.
- `human_qc_original.json` and `human_review_2026-10-05.txt`: supplied human review
  of the original queue, with 16 accepts, four revision requests and four rejects.

## Human review

Review every problem and annotated step against English. Record ACCEPT, REVISE
with precise Arabic corrections, or REJECT with a reason using record numbers
1–24 (train 1–16; dev 17–24). Supply reviewer identity and review date. Review
notes flag source wording or annotation concerns; translation QC cannot silently
repair those. Suspected source-label issues need separate adjudication before use.
Incorrect mathematical reasoning must remain as supplied. Preserve source records,
IDs, hashes, masks, labels and step boundaries. Nine neutral steps stay masked.

All records remain blocked from training. The export gate was exercised with the
pending decision file and correctly refused it. Only human-reviewed decisions
bound to the final queue hash may permit export. Revisions require a new queue
version and updated review history. Never transfer QC12 approval to this batch.

Active source-annotation quarantines are now stored in the central
`../../source_quarantine.json`. New batch selection automatically excludes their
exact trajectory IDs; export refuses accepting those IDs. Source records and
supervision are never relabeled. Quarantine resolution requires separate human
source-annotation adjudication.

## Replay from repository root

Use fresh output directories for every generated artifact. Regenerate the original
1,000-row/100-problem source staging set unchanged before using it as the anchor.
Its manifest SHA256 must match `ingestion_manifest.json`'s anchor hash. Native
source queue records and the source lock are authoritative; never refreeze them.

The selection commands below describe the original pre-QC batch at commit
`d829cd4`. Current selection excludes active quarantines, so it will select a
different new batch. Historical source-queue reproduction must use that original
selection version in an isolated checkout, or the preserved frozen queues. Use
current guarded export code for any training export. The r1 materialization uses
the same preserved source queues and source lock, never a fresh selection.

```bat
.venv\Scripts\python.exe research\prm_arabic_english\prm800k_ingest.py --max-rows 5000 --max-bytes 67108864 --max-problems 500 --split-anchor-dir research/prm_arabic_english/data/prm800k_staging_1000 --output-dir research/prm_arabic_english/data/prm800k_staging_5000_replay
.venv\Scripts\python.exe research\prm_arabic_english\prepare_translation_batch.py --source-dir research/prm_arabic_english/data/prm800k_staging_5000_replay --output-dir research/prm_arabic_english/data/prm800k_staging_5000_replay/translation_batch_qc24 --train-count 16 --dev-count 8 --max-steps 16 --exclude-source-lock research/prm_arabic_english/translation_batches/prm800k_qc12/source_lock.json
.venv\Scripts\python.exe research\prm_arabic_english\materialize_translation_batch.py --queue-dir research/prm_arabic_english/data/prm800k_staging_5000_replay/translation_batch_qc24 --assets-dir research/prm_arabic_english/translation_batches/prm800k_qc24 --output-dir research/prm_arabic_english/data/prm800k_staging_5000_replay/translation_batch_qc24/arabic_draft
.venv\Scripts\python.exe research\prm_arabic_english\render_translation_review.py --input research/prm_arabic_english/data/prm800k_staging_5000_replay/translation_batch_qc24/arabic_draft/review_queue.jsonl --output research/prm_arabic_english/data/prm800k_staging_5000_replay/translation_batch_qc24/review.html
```

Replay materializes the versioned prose; it does not call a translation service or
promise identical output from rerunning a generative model. Staging/raw source
files are ignored by Git. Preserve upstream MIT attribution (`LICENSE.prm800k`)
and underlying MATH attribution when redistributing derivatives. No new model
training or performance evaluation was performed in this expansion.
