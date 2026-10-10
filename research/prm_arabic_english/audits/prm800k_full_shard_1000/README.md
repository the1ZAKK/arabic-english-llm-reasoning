# PRM800K full-shard 1,000-problem audit

The full pinned PRM800K `phase2_train.jsonl` shard was scanned on 2026-10-10
using the two-pass deterministic problem-group sampler. The GitHub Actions run
completed successfully and uploaded the raw manifest plus compact audit summary.

## Provenance

- Source revision: `7ecc794703b2877f63226f2477a49b34f9b25163`
- Full source SHA256: `1110237feeb51d1bc200cb37b8f965cfdc1036eac7d506094049366fe7dc1089`
- Full source size: 456,135,365 bytes
- Workflow run: 38043586637
- Artifact: `prm800k-full-shard-audit-1000` (ID 11666640814)
- Artifact ZIP SHA256: `c1956bcac930145af22b5330f8247909a318006cfd0fd4c216e695810c3db1a3`

The sampler preserved the committed 500-problem train/dev split lock and added
500 new problem groups using deterministic SHA256 priorities.

## Audit result

| Metric | Result |
|---|---:|
| Raw rows scanned | 97,782 |
| Eligible source records | 73,792 |
| Selected problem groups | 1,000 |
| Anchored / new groups | 500 / 500 |
| Train / dev problems | 790 / 210 |
| Train / dev trajectories | 5,267 / 1,433 |
| Total selected trajectories | 6,700 |
| Correct / incorrect trajectories | 924 / 5,776 |
| Annotated steps | 44,833 |
| Supervised binary steps | 41,607 |
| Neutral/masked steps | 3,226 |
| Positive / negative targets | 35,831 / 5,776 |
| Problem overlap | 0 |

Counted exclusions over the full shard were 20,751 QC/screening rows, 3,048
unfinished/bad-problem rows, 162 conflicting duplicate-rating rows, 28
solution-with-error rows, and one invalid/missing rating row.

## Coverage improvement

The bounded 5,000-row source staging covered only generations 8 and 9. The
full-shard sample covers **all generations 0 through 9**:

| Generation | Trajectories |
|---|---:|
| 0 | 158 |
| 1 | 193 |
| 2 | 469 |
| 3 | 759 |
| 4 | 829 |
| 5 | 953 |
| 6 | 898 |
| 7 | 1,633 |
| 8 | 658 |
| 9 | 150 |

Reasoning length spans 1 through 43 annotated steps, and first errors occur
throughout the trajectory, including early, middle and late positions.

## Interpretation

This audit resolves the main **generation-coverage** weakness of the earlier
bounded-prefix staging. It does **not** mean that all 6,700 trajectories should be
translated and used directly for training.

The source pool is strongly error-heavy: 5,776 incorrect trajectories versus
924 correct trajectories. Translating every selected trajectory would also mean
reviewing 44,833 annotated steps. The 1,000-problem output is therefore an
**audited production source pool**, not the final ArabicPRM-T training corpus.

The next corpus-design step is to freeze a deterministic subset-selection policy
from this pool that improves class balance while preserving generation coverage,
reasoning-length diversity, neutral-step coverage, and early/middle/late error
positions. Mathematical-domain coverage still requires an upstream mapping or
documented annotation; it must not be inferred casually from filenames or text.

Global-MGSM was not accessed. No translation or model training was performed in
this audit.
