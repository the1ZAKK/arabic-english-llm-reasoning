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
is null, a unique exact match to the original generated step is required; the
converter never substitutes a repaired alternative. Human-written paths,
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

## Verified first inspection (2026-10-05)

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
