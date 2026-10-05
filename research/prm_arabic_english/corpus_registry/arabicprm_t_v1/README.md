# Approved ArabicPRM-T corpus v1

This registry freezes the aggregation of **existing** human-accepted QC12 r1
and QC24 r1 exports. Zakaria Brim's original reviewer identity, dates and notes
remain in every accepted row. Merging performs no human QC or new approval.

| Split | Trajectories | Annotated steps | Supervised steps | Neutral/masked |
|---|---:|---:|---:|---:|
| Train | 21 | 200 | 189 | 11 |
| Dev | 11 | 98 | 87 | 11 |
| Total | 32 | 298 | 276 | 22 |

The corpus contains 31 source problem groups. All original source IDs, pair IDs,
labels, masks, first-error positions, source provenance and split assignments
are preserved. There are 261 positive and 15 negative supervised targets.
The four QC24 source-annotation conflicts remain rejected/quarantined and are
excluded. `source_quarantine.json` is unchanged, with SHA256
`3efce6b68ddbfe69b577c955de9aadedeaf8c683057c327bf8e4a21d448c5903`.

## Versioned evidence

- `input_batches.json`: repository-relative inputs and three exact hash pins per batch.
- `manifest.json`: accepted counts, input/decision/output hashes, rejected reasons,
  quarantine snapshot, step and supervision distributions.
- `accepted_registry.json`: per-record source, grouping, split, approval and batch evidence.

Generated Arabic JSONL files remain local under the ignored
`data/reviewed_corpora/arabicprm_t_v1/` directory. Manifest output SHA256 values:

| File | SHA256 |
|---|---|
| train_ar.jsonl | `3287347500c8cb75857bde49784c22f0679418c373078d9019a1fed535c42472` |
| dev_ar.jsonl | `a9d966328e327cbaeb65714fc2be9c785c1c2811df33754e379eef60ddb78ec4` |
| accepted_registry.json | `a8fc2ec67e956f8b212f8adfc120e807ca49d4da874389071e66995701b16aa5` |

The merger rechecks raw input hashes and regenerates the approved records from
the bound queues/decisions before comparing every complete output row. It blocks
duplicate source IDs and source problem leakage across batches using both stored
problem IDs and normalized original English text. Active source quarantines block
acceptance. Input edits during validation and nonstandard JSON constants fail.
An existing output directory is refused. Fifteen regression tests passed.

## Replay

Run from the repository root after reconstructing the exact original reviewed
queues/exports described in the QC12 and QC24 r1 READMEs. The registry pins their
Windows-produced bytes; a differently serialized manifest fails the pin rather
than silently substituting evidence. Hash-bound versioned JSON uses `-text` Git
attributes so a Windows checkout preserves its bytes.

```bat
.venv\Scripts\python.exe -m unittest discover -s research/prm_arabic_english -p test_merge_reviewed_corpus.py -v
.venv\Scripts\python.exe research\prm_arabic_english\merge_reviewed_corpus.py --batches research/prm_arabic_english/corpus_registry/arabicprm_t_v1/input_batches.json --output-dir research/prm_arabic_english/data/reviewed_corpora/arabicprm_t_v1_replay
```

The real v1 output passed the existing manifest-checked `load_reviewed_splits`
loader. In-memory regeneration matched all records, registry content and manifest
exactly. No model training, optimizer update or completed-pilot rerun occurred.

## Scope and next version

This is a small curated approved corpus from bounded PRM800K training prefixes,
with development data inherited from the existing fixed problem split. It is not
a final evaluation set or representative production sample. English, Arabic and
future hybrid variants must retain the same source-problem split. Source test
files and Global-MGSM remain reserved for evaluation.

QC24 Batch03 remains outside v1 until complete human review and a new guarded
export. Freeze accepted additions in a new registry/corpus version, retaining v1.
Broader generation/domain coverage and a documented full-scan budget remain
part of the production sampling phase. Preserve upstream PRM800K attribution
and the source terms recorded in the ingestion documentation.
