# ArabicPRM-T first translation and QC batch

This is a work queue, not Arabic training data. Translation is pending. Run
`prepare_translation_batch.py` from the existing venv after the 1,000-row source
inspection. Default output is the ignored source staging directory's
`translation_batch/`, with train/dev queues and a checksum/provenance manifest.
Existing output directories are refused. No model or API is called.

Current status: QC12 r1 has completed human review and export. The next QC24 batch
has 24 Arabic drafts / 201 steps from the expanded 5,000-row prefix and remains
pending human review. See `translation_batches/prm800k_qc24/README.md` for exact
hashes, limits and replay commands. New batch approvals are never inferred from
prior batches. Export and mask-aware adapter/real QLoRA smoke validation now exist;
the original pilot trainer remains incompatible with reviewed-data queues.

The default batch has 8 train and 4 dev trajectories, half annotated solutions
and half annotated errors in each split. A deterministic greedy selector seeks
coverage of length bins (1-4, 5-12, 13+ steps), first-error positions (1-4, 5-12,
13+, or none), and neutral-label presence. These bins describe annotated
prefixes, not full generated trajectories. This is a deliberately curated QC
batch, not a representative sample or new evaluation benchmark. Greedy selection
does not guarantee every bin. The manifest records actual coverage.

All source IDs, problem IDs, source step text, ratings, masks and source split
assignments remain unchanged. Source train/dev checksums and problem overlap are
checked before selection. The 200-row and 1,000-row inspection runs are separate
exploratory subsets: group assignment can change when their source pool changes.
Neither split has been frozen for training. Freeze a versioned source-problem
split before production translation; never mix exploratory assignments.

For the QC24 expansion, the 1,000-row/100-problem assignments are now anchors:
`prm800k_ingest.py --split-anchor-dir` verifies the old record hashes and retains
their problem splits. New problem groups use seeded independent SHA256-threshold
assignments. Carry forward the complete latest staging set as the next anchor;
do not rerun a growing corpus with an unanchored exploratory split. A versioned
500-problem split lock accompanies QC24. `--exclude-source-lock` prevents selecting
previous batch IDs, and `--max-steps` records an explicit review-length budget.

## Translation contract

Fill only the `translation` object in each queue record. Preserve
`source_record`, `source_record_sha256` and `split` exactly.

- Translate the problem and every annotated source step into clear Modern
  Standard Arabic, one translated array entry per source step.
- Preserve numbers, units and formulas. Keep mathematical expressions and LaTeX
  unchanged for this first batch; use the original digit representation.
- Preserve incorrect reasoning exactly. Do not fix arithmetic, explain the
  mistake, add a conclusion, or improve the original solution.
- Do not merge/split steps, add an unlabeled continuation, or discard neutral
  steps. Embedded source newlines do not create additional array entries.
- Record translator/model identifier, version, prompt, generation settings,
  date and per-record translation notes before marking translation complete.
- Keep the English source record labeled `language=en`. Arabic export is a later
  step after translation and QC, with immutable source IDs and inherited splits.

## Researcher QC

Check every record in this first small batch. Record reviewer, date, decision
and specific corrections in `qc`, without altering source supervision.

1. Confirm the source hash and train/dev assignment are unchanged.
2. Check that the translated problem preserves the mathematical task.
3. Compare each source/Arabic step for semantic fidelity and exact preservation
   of numeric expressions and formulas; preserve any deliberate errors.
4. Verify the number and order of steps, labels and supervision masks.
5. Review Arabic fluency without changing mathematical meaning.
6. Record accept/revise/reject, the reason, and an adjudication history.

This translation QC does not independently establish the correctness of all
source annotations. Any suspected source-label issue should be quarantined and
reviewed, never silently corrected. Neutral source ratings stay masked. Only
accepted translations may enter a later Arabic export. Before training, implement
and validate an exporter and mask-aware loader; current pilot training is not
compatible with these queues. Global-MGSM remains reserved for final evaluation.
