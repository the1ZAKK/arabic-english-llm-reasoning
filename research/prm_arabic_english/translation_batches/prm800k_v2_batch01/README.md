# ArabicPRM-T v2 Batch01

First AI-drafted translation/QC batch from the frozen 256-trajectory production
selection.

- 6 train trajectories: 3 correct, 3 incorrect
- 2 dev trajectories: 1 correct, 1 incorrect
- 8 unique source problem groups
- inherited full-shard train/dev assignments
- source labels, masks, ratings and step boundaries are immutable
- no source reasoning may be repaired or completed during translation
- human QC is required before any export or corpus merge

This is deliberately small so the new production translation path is validated
end-to-end before scaling to the remaining v2 selection. The Arabic draft is
AI-assisted; AI checks do not constitute human review.
