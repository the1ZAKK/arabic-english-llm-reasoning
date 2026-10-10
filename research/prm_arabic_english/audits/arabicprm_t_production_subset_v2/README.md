# ArabicPRM-T production subset v2

This milestone freezes a deterministic translation subset from the verified
1,000-problem full-shard PRM800K source pool.

## Selection policy

The source pool is intentionally not translated wholesale because it contains
5,776 incorrect versus 924 correct trajectories. The production selector instead
uses exact 50/50 correct/incorrect quotas independently in the inherited train and
dev splits, while greedily improving coverage of source generation, trajectory
length, first-error position and neutral-step presence. SHA256-seeded tie breaks
make the result deterministic. No more than two selected trajectories may come
from one problem group.

Active quarantines and every previously reviewed source lock are excluded.
Global-MGSM is not accessed.

## Frozen budget

- 400 trajectories total
- 320 train / 80 dev
- 200 correct / 200 incorrect
- 363 distinct source problems
- zero train/dev problem overlap
- 4,106 annotated steps
- 3,554 positive source ratings
- 200 negative source ratings
- 352 neutral/masked source ratings

The train split contains 160 correct and 160 incorrect trajectories. The dev
split contains 40 correct and 40 incorrect trajectories.

## Diversity audit

All generations 0 through 9 are represented:

| Generation | Records |
|---:|---:|
| 0 | 30 |
| 1 | 27 |
| 2 | 33 |
| 3 | 33 |
| 4 | 36 |
| 5 | 36 |
| 6 | 35 |
| 7 | 56 |
| 8 | 58 |
| 9 | 56 |

Length coverage is 107 short, 148 medium and 145 long trajectories. Among the
200 incorrect trajectories, first errors are distributed across 68 early,
68 middle and 64 late cases. There are 170 trajectories containing at least one
neutral/masked step.

This is a diversity-aware source selection, not a claim of domain-stratified
sampling. Native PRM800K rows do not supply reliable mathematical-domain tags, so
none are invented here.

## Reproducibility evidence

GitHub Actions run: 38058613943

Artifact: `arabicprm-t-production-subset-v2`

Artifact ID: 11672805357

Artifact ZIP SHA256:
`07be0cfbdbbc7209f85e9ddf235035a063828da5fe27a54de263438afe71b38b`

Frozen source hashes:

- `train_en.jsonl`: `edfd38dbe6c23c1547763da80c49cd30eb158bab932314685baa6c24c9970f78`
- `dev_en.jsonl`: `59a084b5755ad7fdb37c6ac7bed87a71b0a47a9c99da45f79dcfb74390259bb7`
- train translation queue: `47611ca310eecf440ebd4be87aff645f712f2a06a60046b92bec1503d6804b3e`
- dev translation queue: `a84c1c13ab26f8e4967124f401771ae5d1facc91735f331fe37c023c22ec7a0e`

The resulting queue is **not training eligible** until automated preservation
checks and explicit human QC are complete.
