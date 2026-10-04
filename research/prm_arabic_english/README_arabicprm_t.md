# ArabicPRM-T: reproducible source ingestion milestone

This stage inspects and converts a bounded English source subset. It does not
translate, train, or evaluate ArabicPRM. Existing pilot data and checkpoints are
unchanged. Global-MGSM is reserved for final evaluation and is never opened by
this pipeline. Do not use it for development, synthetic errors, selection, or tuning.

## Source and scope

Source: [OpenAI PRM800K](https://github.com/openai/prm800k), revision
`7ecc794703b2877f63226f2477a49b34f9b25163`, file
`prm800k/data/phase2_train.jsonl`. The upstream repository provides MIT licensing;
retain its attribution and review the underlying MATH dataset terms before
redistributing a derived corpus. Citation: Lightman et al., *Let's Verify Step
by Step* (2023), https://arxiv.org/abs/2305.20050.

Upstream contains phase1/phase2 train/test files. This milestone reads only
phase2_train and never uses the upstream test files for development. The native
file is Git LFS-backed, 456,135,365 bytes. Its LFS SHA256 is recorded in each
manifest, but a bounded prefix cannot verify the full-file checksum.

The default acquisition stops after 200 complete records or 8 MiB, whichever
comes first, and closes the stream. Sampling uses the source prefix, then orders
normalized problem hashes by SHA256(seed:problem_hash) and retains up to 30
groups. It is deterministic, **not representative** of the full corpus. The
initial prefix is entirely generation 9, so larger-scale sampling must address
generation/domain/length/error diversity before training claims.

## Source schema and supervision policy

Each raw row has `question`, `label`, generation and annotation metadata.
`question.pre_generated_steps` is the original model path. `label.steps` contains
candidate completions with text, rating, flags and a chosen-completion index.
Only the annotated original generated path is accepted. When the chosen index
is null, an exact match to the original generated step is required. Multiple
exact copies are accepted only when all ratings agree and none is flagged;
every matching index is retained and the lowest index is selected deterministically.
Conflicting ratings and flagged duplicates remain excluded. The converter never
substitutes a repaired alternative. Human-written paths,
ambiguous matches, flagged steps, bad problems, give-ups and QC/screening rows
are excluded with counted reasons. Unexpected schema errors stop the run.

Native ratings are preserved in `source_step_ratings`:

| Source rating | Staged label | Supervision mask |
|---|---|---|
| +1 | 1 | 1 |
| -1 | 0 | 1 |
| 0 (neutral/non-progress) | null | 0 |

Neutral is neither a positive nor a negative binary target. `first_error_step`
is the 1-based first native -1. Phase2 labeling stops at the first error: later
generated steps are **not** assigned zero labels. Their count is recorded, while
the full source is retained in `source_prefix.jsonl`. A solution is accepted only
with no negative rating; found_error must end at the first annotated negative.
These are source annotation categories, not new mathematical adjudications.

Staging retains the familiar `id`, `pair_id`, `language`, `source`, `variant`,
`problem`, `response`, `step_labels`, `first_error_step`, `error_type` fields plus
exact source steps, masks, grouping IDs, revision and source line provenance.
`language=en` and `stage=english_translation_pending` prevent claiming Arabic
data. Error taxonomy is unknown, so `error_type=null`. `pair_id` groups all paths
from the same normalized source problem; it does not promise exactly two paths.
Embedded newlines are replaced by spaces only in `response` to preserve one
tokenizer reward position per source step; original text remains in `steps`.

The existing pilot validator and training scripts are **not compatible** with
masked neutral labels or variable trajectory counts. A future trainer must use
`supervision_mask` to filter BCE targets, not turn nulls into zeros. Future
translation must preserve source IDs, source grouping, step boundaries, formulas,
numbers and ratings, and must pass Arabic QC before changing stage/language.

## Windows CMD commands

Run from the repository root. Calling the venv interpreter directly is equivalent
to activating it and avoids affecting another shell session. This ingestion path
does not need GPU packages or PYTHONPATH.

```bat
.venv\Scripts\python.exe -c "import datasets; print(datasets.__version__)"
.venv\Scripts\python.exe -m pip install -r research\prm_arabic_english\requirements-ingestion.txt
.venv\Scripts\python.exe research\prm_arabic_english\test_prm800k_ingest.py
.venv\Scripts\python.exe research\prm_arabic_english\prm800k_ingest.py
```

Outputs go to the ignored `research/prm_arabic_english/data/prm800k_staging/`:
raw prefix, train_en.jsonl, dev_en.jsonl, manifest.json. Existing output directories
are rejected to prevent overwrites. Paths default relative to the script's repo,
not the caller's working directory. An offline deterministic replay is:

```bat
.venv\Scripts\python.exe research\prm_arabic_english\prm800k_ingest.py --input research\prm_arabic_english\data\prm800k_staging\source_prefix.jsonl --output-dir research\prm_arabic_english\data\prm800k_staging_repeat
```

Offline input provenance is explicitly unverified; use the recorded prefix hash
to verify that a replay input matches a known acquisition. Train/dev JSONL hashes
should match. Manifests record acquisition differences, so need not be identical.
All trajectories and their future translations stay within the source-problem
split. Whitespace/NFKC normalization handles simple spelling-format duplicates,
but does not establish freedom from paraphrase or benchmark contamination.

## Verified first inspection (2026-10-05, policy v1)

Python 3.11.9; installed datasets 5.0.1. Ingestion is standard-library-only;
`datasets` is available for later inspection. Pip adjusted fsspec from 2026.7.0
to 2026.6.0 to satisfy datasets. This is not a full training environment lock.

- 200 raw records, 1,051,752 bytes, 179 eligible records.
- 17 ambiguous original-path selections and 4 unfinished trajectories excluded.
- 30 selected groups: 24 train records/problems, 6 dev records/problems.
- No normalized problem overlap.
- 261 selected annotated steps: 203 positive, 24 negative, 34 masked neutral.
- Train has 5 solution / 19 error trajectories; dev has 1 solution / 5 error
  trajectories. This inspection sample is imbalanced and too small for robust
  evaluation; the split is not stratified.

This is ingestion verification, not an Arabic corpus or a model result. Next:
review excluded-source cases, design broader sampling, define step-preserving
translation and mathematical QC, then implement training support for masks.

## Exclusion audit and broader sampling plan (policy v2)

The 17 ambiguous cases in the original 200-row prefix all contain duplicate
exact copies of the original generated step with agreeing negative ratings.
Policy v2 accepts these only under the agreement/unflagged rule above. The
four give-up trajectories stay excluded. Old staging directories are preserved;
run the revised converter into a new directory and keep its new manifest.
Schema v2 adds the conversion policy, candidate-match provenance, duplicate-match
counts, variant balance, generation coverage, step lengths and first-error positions.

Verified v2 replay: 196 eligible records, 17 duplicate-match steps recovered,
4 give-ups excluded. The default 30-group selection still has 24 train / 6 dev
records and zero normalized problem overlap; selected steps are 224 positive,
24 negative and 32 masked neutral. All 10 offline tests passed. Every selected
record is still generation 9, confirming that prefix expansion alone is not a
generation-diverse sampling strategy.

Before translation, expand source inspection in bounded increments (for example
1,000 rows, 8 MiB, 100 problem groups), reviewing the recorded exclusions and
coverage after each run. A larger prefix still may contain only generation 9;
do not describe it as representative. A production sampler should scan a pinned
training shard once and use seeded reservoir selection **by problem group**,
collecting all eligible trajectories for selected groups in a second pass.
This requires a separately documented download/time budget before a full scan.

Keep one fixed source-problem split across original English, Arabic translations
and future hybrid variants. Review generation coverage, length bins, positive/
negative/neutral step counts, first-error positions, trajectory class balance
and mathematical domain before freezing the corpus. Native rows lack explicit
domain tags: obtain domain metadata from the upstream training problem mapping
or document researcher annotation; do not invent domain labels from filenames.
Keep source test data and Global-MGSM out of sampling and development.

Initial translation/QC should operate on a small reviewed batch with stable
source IDs and one translated step per source step. Check numeric/formula
preservation, label/mask alignment and Arabic fluency before scaling. Translation
models/settings, prompts, revisions, outputs and adjudication must be recorded.
No translation, new model training or completed-pilot reruns are part of this audit.

## Expanded bounded inspection and translation queue (2026-10-05)

The 1,000-row acquisition read 5,210,142 bytes (below the 8 MiB budget).
944 records were eligible; 29 QC/screening records and 27 unfinished records
were excluded. Among eligible records, 70 duplicate-match steps were accepted
under policy v2. The seeded selection retained 100 source problem groups:

| Split | Problems | Trajectories | Solutions | Error trajectories |
|---|---:|---:|---:|---:|
| Train | 80 | 90 | 46 | 44 |
| Dev | 20 | 21 | 14 | 7 |

There is zero normalized problem overlap. Selected annotations include 1,042
positive, 51 negative and 64 masked neutral steps. Generation coverage is still
skewed: 102 trajectories from generation 9 and 9 from generation 8. This is not
a representative full-corpus sample. The train/dev outputs were replayed from
the saved source prefix and compared byte-for-byte with Windows `fc /b`; both
comparisons returned `FC: no differences encountered`.

Source prefix SHA256:
`30c3a8a1b7d0b765152eee8685d28ed0ca7ddabfb00ff3cc823124c3eabdb17a`.
Train JSONL SHA256:
`19d50e62aacb6e796fbea9df3e9ec7ac76c31a78a45bdd7e3e4c5c9cde32f5b8`.
Dev JSONL SHA256:
`476a929c5a897b2fa532f88cca377540a3682f98229da42f342785ba32d853ff`.

`prepare_translation_batch.py` created a pending 12-trajectory queue: 8 train
(4 solutions / 4 errors, 92 steps) and 4 dev (2 solutions / 2 errors, 44 steps).
Both splits cover short/medium/long annotated lengths and neutral/non-neutral
cases. Train covers early/middle/late first errors; dev covers early/late errors.
Original IDs, labels and source split assignments are inherited unchanged.
The three batch-selection tests passed. See [TRANSLATION_QC.md](TRANSLATION_QC.md)
for the translation contract and acceptance checklist. The work queues remain
English with null Arabic fields; translation and training have not started.
