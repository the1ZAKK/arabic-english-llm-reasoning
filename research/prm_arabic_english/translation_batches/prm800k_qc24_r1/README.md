# QC24 r1: requested revisions awaiting final human acceptance

Zakaria Brim's supplied human training-data review accepted 16 original records,
requested revisions on 16, 17, 19 and 20, and rejected/quarantined 1, 9, 12 and 18
for source-annotation conflicts. The original review and original translation
payload are preserved in `../prm800k_qc24/`.

Exactly eight Arabic text fields were revised: record 16 step 2; record 17 steps
3 and 4; record 19 problem and steps 1 and 7; record 20 steps 2 and 7. See
`requested_changes.json` for exact before/after wording and `revision_audit.json`
for the source, label, mask, formula, number and split preservation checks.
The complete 20 unchanged queue records were compared with the reviewed originals.

`human_qc_r1_pending.json` retains the original 16 accepts and four rejects only
for those unchanged records, with the original review hash and carry-forward basis.
It does not claim a new human review of edited text. The four revised decisions
remain REVISE until explicit human acceptance. Their updated Arabic wording passed
automated preservation checks, which do not establish acceptance.

The revised review queue SHA256 is
`81f6552e58304f0b4485d5ea60c95c1315c06a44159d938b9c75494fbda59d4a`.
It contains the same 24 records and 201 steps. Source records, canonical source
hashes, pair IDs, supervision masks, source ratings, step labels, split assignments
and intentional errors are unchanged. No formula normalization was applied.

Four source-annotation rejects remain in the central `../../source_quarantine.json`
outside immutable source data. Active quarantined IDs are excluded from future
translation batch selection and cannot be exported with an ACCEPT decision.
Rejection remains legal. A malformed present catalog blocks selection/export.
An absent catalog supports historical runs that predate the feature. Do not remove
or deactivate catalog entries without human source-annotation adjudication.

The actual r1 export attempt correctly failed because revisions are pending and
created no Arabic export directory. Eight quarantine tests and the existing
batch-selection/materialization/export tests passed. This revision performed no
model training, held-out evaluation, source relabeling, or automatic QC approval.

Replay the payload with the existing frozen source queues and a fresh output:

```bat
.venv\Scripts\python.exe research\prm_arabic_english\materialize_translation_batch.py --queue-dir research/prm_arabic_english/data/prm800k_staging_5000/translation_batch_qc24 --assets-dir research/prm_arabic_english/translation_batches/prm800k_qc24_r1 --output-dir research/prm_arabic_english/data/prm800k_staging_5000/translation_batch_qc24/arabic_draft_r1_replay
```

Do not refreeze source IDs or rerun the current new-batch selector to reconstruct
this historical selection; active quarantine exclusions deliberately change it.
See the original batch README for historical source-queue replay guidance.
After the four revised records receive explicit final human decisions, version a
new decision manifest bound to the exact r1 queue hash before any export.
