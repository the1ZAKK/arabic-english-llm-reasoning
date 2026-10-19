# Session handoff

## Current evidence update — 2026-10-19

Remote head was 2394467dbce62a1fc9adbb9e1b7872ce392beba6 at session start. Actual `semantic_audit.json` and `provisional_bilingual_QC.md` have now been supplied and independently revalidated. See [PILOT20_FINDINGS_V2_1.md](PILOT20_FINDINGS_V2_1.md) and the public safe aggregate. All 20 hashes, frozen contexts, old analyses, initial order and entire completion inventories reproduce; Markdown matches exactly. The audit canonical identity is 3942a346a653ee2c3f579f7a0ae83d1f83c6bba722336cf1a4a2180d44aaefec. Raw ledger/approval/report/HTML were not uploaded, so reservation accounting is laptop-attested, not cloud-replayed. Actual generation was v1, not the proposed v2 prompt.

Post-pilot Batch09–32: 1,089 complete / 1,163 remaining fields, 1,985 missing slots, 11 complete / 174 partial / 7 no-complete-field trajectories. Human QC pending; semantic approval not established. Subtraction/geometry/interval/grammar issues and separate original score/circle reasoning errors are documented. Source native ratings (including negative score and positive circle steps) remain unchanged. Develop separate v2.1 files and tests, not edits to historical v2 evidence or original plan-bound code. The older missing-output paragraphs below describe the prior session only.

The latest verified **code and launcher** milestone is `0ef991fdbf2a0fe3cf0269aabfcc3665637ee870`: [CI 39056158971](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39056158971) passed 245 offline tests on both Windows and Linux, native recovery-v2 package verification and real CMD correct/incorrect-installer-hash checks. Legacy scheduled-task execution was skipped. The containing final handoff commit changes documentation only; verify its branch head and attached checks when resuming. No continuing background execution is implied.

## Durable milestones

| Commit | Work | CI |
|---|---|---|
| `65e803620919324b89adf88b2e74e1d23365d4ca` | Read-only project inventory and five permanent project records | [39053290606](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39053290606), Windows/Linux success |
| `270d537965fef20604d993d07afb7ceb9d72ab27` | Separate context/glossary/risk prototype, exact completion inventory and pending bilingual UI | [39053835394](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39053835394), 232 tests each |
| `2ce19a17570829495856da1f732d96b06694f402` | Immutable offline Windows package, full closed-ledger audit, downstream contracts and research protocol | [39055459666](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39055459666), 244 tests each + native package |
| `0ef991fdbf2a0fe3cf0269aabfcc3665637ee870` | Pinned single CMD, exact CRLF SHA256 and native tampered-hash rejection | [39056158971](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39056158971), 245 tests each + native package/CMD |

Only branch `research/arabicprm-v2-production` is authorized. No force push or main modification. All 13 original plan-bound code hashes remain unchanged from the original execution workflow `4434b29fdbce65abf13fcbd8ede03223c7e106b1`. Frozen sources, locks, original supervisor/checkpoints, retry history, accepted translations and recorded human QC are preserved.

## Verified evidence and unresolved scientific work

Frozen selection: 256 records / 2,753 steps / 3,009 fields; 204 train and 52 dev, unique source groups without train/dev overlap. Batch01–08: 64 committed AI assistant drafts pending human QC, 757 fields, 45 whole records pass current strict checks and 35 fields fail. Batch09–32 original plan: 192 records / 2,252 fields, 1,075 mechanically complete and 1,177 unresolved / 2,005 missing slots. Original record status is 9 all-fields complete, 176 partial and 7 no-complete-field trajectories. Source-only preparation verified all 2,005 contexts and the public 12-slot proposal's context/request hashes.

`STRICT_REVALIDATION_NOTES_V2.md` inspects three strict failures: an English compound `a two-` misclassified as a mathematical literal, plus two translated annotation cases inside whole frozen LaTeX environments. These qualify the mechanical-policy result, not the semantic-error count. No parser or draft was modified. A future segmentation design must remain separately versioned and preserve the original plan/artifacts.

The user reports pilot20 exhausted with 20 accepted fragments. The actual `report.json` and `pilot_review.html` have **not** been supplied in Work; they were requested once. Three uploaded text files contain directives, not pilot output evidence. Do not treat the counts as independently verified, invent Arabic candidates, claim semantic accuracy or calculate post-pilot complete-field counts. The old 20-request allowance is closed forever and must never be reset, renewed or reused.

## Delivered offline Windows workflow

Use [RECOVERY_V2_WINDOWS.md](RECOVERY_V2_WINDOWS.md) and its exact verified CMD URL. `verify_semantic_recovery_windows_v2.cmd` pins implementation `2ce19a17570829495856da1f732d96b06694f402`; exact CRLF SHA256 is `67320c2326cb109e8697b31b43eddf14c0772ab7c016ec3926c86ce1415335f5`. It fetches SHA256-verified GitHub code and does not contact Ollama. The laptop's existing report/HTML and full original ledger/witness/checkpoint are checked read-only. New artifacts live under `recovery_artifacts/recovery-v2/<plan>/<audit>/`: `semantic_audit.json`, `provisional_bilingual_QC.md`, `human_review.html`, pending decisions, inactive experiment proposal and hash manifest. The browser review defaults all decisions to pending and records only actual reviewer-entered decisions in a separate download. It grants no training eligibility. Original v1 artifacts remain untouched.

Private `/recovery_artifacts/` is Git-ignored. Do not force-add approvals, reviewer identities, private paths, raw ledgers, sensitive checkpoints or unapproved outputs. Publish only code and permissible aggregate evidence.

## Next safe action and authorization gates

1. Read actual pilot report/HTML when available, verify accounting/provenance against the exact plan/model/20/2/512 constraints, and perform the complete provisional bilingual analysis of every recorded outcome. Use the laptop offline tool for full reservation proof. Keep unsupported judgments unsupported and source reasoning errors separate from translation errors.
2. Genuine bilingual reviewers must act before human QC is complete. Corrections never replace original output; independently review corrections and retain initial decisions/adjudications.
3. The proposed diagnostic is at most 24 **new** requests: 12 source-paired slots, isolated-v1 payload versus context/glossary-v2, one request per slot/arm, 512 tokens, exact original qwen3 digest. It is not approved, has zero authorized requests and no execution runner. First review the actual pilot and design, then obtain a separate explicit budget and reviewed runtime. Never reuse pilot20.
4. Downstream `research_contracts_v2.py` and `prm_research_config_v2.json` are pure offline alignment/masking/metrics/readiness preparation, not a trainer/exporter. Genuine QC, complete aligned data, reward-position tests, model/environment pins, measured GPU feasibility and explicit training/export permission remain required. Legacy GPU scripts load models at module scope: inspect with AST, never import for offline checks.
5. `RESEARCH_PROTOCOL_V2.md` is a methodology/thesis working draft with verified aggregates and unknown-result placeholders. No new inference, training, export, model download, task installation or Global-MGSM access occurred. Do not claim the project is scientifically complete or that CI proves translation quality.

Continue safe work when genuine new evidence arrives, verify current GitHub state first, and update the status/roadmap/registry/decisions/handoff after meaningful verified milestones.

## Recovery-v2.1 development milestone

Evidence commit aceacd47bedcc1cb1122f6a6986091e8b5f04bfb passed CI 39219153070: 249 tests each on Linux/Windows plus native checks. New v2.1 files preserve old v2 bytes: `semantic_policy_v2_1.py`, glossary v1.1, follow-up/review Python and JS, and separate offline runtime/installer. New UI can load prior v2.1 decisions, preserves unchanged reviewer/timestamp fields, and requires attestation for changed non-pending decisions. AI analysis is collapsed; original output, correction proposal and English/source-label cautions are separate.

All20 provisional AI case findings: two serious meaning/operation risks, one terminology/sentence issue, three agreement review cases (two interpretation/register dependent), fourteen with no identified issue. Not human labels or a quality estimate. Revised inactive diagnostic proposal 4327d769e30fdf2324d0d8000b4c828d3d311917993987af23c98687f1e0aa6d has twelve pairs across seven problems, including observed errors and fresh controls, 24 maximum new reservations, one per slot per arm, 512 tokens. No executor or budget exists. See the exact gates in RECOVERY_V2_1_DIAGNOSTIC_DECISION.md. Complete the current implementation CI before declaring the new milestone verified.
