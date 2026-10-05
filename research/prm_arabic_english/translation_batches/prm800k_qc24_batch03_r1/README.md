# QC24 Batch03 r1: only record 21 awaits final acceptance

Zakaria Brim reviewed the original 24-record queue on 2026-10-05: **17 ACCEPT,
six REJECT/source-annotation conflicts and one REVISE**. Original supplied text
and decisions remain in the parent Batch03 directory. Records **5, 7, 10, 11,
16 and 18** are now active quarantines with the exact human reasons. All source
labels/provenance remain unchanged. There are ten active quarantines in total.

This revision removes **only** the literal `[* 1]` through `[* 9]` markers from
record 21's Arabic step 2. It preserves all remaining characters, including
mathematics, punctuation and whitespace. The introductory neutral step remains
untouched. The full reasoning remains one negatively rated annotated step:

| Field | Preserved value |
|---|---|
| Record ID | `prm800k_b1fe0ed874975c53b348eda00f810cd5ee7ba015b660a3442f84308cb271a400` |
| Source record SHA256 | `dc05c19873824349a58c078be2acb090bc77c39cb289e84c5bdef98e34c1af7f` |
| Split / annotated steps | dev / 2 |
| Source ratings | `[0, -1]` |
| Labels / masks | `[null, 0]` / `[0, 1]` |

All 23 other translated rows are exactly unchanged; only JSONL line/record 21
differs. Original English still includes the markers. The source normalization is
a comparison copy, scoped to this exact source ID and step 2. It grants no new
acceptance and cannot remove markers from other records/steps or relax the
protected-math/numeric checks. Eight regression tests passed.

## Queue hashes and approval state

Original queue:
`d79089e604cf842fe5e2306af31ae7370f01c040d09e4d05c0f5c6f436282413`.

Revised complete 24-record queue:
`a58576d8eae1ec57843c4a9febb0c676684bd7020004a6616facd748cf54ea1a`.

Payload:
`d3c3ea2a3c3cf5366bb7eae798ecb3faebd33e70e31167fbd7897eb9f4ed18b5`.

`human_qc_r1_pending.json` binds the revised queue. It retains the original 17
acceptances and six rejections for unchanged records, with the original decision
hash and a verified unchanged-row list. Record 21 is pending with no final review
date, and `human_review=false` until its final human decision. Only record 21 is
shown on the new review page. No acceptance was carried onto the edited text.

Both actual export gate checks refused: the original decisions contain REVISE;
the revised decisions lack final human attestation. No Batch03 training export
directory was created. The reviewed corpus v1 remains unchanged at 32 records;
regeneration under the expanded quarantine catalog matched its original records,
registry and Arabic output hashes. Its four-quarantine snapshot remains historical.

## Versioned evidence

- `source_lock.json`, `LICENSE.prm800k`: exact copies from the original batch.
- `translations.json`: versioned payload, changed only at record 21 step 2 plus revision metadata.
- `requested_changes.json`: nine literal removals, source/step hashes and human instruction evidence.
- `human_qc_r1_pending.json`: 17 accept, six reject, record 21 pending; export blocked.
- `revision_precheck.json`: marker-only comparison, preserved historical hashes and quarantine amendment.
- `translation_report.json`: materialized queue checks, one authorized comparison-step normalization.
- `revision_validation.json`: actual queue/HTML checks, export refusal and approved-corpus regeneration.

## Reconstruct the revision from frozen source queues

Use the original frozen English work queues, which retain rejected records for
review/provenance. Do not rerun selection to replace rejected records inside this
batch. Future new-batch selection excludes the current ten active quarantine IDs.
Run from the repository root and use a fresh output path:

```bat
.venv\Scripts\python.exe -m unittest discover -s research/prm_arabic_english -p test_materialize_authorized_normalizations.py -v
.venv\Scripts\python.exe research\prm_arabic_english\materialize_translation_batch.py --queue-dir research/prm_arabic_english/data/prm800k_staging_5000/translation_batch_qc24_batch03 --assets-dir research/prm_arabic_english/translation_batches/prm800k_qc24_batch03_r1 --output-dir research/prm_arabic_english/data/prm800k_staging_5000/translation_batch_qc24_batch03/arabic_draft_r1_replay
.venv\Scripts\python.exe research\prm_arabic_english\render_translation_review.py --input research/prm_arabic_english/data/prm800k_staging_5000/translation_batch_qc24_batch03/arabic_draft_r1_replay/review_queue.jsonl --output research/prm_arabic_english/data/prm800k_staging_5000/translation_batch_qc24_batch03/record21_r1_replay.html --batch-id QC24-Batch03-r1 --record-number 21
```

After the human's final decision on revised record 21, preserve that evidence and
create a separately versioned final decision file bound to the same queue hash.
Rerun the full preservation checks before export. If further Arabic changes are
requested, create another payload/queue revision and review its new hash.
All generated data stays local and ignored; no training or pilot rerun occurred.
