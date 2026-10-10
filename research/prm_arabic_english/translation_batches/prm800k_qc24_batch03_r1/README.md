# QC24 Batch03 r1: final human QC complete

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

`human_qc_r1_final.json` now binds the revised queue and records final human
attestation by Zakaria Brim on 2026-10-10. It retains the original 17 acceptances
and six rejections for unchanged records and changes only revised record 21 from
pending to ACCEPT. The final Batch03 result is therefore **18 ACCEPT and six
REJECT/source quarantines**, with no pending or revise decisions. The human
authorization is preserved in `human_review_final_2026-10-10.txt`; AI assistance
is explicitly documented rather than presented as independent human review.

The earlier blocked export attempts remain useful negative gate tests. No Batch03
training export is committed in this folder; export should be regenerated from
the exact revised queue and `human_qc_r1_final.json` before a future corpus merge.
The reviewed corpus v1 remains historically unchanged at 32 records until those
accepted Batch03 records are exported and frozen into a new corpus version.

## Versioned evidence

- `source_lock.json`, `LICENSE.prm800k`: exact copies from the original batch.
- `translations.json`: versioned payload, changed only at record 21 step 2 plus revision metadata.
- `requested_changes.json`: nine literal removals, source/step hashes and human instruction evidence.
- `human_qc_r1_pending.json`: preserved pre-final state.
- `human_review_final_2026-10-10.txt`: explicit final reviewer authorization.
- `human_qc_r1_final.json`: 18 accept, six reject, full final human attestation.
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

The final decision on revised record 21 is now preserved in the separately
versioned final decision file bound to the same queue hash. Before adding Batch03
to an approved corpus version, reconstruct the exact reviewed queue, rerun the
full preservation/export checks, and freeze only the 18 accepted records. If any
future Arabic text changes are requested, create another payload/queue revision
and review its new hash. No model training or pilot rerun occurred in this QC
finalization.
