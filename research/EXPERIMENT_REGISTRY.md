# Experiment and evidence registry

| ID | State / evidence | Result / limitation |
|---|---|---|
| Frozen-v2-selection | Source revision 7ecc794703b2877f63226f2477a49b34f9b25163 verified | 256 unique source groups; 204/52 train/dev; 2,753 steps; no train/dev group leakage |
| Historical-v1-registry | Existing immutable accepted registry; separate cohort | Recorded 32 records / 298 steps; no new human QC here; not v2 completion |
| Recovery-v1-baseline | Original plan 446191b8; unchanged | 1,075/2,252 mechanically complete fields; historical nine attempts per unresolved slot |
| Recovery-v1-pilot20 | Actual derived laptop audit 3942a346 and exact Markdown revalidated; generation prompt msa-single-fragment-v1 | 20 mechanically accepted fragments; +14 fields / +2 trajectories. Twenty charged / zero left and reservation proof laptop-attested, not cloud-replayed. Permanently closed |
| Repository-strict-audit-v2 | Reproducible current-policy audit of 64 committed drafts | 45 whole records pass; 35 field failures across 19 records; not a semantic-error rate |
| Strict-policy-case-inspection | Three cases investigated read-only | English compound math-span false positive and two frozen-LaTeX annotation differences; no parser/draft edit or human decision |
| Recovery-v2-prototype | Historical separate prompt/glossary/risk prototype; CI 39053835394 and 39055459666 passed | Source-only proposal and pending-review UI; no v2 model-generation result |
| Recovery-v2-Windows-v2.0 | Publication 0ef991f; CI 39056158971, 245 tests each plus native package/hash checks | Historical launcher pins 2ce19a1; preserved unchanged; user used it to produce the uploaded derived audit |
| Pilot20-derived-evidence-v2.1 | aceacd47; CI 39219153070, 249 tests per platform | All20 item/source/output/context hashes, exact Markdown, original analyses and entire inventories independently reproduced. Source/label errors separated |
| Recovery-v2.1-policy-and-QC | Implementation 25d308f; exact proposal/glossary binding f8fba2b; CI 39221246449 | Separate policy/glossary, observed/false-positive regressions, all20 provisional case notes, immutable QC import/resume. Both platforms passed 282 offline tests (Linux 53.045 s; Windows 320.236 s), including native Windows v2.1 packaging. Scheduled-task execution was skipped. CI validates software behavior, not semantic quality. |
| Recovery-v2-paired-diagnostic-original | Original source-only v2 proposal retained unchanged | Superseded for prospective review by v2.1; never approved or executed |
| Recovery-v2.1-diagnostic-design | NOT APPROVED; canonical proposal 4327d769e30fdf2324d0d8000b4c828d3d311917993987af23c98687f1e0aa6d | 12 pairs / 7 source problems; max24 new reservations, 1 per arm / 2 per slot, 512 tokens. No executor or active approval |
| Downstream PRM / QLoRA | Offline contracts/config/methodology only | No training/export, model download, GPU resource measurement or downstream result |

[Findings](PILOT20_FINDINGS_V2_1.md) and [diagnostic decision](RECOVERY_V2_1_DIAGNOSTIC_DECISION.md) are provisional AI research review. Current all20 review findings are not human labels, held-out accuracy or evidence that v2.1 improves generation. Newly added regression cases are development fixtures. Raw private outputs, approval identities, attempt ledgers, checkpoints and human-review records remain private; Git contains code, deterministic test fixtures, source-bound inactive proposals and permissible aggregate evidence only.

GPT Work AI-review follow-up: the user requested completion by GPT rather than manually filling the human form. [AI-review workflow](AI_REVIEW_WORKFLOW_V2_1.md) records all20 explicit contextual decisions in a separate AI-only report: 14 provisionally acceptable, four clear revision recommendations, two context/style advisories. Human QC remains pending; the AI record cannot validate as human approval or a recovery budget. Original records and the tested launcher remain unchanged; no new Ollama requests are authorized or sent.
