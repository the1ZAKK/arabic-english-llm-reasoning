# ArabicPRM-T production source sampling

This milestone replaces bounded-prefix source selection with a full-shard,
problem-group sampler. It does **not** translate, train, or evaluate a model.

## Why this exists

The earlier 1,000-row and 5,000-row PRM800K prefixes were useful for validating
the ingestion, translation, QC, quarantine and training infrastructure, but they
were dominated by generations 8 and 9. Prefix expansion alone therefore cannot
support a strong claim that the final ArabicPRM-T training source is broadly
sampled from PRM800K.

`prm800k_production_sample.py` implements the next methodological step:

1. require a local copy of the pinned `phase2_train.jsonl`;
2. require the expected full-file SHA256 before any output is written;
3. scan the complete training shard once;
4. apply the existing exact-original-path conversion and exclusion policy;
5. select problem groups using a deterministic bottom-k SHA256 reservoir;
6. preserve any previously anchored train/dev problem assignments;
7. scan the same shard a second time;
8. collect **all eligible trajectories** for every selected problem group;
9. verify that the source hash is identical across both passes;
10. emit train/dev English staging files plus a coverage manifest.

Global-MGSM and PRM800K test files are not read.

## Sampling semantics

The reservoir unit is the normalized `problem_id`, never an individual
trajectory. Every eligible trajectory belonging to a selected problem is
collected on pass two. This prevents a source problem from being split across
train and dev and avoids selecting only a convenient trajectory from a group.

For a fixed seed, each non-anchored problem group receives a deterministic SHA256
priority. The smallest priorities are retained. This is order-independent and
replayable without holding the entire source shard in memory.

Existing problem assignments can be retained with `--split-anchor-dir`. New
problem groups receive their split through a separate deterministic SHA256
threshold. The resulting English split should be reused by ArabicPRM-T,
ArabicPRM-S comparison material, ArabicPRM-H and any English-side controls.

## Required budget decision

A full scan is roughly a 456 MB local read per pass. The script performs two
passes, so the user should explicitly decide the problem-group budget before
running it. `--max-problems` is therefore required rather than silently defaulted.

The script intentionally does not download the full shard. Obtain the pinned
training shard separately, record the Git LFS object SHA256, and pass that exact
checksum with `--expected-sha256`.

Example Windows CMD command:

```bat
.venv\Scripts\python.exe research\prm_arabic_english\prm800k_production_sample.py ^
  --input D:\path\to\prm800k\data\phase2_train.jsonl ^
  --expected-sha256 <PINNED_LFS_SHA256> ^
  --output-dir research\prm_arabic_english\data\prm800k_production_1000 ^
  --max-problems 1000 ^
  --seed 42 ^
  --dev-fraction 0.2 ^
  --split-anchor-dir research\prm_arabic_english\data\prm800k_staging_5000
```

The exact production budget is a research decision and should be frozen before
translation begins.

## Manifest audit

The output manifest records:

- full source SHA256 and byte count;
- first-pass and second-pass source hashes;
- total rows and eligible records;
- counted exclusions;
- number of anchored and newly sampled problem groups;
- train/dev record and problem counts;
- zero problem overlap;
- trajectory-class balance;
- source rating totals;
- neutral/masked and supervised step counts;
- generation coverage;
- annotated trajectory lengths;
- first-error positions;
- output hashes;
- explicit flags that Global-MGSM, translation and training were not used.

The sampler is uniform over eligible problem groups under the deterministic hash
priority. It is **not domain-stratified**. Do not call the resulting corpus
representative until generation, length, error-position and mathematical-domain
coverage have been audited.

PRM800K rows do not provide a reliable domain field for this purpose. Domain
metadata should come from an upstream problem mapping or documented researcher
annotation; it must not be invented from filenames or problem wording.

## Validation

Run the offline unit tests before a real scan:

```bat
.venv\Scripts\python.exe -m unittest research.prm_arabic_english.test_prm800k_production_sample -v
```

The tests cover:

- order-independent problem-group selection;
- collection of all eligible trajectories from a selected problem;
- preservation of anchored train/dev assignments;
- refusal to write outputs when the full-source checksum is wrong.

## What this milestone does not do

It does not:

- decide the final corpus size;
- translate records;
- perform human QC;
- repair source labels;
- use quarantined records for reviewed Arabic training;
- train ArabicPRM-T;
- use Global-MGSM;
- claim domain representativeness.

After the full-shard sample is frozen and its coverage is reviewed, the next step
is to select translation/QC batches from that staging source while preserving
the same problem-level split and active source quarantine.
