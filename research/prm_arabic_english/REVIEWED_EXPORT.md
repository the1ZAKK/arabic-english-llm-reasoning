# Human QC gate and Arabic export

The approved corpus v1 aggregates QC12 r1 and QC24 r1: 32 trajectories, 21 train
and 11 dev, 298 steps with 22 neutral/masked. Its immutable input pins, accepted
record registry and export manifest are versioned under
`corpus_registry/arabicprm_t_v1/`. `merge_reviewed_corpus.py` regenerates each
accepted export from its original queue and human decisions, verifies complete
row equality and output hashes, and blocks duplicate IDs, cross-split source
problem overlap, active quarantines and input edits during validation. It retains
original human approval metadata and creates no new approvals. Its output loads
through `load_reviewed_splits`; generated data stays local in the ignored
`data/reviewed_corpora/` directory. See the registry README for replay commands.

QC24 Batch03 human review returned 17 ACCEPT, six source-conflict REJECT decisions
and one REVISE. The six rejected IDs are active quarantines, alongside the earlier
four. Original human notes and decisions are preserved in the Batch03 directory.
Revision r1 removes only the nine literal markers from record 21 step 2 and binds
a new complete-queue hash. The 23 unchanged human decisions are retained with
original decision evidence; the changed record is pending and the revised global
human attestation is false. Only record 21 needs final review. Original and revised
export attempts both refused, and no Batch03 training export was created. See
`translation_batches/prm800k_qc24_batch03_r1/README.md` for revision evidence.

QC24 r1 has completed final human review: 20 ACCEPT decisions and four
source-annotation quarantines. Its reviewed export contains 13 train and seven
dev records (162 steps: 153 supervised and nine neutral). Exact queue hashes and
preservation checks passed before the four revised decisions were accepted. See
`translation_batches/prm800k_qc24_r1/README.md` for the exact revised queue and
decision history. The exporter automatically blocks accepting any active ID in
`source_quarantine.json`; legal REJECT decisions still exclude those records.
New batch selection also excludes active quarantine IDs. Keep original source
annotations unchanged and require separate human adjudication to resolve them.

All 20 QC24 r1 exports passed the manifest-checked loader, cached-tokenizer step
alignment and synthetic-logit gradient-mask check; 115–704 tokens per record.
Final decisions, export hashes and smoke evidence are versioned in the r1 assets.
Original pending/revision-stage evidence remains unchanged. QC24 r1 is a small
curated batch, and this data check performs no PRM training or optimizer update.

QC12 revision r1 has completed human review; see the versioned batch README and
`human_qc_r1.json` for the exact approval and queue hash. New drafts remain pending.
`export_reviewed_arabic.py` creates
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

QC12 r1 has two human-authorized, source-ID/step-specific Arabic normalizations:
removal of an embedded annotation marker and correction of `\pod` to `\pmod`.
The original source records remain unchanged; other protected spans must match.

Batch03 r1 adds one precise authorized comparison-source exception: deletion of
the literal `[* 1]` through `[* 9]` markers only for its record 21, step 2. The
original English step and source hash retain all nine markers. Arabic mathematics,
all other numeric content, the two step boundaries, ratings `[0, -1]`, binary/neutral
labels `[null, 0]` and masks `[0, 1]` remain unchanged. This exception changes no
source labels and grants no final acceptance. Eight normalization regression tests
and real-artifact preservation checks passed.

`training_supervision(record)` returns zero-based annotated-step positions and
binary targets only for mask=1. Neutral positions never enter those target lists.
For model training, align all translated steps with tokenizer reward positions,
then index the differentiable reward logits by these returned positions before
BCE. This helper is CPU/data validation only: it is not a new training run or a
tested replacement for the pilot trainer. Export manifests explicitly state that
the current pilot trainer is incompatible. This tiny curated batch remains QC
material, not a production training corpus or final held-out evaluation.

## Reviewed-data training adapter

`reviewed_training_data.py` provides a separate path without changing the completed
pilot trainer. `load_reviewed_splits(directory)` checks exported file hashes,
accepted QC metadata, labels/masks, unique IDs and problem-level split separation.
`prepare_reviewed_record(record, tokenizer, max_length)` uses explicit step lists
and the repository's BOS/problem/newline convention. Internal step newlines do
not create extra annotations. Overlength trajectories are rejected, never silently
truncated. Neutral steps stay in the model context but have no direct loss target.

Integration with a PRM returning raw logits:

```python
prepared = prepare_reviewed_record(record, tokenizer, max_length=32768)
_, _, logits = model(
    input_ids=prepared['input_ids'].to('cuda:0'),
    attention_mask=prepared['attention_mask'].to('cuda:0'),
    return_probs=False,
)
loss = masked_step_loss(logits, prepared)
loss.backward()
```

`smoke_reviewed_training_data.py` uses only a locally cached tokenizer and synthetic
raw logits. It verifies exactly which token positions receive gradients. It does
not load PRM weights, update an optimizer, test QLoRA, or estimate performance.
QC12 r1 passed on all 12 records: 136 steps, 123 supervised and 13 neutral;
174–1109 tokens per record. Five regression tests additionally cover internal
newlines, positive/negative gradients, neutral masking, overlength rejection,
pending-record rejection and invalid logit shape.

```bat
.venv\Scripts\python.exe research\prm_arabic_english\test_reviewed_training_data.py
.venv\Scripts\python.exe research\prm_arabic_english\smoke_reviewed_training_data.py --data-dir research/prm_arabic_english/data/prm800k_staging_1000/reviewed_arabic_r1 --report research/prm_arabic_english/data/prm800k_staging_1000/reviewed_training_smoke_replay.json
```

Before a larger training run, integrate this adapter into a separate PRM/QLoRA
runner and verify real model backward/optimizer behavior in a fresh smoke output
directory. Never reuse pilot checkpoints or treat QC12 as a final training corpus.

## Real QLoRA smoke runner

`smoke_reviewed_qlora.py` loads the locally cached Skywork snapshot in NF4 4-bit,
adds rank-8 QLoRA to q_proj/v_proj, and trains the reward head in FP32. Three
train trajectories are selected deterministically, preferring neutral-containing
and shorter inputs. Dev records are validated but never used for optimization.
The mean of three trajectory losses is accumulated for exactly one AdamW update
(LoRA LR 1e-4, head LR 5e-5, clip norm 1, seed 42).

The runner checks finite logits/loss/gradients, nonzero gradients and weight
changes in both parameter groups, and zero direct logit gradients outside
supervised positions. Neutral steps remain part of the causal context. It saves
the adapter, reward head and tokenizer into a fresh output directory, frees the
first model, reloads a fresh quantized base plus saved weights, and compares all
annotated-step logits in eval mode with rtol=atol=1e-5. A success report includes
dependency versions, source snapshot, input manifest hash, GPU memory peaks and
checkpoint file hashes. This is an infrastructure test, not a performance result
or proof of optimizer-resume reproducibility; optimizer state is not saved.

```bat
.venv\Scripts\python.exe -u research\prm_arabic_english\smoke_reviewed_qlora.py --data-dir research/prm_arabic_english/data/prm800k_staging_1000/reviewed_arabic_r1 --output-dir research/prm_arabic_english/checkpoints/reviewed_qlora_smoke_replay
```

Existing output directories are refused. Model and tokenizer downloads are not
needed; use a fresh output directory for each run. Original pilot code and saved
pilot results are untouched.

QC12 r1 real smoke result: three train records, 23 supervised and seven neutral
steps, one optimizer update. All losses and gradients were finite; both LoRA and
reward-head weights changed. Peak allocated VRAM was 2.036640 GiB (reserved
2.630859 GiB) on an RTX 2060 Max-Q. All three fresh-reload comparisons had zero
maximum absolute step-logit difference. The versioned evidence is
`translation_batches/prm800k_qc12/qlora_smoke_r1.json`; checkpoint files stay local
under `checkpoints/reviewed_qlora_smoke_r1/` and are ignored by Git.

Example template command (no training export occurs):

```bat
.venv\Scripts\python.exe research\prm_arabic_english\export_reviewed_arabic.py --make-template --decisions qc12_decisions.json --output-dir research\prm_arabic_english\data\prm800k_staging_1000\reviewed_arabic
```

After genuine human review has filled the decision file, omit `--make-template`
to export. Existing template files/output directories are refused to prevent
overwriting decisions or artifacts. Keep generated data within ignored staging
directories; commit reviewed metadata deliberately after inspecting it for scope
and attribution. Global-MGSM is not used by this stage.
