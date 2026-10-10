# ArabicPRM-T v2 frozen production selection

This directory freezes the deterministic 256-trajectory production
translation selection generated from the verified full PRM800K shard.

It contains 204 train and 52 dev trajectories, exactly balanced between
correct and incorrect variants in each split, with at most one trajectory
per source problem group. Selection excludes the active quarantine catalog,
the complete ArabicPRM-T v1 accepted registry, and every Batch03 source
problem group. No translation, human QC, export, or training has occurred
in these queues.

The source pool is the 1,000-problem full-shard audit at revision
`7ecc794703b2877f63226f2477a49b34f9b25163`, full-source SHA256
`1110237feeb51d1bc200cb37b8f965cfdc1036eac7d506094049366fe7dc1089`.

Human review must bind to the exact post-translation queue hashes. AI
translation or AI-assisted checks do not count as human QC.
