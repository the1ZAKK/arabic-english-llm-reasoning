# ArabicPRM-T v2 Batch02

Second AI-drafted translation/QC batch from the frozen 256-trajectory production selection.

Selection rule: scan the frozen train/dev queues in order after excluding Batch01 records, and take the earliest unused records needed to preserve the Batch01 production shape:
- train: 3 correct + 3 incorrect
- dev: 1 correct + 1 incorrect

Result:
- 6 train trajectories: 3 correct, 3 incorrect
- 2 dev trajectories: 1 correct, 1 incorrect
- 8 unique source problem groups
- inherited full-shard train/dev assignments
- source labels, masks, ratings and step boundaries are immutable
- no source reasoning may be repaired or completed during translation
- human QC is required before any export or corpus merge

Batch01 remains independently frozen and pending genuine human QC.
