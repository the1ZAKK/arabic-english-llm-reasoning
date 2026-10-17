# Experiment and evidence registry

| ID | State / evidence | Result / limitation |
|---|---|---|
| Frozen-v2-selection | Verified from frozen queues and manifest; source revision `7ecc794703b2877f63226f2477a49b34f9b25163` | 256 unique source problem groups; 204/52 train/dev; no group leakage |
| Historical-v1-registry | Existing immutable accepted registry; separate cohort | Recorded 32 records; no new human review performed here |
| Recovery-v1-baseline | Actual original plan read-only | 1,075/2,252 fields mechanically complete; nine historical attempts per unresolved slot |
| Recovery-v1-pilot20 | User-reported completed; actual report/HTML missing | Reported 20 requests / 20 accepted fragments / zero remaining. Semantic results and post-pilot field totals unknown. Permanently closed; never reset |
| Repository-strict-audit-v2 | Reproducible offline audit of 64 committed drafts | 45 complete records under current strict checks; 35 field failures requiring investigation; not a semantic-error rate |
| Recovery-v2-prototype | Development only | Context/glossary/risk heuristics; no model results, approval identity or inference allowance |
| Recovery-v2-paired-diagnostic | Proposal pending actual-pilot audit and design review | No approved budget; no generated outputs; no comparison result |
| Downstream PRM / QLoRA | Preparation only | No run, no export, no GPU feasibility claim; historical scripts unsafe to import offline |

Raw private laptop approvals, attempt ledgers, checkpoints and unapproved outputs remain local. Public records contain aggregate evidence and artifact identities only. Software tests use deterministic synthetic responses and establish software behavior, not translation accuracy.
