# Experiment and evidence registry

| ID | State / evidence | Result / limitation |
|---|---|---|
| Frozen-v2-selection | Verified from frozen queues and manifest; source revision `7ecc794703b2877f63226f2477a49b34f9b25163` | 256 unique source problem groups; 204/52 train/dev; no group leakage |
| Historical-v1-registry | Existing immutable accepted registry; separate cohort | Recorded 32 records; no new human review performed here |
| Recovery-v1-baseline | Actual original plan read-only | 1,075/2,252 fields mechanically complete; nine historical attempts per unresolved slot |
| Recovery-v1-pilot20 | User-reported completed; actual report/HTML missing | Reported 20 requests / 20 accepted fragments / zero remaining. Semantic results and post-pilot field totals unknown. Permanently closed; never reset |
| Repository-strict-audit-v2 | Reproducible offline audit of 64 committed drafts | 45 complete records under current strict checks; 35 field failures requiring investigation; not a semantic-error rate |
| Strict-policy-case-inspection | Three Batch01 failures inspected read-only; see STRICT_REVALIDATION_NOTES_V2.md | One English compound math-span false positive and two frozen-environment annotation differences observed; no general category totals, parser fix, draft edit or human QC |
| Recovery-v2-prototype | Verified at 270d537 and 2ce19a1; Windows/Linux CI 39053835394 and 39055459666 passed | Context/glossary/risk heuristics and pending human UI; full ledger integration and immutable restart verified on synthetic evidence; no model results or inference allowance |
| Recovery-v2-paired-diagnostic | Source-risk proposal: 12 slots / 24 requests, pending actual-pilot audit and design review | No approved budget; no generated outputs; no comparison result; source-only plan context verified |
| Recovery-v2-Windows-offline-launcher | Verified publication 0ef991f, CI 39056158971; 245 tests each on Windows/Linux plus native package/CMD checks | Pins tested implementation 2ce19a1; SHA256 67320c2326cb109e8697b31b43eddf14c0772ab7c016ec3926c86ce1415335f5; no model access or old budget reuse |
| Downstream PRM / QLoRA | Offline contracts/config/methodology implemented; six tests passed on both platforms in CI 39055459666 | No trainer, run, export or GPU feasibility claim; historical scripts unsafe to import offline |

Raw private laptop approvals, attempt ledgers, checkpoints and unapproved outputs remain local. Public records contain aggregate evidence and artifact identities only. Software tests use deterministic synthetic responses and establish software behavior, not translation accuracy.
