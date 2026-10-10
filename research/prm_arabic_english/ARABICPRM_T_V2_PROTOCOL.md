# ArabicPRM-T v2 frozen production protocol

This file freezes the primary ArabicPRM-T v2 corpus/training protocol **before**
the new human-QC decisions and before model training. It is intended to prevent
post-hoc tuning on the final held-out evaluation.

## 1. Source pool

Use only the pinned OpenAI PRM800K phase-2 training shard:

- revision: `7ecc794703b2877f63226f2477a49b34f9b25163`
- file: `prm800k/data/phase2_train.jsonl`
- full SHA256:
  `1110237feeb51d1bc200cb37b8f965cfdc1036eac7d506094049366fe7dc1089`
- full size: 456,135,365 bytes

Reconstruct the verified 1,000-problem source pool with seed 42 while preserving
the committed 500-problem train/dev split lock. Global-MGSM is not read.

## 2. New v2 source subset

The new production extension is **100 matched problem groups / 200 trajectories**:

- train: 80 problem groups, exactly 80 correct + 80 incorrect trajectories;
- dev: 20 problem groups, exactly 20 correct + 20 incorrect trajectories;
- every selected problem contributes exactly one correct and one incorrect path;
- all active source-quarantine records are excluded;
- every problem group appearing in a prior QC source lock is excluded, not merely
  the previously selected trajectory ID;
- train/dev assignments are inherited and never reassigned.

Selection is deterministic. Greedy scoring reduces deficits in source generation
0-9, annotated-step length (short 1-4, medium 5-12, long 13+), incorrect
first-error position (early 1-4, middle 5-12, late 13+), and neutral-annotation
coverage. SHA256 provides deterministic tie-breaking.

This is a **balanced/diverse corpus-design sample**, not a claim that the selected
200 trajectories are statistically representative of all PRM800K.

The latest pre-translation run after excluding all prior problem groups produced:

| Split | Records | Problem pairs | Correct / incorrect | Annotated steps | Supervised steps | Neutral trajectories |
|---|---:|---:|---:|---:|---:|---:|
| train | 160 | 80 | 80 / 80 | 1,494 | 1,401 | 50 |
| dev | 40 | 20 | 20 / 20 | 444 | 426 | 9 |

All generations 0-9 are represented in both splits. Train length coverage is
48 short / 55 medium / 57 long; dev is 12 / 15 / 13. Incorrect first-error
coverage is 32 early / 25 middle / 23 late in train and 9 / 6 / 5 in dev.

## 3. Arabic translation

Generate an automated **draft only** with
`Helsinki-NLP/opus-mt-en-ar`. Mathematical protected spans, literal source
annotation markers, unwrapped LaTeX, and digit-form source numbers must remain
outside the translation model and be restored/copied in source order. If the MT
model converts a word-form source number into digit form, the generated digit is
spelled back into Arabic words before preservation validation.

The normal materialization gate then rechecks:

- unchanged source IDs/hashes/splits;
- one Arabic entry per source step;
- exact protected mathematical spans;
- exact digit-form numeric sequence;
- source ratings/labels/masks unchanged;
- no train/dev problem leakage.

Automated translation is never training eligible.

## 4. Human QC

Every new translated record must receive an explicit human decision bound to the
exact review-queue SHA256. The researcher checks the problem and every annotated
step for Arabic fidelity, mathematical-expression preservation, intentional-error
preservation, step alignment, and fluency.

Allowed final decisions are ACCEPT or REJECT. Any textual revision creates a new
translation payload/review-queue hash and requires review of the revised text.
Source-supervision conflicts are quarantined; source labels are never silently
repaired. Neutral ratings remain masked.

AI assistance may propose decisions/corrections but is not a substitute for the
researcher's final attestation.

## 5. ArabicPRM-T v2 reviewed corpus

After QC, export only accepted Arabic trajectories with the existing
`export_reviewed_arabic.py` gate. ArabicPRM-T v2 is formed from:

1. the frozen historical reviewed ArabicPRM-T v1 corpus;
2. accepted Batch03 r1 trajectories;
3. accepted trajectories from this new 200-trajectory production extension.

Before merge, revalidate every source decision/export, reject duplicate source
IDs, reject active quarantines, and verify zero cross-split problem overlap.
The final v2 manifest and exact train/dev file hashes are frozen before training.

QC rejection may make the final record counts slightly unbalanced. Do not replace
rejected trajectories after viewing their QC outcome; doing so would make the
source selection adaptive to human review.

## 6. Primary QLoRA training protocol

Base PRM:
`Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B`.

Primary configuration is locked as:

- seed: 42;
- epochs: 3;
- one trajectory per forward/backward pass;
- gradient accumulation: 8 trajectories;
- 4-bit NF4 with double quantization, fp16 compute;
- gradient checkpointing enabled;
- LoRA targets: `q_proj`, `v_proj`;
- LoRA rank 8, alpha 16, dropout 0.05;
- LoRA learning rate: 1e-4;
- reward/value-head learning rate: 5e-5;
- maximum gradient norm: 1.0;
- fixed negative-step BCE weight: 1.0 (unweighted primary loss);
- maximum sequence length: 4096 tokens;
- **no silent truncation**: any overlength accepted trajectory blocks the run and
  must be handled by an explicit pre-training corpus decision;
- no English replay in the primary ArabicPRM-T run.

The primary checkpoint-selection metric is **dev step discrimination**:
mean score(valid supervised steps) minus mean score(invalid supervised steps).
The untouched base PRM is evaluated on the same frozen reviewed dev split before
training. Dev data is never optimized.

Secondary dev diagnostics include step accuracy at 0.5, ROC AUC, trajectory mean
and minimum-score gaps, and first-error localization exact/within-one.

If no adapted epoch exceeds the untouched base on the locked primary dev metric,
report that result rather than selecting an adapted checkpoint by another metric.

## 7. Post-training evaluation order

After the v2 checkpoint is frozen:

1. evaluate on the controlled Arabic discrimination benchmark;
2. evaluate English retention with the already frozen English benchmark;
3. run any independent Arabic process-verification analysis specified in the
   thesis protocol;
4. proceed to ArabicPRM-S / ArabicPRM-H and translate-to-English baseline as
   separate variants;
5. only at the end, evaluate the final frozen choices on untouched Global-MGSM.

Do not tune the v2 corpus, hyperparameters, checkpoint criterion, or thresholds
after seeing Global-MGSM.
