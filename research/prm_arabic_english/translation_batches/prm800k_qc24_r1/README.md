# QC24 r1: final human acceptance and reviewed export

On 2026-10-05, Zakaria Brim explicitly accepted revised records 16, 17, 19 and 20
after reviewing their corrected wording. The exact r1 queue hash and all existing
preservation checks were verified again before recording `human_qc_r1_final.json`.
The final decisions are 20 ACCEPT and four REJECT: records 1, 9, 12 and 18 remain
actively quarantined, with their source labels unchanged. See the supplied final
message in `human_review_final_2026-10-05.txt` and `final_acceptance_precheck.json`.

The reviewed export contains 13 train and seven dev records: 162 annotated steps,
153 supervised and nine neutral. `reviewed_export_manifest_final.json` records
the queue, final decision and exported file hashes. The actual data remains local
in the ignored `data/prm800k_staging_5000/reviewed_arabic_qc24_r1/` directory.
`reviewed_training_smoke_final.json` verifies the cached-tokenizer alignment and
synthetic-logit gradients for all 20 records; all neutral positions remain masked.
This check loads no PRM weights and performs no model training. This batch remains
small curated QC material, not a complete training corpus or final evaluation set.

Repository `.gitattributes` preserves the exact bytes of hash-bound source locks,
payloads, decision files, final review receipt, quarantine catalog and final
evidence files. Windows `core.autocrlf` must not change their recorded SHA256 hashes.
`git_byte_verification_final.json` records the successful comparison of all 14
protected files with their Git index bytes and an actual fresh Windows checkout.

Replay export into a fresh directory after reproducing the exact r1 queue:

```bat
.venv\Scripts\python.exe research\prm_arabic_english\export_reviewed_arabic.py --queue research/prm_arabic_english/data/prm800k_staging_5000/translation_batch_qc24/arabic_draft_r1/review_queue.jsonl --decisions research/prm_arabic_english/translation_batches/prm800k_qc24_r1/human_qc_r1_final.json --output-dir research/prm_arabic_english/data/prm800k_staging_5000/reviewed_arabic_qc24_r1_replay
```

## Revision-stage history (preserved)

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

The initial r1 export attempt correctly failed because revisions were pending and
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
The subsequent final decisions are versioned separately and bound to this exact
r1 queue hash. Pending decisions and revision-stage reports remain historical
evidence; they were not overwritten by final acceptance.
