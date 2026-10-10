# ArabicPRM-T v2 deterministic source subset

The production extension was frozen on 2026-10-10 from the verified 1,000-problem
full-shard PRM800K source pool.

The final pre-translation subset contains **100 matched problem groups / 200
trajectories**. Each selected problem contributes exactly one source-annotated
correct path and one source-annotated incorrect path. Prior QC problem groups are
excluded in full, so v2 does not quietly reuse a different trajectory from an
already reviewed mathematical problem.

## Frozen counts

| Split | Problem pairs | Records | Correct / incorrect | Annotated steps | Supervised steps | Neutral trajectories |
|---|---:|---:|---:|---:|---:|---:|
| train | 80 | 160 | 80 / 80 | 1,494 | 1,401 | 50 |
| dev | 20 | 40 | 20 / 20 | 444 | 426 | 9 |
| total | 100 | 200 | 100 / 100 | 1,938 | 1,827 | 59 |

There is zero train/dev problem overlap. All source generations 0-9 occur in both
splits. Train length coverage is 48 short / 55 medium / 57 long and dev is
12 / 15 / 13. Incorrect first errors cover early, middle and late positions in
both splits.

The selection excludes 60 source-record IDs and 57 complete prior problem groups
from the QC12, QC24 and Batch03 source locks, in addition to the active quarantine
catalog.

## Provenance

- source revision: `7ecc794703b2877f63226f2477a49b34f9b25163`
- source full SHA256:
  `1110237feeb51d1bc200cb37b8f965cfdc1036eac7d506094049366fe7dc1089`
- workflow run: `38045027730`
- artifact: `arabicprm-t-v2-source-200`, ID `11666632672`
- artifact ZIP SHA256:
  `d9e1739bc1b7a98f547c2ac0ae35169b50af7cbb60478bc177d30df7dd1af081`
- selection manifest SHA256:
  `a21ce1fe1e033eb86b7739eca485509434ba72b6880e2669698ef6558cd431a4`
- translation source-lock SHA256:
  `bc168483952b2f153fe95dd3d0a06b5ebc86dfaa5b20fec32d9422c2d2736174`

This is a balanced/diverse **training-source design**, not a statistical
representativeness claim about PRM800K. Global-MGSM was not accessed. No Arabic
translation, human QC or model training was performed in this source-selection
run.
