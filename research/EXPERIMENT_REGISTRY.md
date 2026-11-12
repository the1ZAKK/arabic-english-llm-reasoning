# Experiment and evidence registry

v3.1 scoring continuation — read-only [replay](PERFORMANCE_GAP_DIAGNOSIS_V3_1.json)
binds the preserved thirteen v3 inputs and reports rounding robustness. The
[recorded scoring analyzer](SCORING_DIAGNOSIS_V3_1.md) validates condition roles,
exact input-token identity, source Unicode offsets, reward boundaries, missing
cells and matched four-cell interactions using synthetic tests only. It executes
zero model forwards. [Reranking operations](RERANKING_OPERATIONS_V3_1.md) now bind
automated choices independently of outcomes and human canonical keys, and label
expert-assisted voting explicitly. New native data, human labels, model records,
training, active allowances and export: none. Real downstream efficacy is missing.

v3.1 offline milestone — [feasibility planner](BENCHMARK_FEASIBILITY_V3_1.md)
compares six size/origin options, including native authoring, permissions screening,
reference checks, two-assessor Arabic labels/outcomes, limited English mirrors and
adjudication. Exact independent paired-test power is checked by exhaustive small
outcomes and null rejection rates; clustered effective-n is explicitly heuristic.
New native items/labels, model observations and active allowances: zero. Recorded
reranking now rejects contradictory canonical-answer outcomes and reports the
oracle/selection distinction. No original candidate or human record was edited.

Verification for this continuation: 558 local offline tests passed (62.690 s), comprising the prior 525 and 33 new audit/native-study regressions. CI sparse inputs now include the three existing model-utility source files, never model weights; the helper is parsed and its preparer is probed only with a synthetic tokenizer. Original thirteen audit inputs are unchanged, with exact-byte Git attributes for reproducibility. The published commit’s Windows/Linux Actions jobs are the cross-platform evidence, not semantic or human approval.

Retained-scoring continuation: the [source-bound pipeline audit](RETAINED_EVIDENCE_AUDIT_V3.md#scoring-pipeline-and-precision-audit)
identifies 160 blank-line reward positions per language and explicitly different
quantization declarations across the old base/adapted runners. Rounded-score
aggregation excluding blank positions retains an EN–AR gap difference about
0.2277; this is a sensitivity analysis, not regenerated scores or a complete cause.
The audit now hashes thirteen named inputs, including the unchanged helper source.
Future matched-precision unadapted-base scoring is needed before adapter-only
attribution. No source, checkpoint, translation or human record is repaired.

2026-11-12 — Native-study v1 preparation: [scientific protocol](ARABIC_NATIVE_STUDY_V3.md),
[human rubric/provenance](ARABIC_NATIVE_BENCHMARK_V1.md), and pure offline metadata,
paired gap/Brier, fixed-pool reranking and sample-size analysis. All test inputs
are synthetic; target 500 groups/240-native test is prospective. Actual native
items, human annotations, candidate pools and new scorer observations: **none**.
No native benchmark performance, downstream gain, generation, training, dataset
release, budget or human endorsement. Original translated-corpus accounting is
retained in the [short supporting QC table](TRANSLATION_QC_SHORT_PROTOCOL.md).

2026-11-12 — Retained-evidence audit v3: deterministic read-only replay, twelve SHA256-bound inputs, 20 matched problem IDs/80 rows per scoring set, pilot dev ten groups/79 steps. All original result bytes retained. New aggregate output: [RETAINED_EVIDENCE_AUDIT_V3.json](RETAINED_EVIDENCE_AUDIT_V3.json). No inference, training, new human labels or downstream result. Previously named generalization/retention runs reuse original examples and must be interpreted as selected-set comparisons.

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
| Recovery-v2.1-diagnostic-design | NOT APPROVED; canonical proposal 4327d769e30fdf2324d0d8000b4c828d3d311917993987af23c98687f1e0aa6d | 12 pairs / 7 source problems; max24 new reservations, 1 per arm / 2 per slot, 512 tokens. Separate executor verified; no active approval |
| Diagnostic24-executor-and-preparation | Publication 9b002e3; [CI 40169998501](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/40169998501), 335 tests each and native Windows checks | Fixed 24/2/1/512 allowance protocol, immutable witnesses, safe resume and blinded queue implemented; zero authorized or executed diagnostic requests |
| Diagnostic24-offline-assessment | Separate assessment import/seal and paired report; [workflow](DIAGNOSTIC24_ASSESSMENT_V2_1.md) | Software and synthetic/public-empty-source tests only; no new diagnostic observations, actual reviewer labels, efficacy estimate or human-QC completion |
| Diagnostic24-review-comparison | Separate [comparison of two sealed assessments](DIAGNOSTIC24_REVIEW_COMPARISON_V2_1.md); arm mapping is not read | All24 outputs retained, error agreements and reviewer differences separated, correction proposals pending; no actual assessments, authenticated independence, automatic adjudication or new allowance |
| Diagnostic24-design-review | [AI source/selection audit](DIAGNOSTIC24_AI_DESIGN_REVIEW_V2_1.md) and bilingual [source-only package](DIAGNOSTIC24_DESIGN_REVIEW_V2_1.md); all12 contexts/24 payloads match, actual private-plan selection replayed | Seven clustered problems; complete policies compared, not glossary ablation. Human design decision and budget remain pending; no new outputs, source/label changes, efficacy estimate or human-QC completion |
| Diagnostic24-independent-adjudication | [Separate human adjudication workflow](DIAGNOSTIC24_ADJUDICATION_V2_1.md), following design package63ab397 / CI41184975964 (404 tests each) | Exact sealed comparisons and correction hashes; third recorded identity/disclosures required, missing/unresolved cases retained; AI evidence never becomes human primary review, corrections unapplied and development gate never auto-passed |
| Diagnostic24-handoff-followup-v2.2 | [Independent AI design follow-up](DIAGNOSTIC24_AI_HANDOFF_REVIEW_V2_2.md), zero-request report auditor and supplementary semantic notes | Local preparation passed according to user handoff, not newly cloud-replayed report bytes; twelve source contexts verified, reused groups corrected, conjunction/clitic regression gaps recorded; zero inference, human approval or frozen-runtime change |
| Diagnostic24-blinded-interface-v2.2 | Separate [self-contained neutral draft form](DIAGNOSTIC24_BLINDED_INTERFACE_V2_2.md), following `90fb484` / [CI 41200983458](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/41200983458), 446 tests each | All 24 positions, source/candidate binding, fixed assessor kind, actual metadata and safe resume; no mapping/AI hints, automatic QC, correction application or allowance. Drafts require unchanged Python validation and sealing; no actual human evidence created |
| Diagnostic24-v2.2-verified-readiness | Code `f24b835`; [CI 41202286513](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/41202286513), **465 tests each Windows/Linux**, native guards passed; tasks skipped | [Final decision package](DIAGNOSTIC24_REVIEW_READINESS_V2_2.md): technically ready for genuine human design review, actual review/independence and owner/local consent still pending. Frozen identities unchanged; no active budget, output, human approval, training or export |
| Diagnostic24-native-browser-v2.2 | Separate [native browser verifier](DIAGNOSTIC24_BROWSER_VERIFICATION_V2_2.md); new CI evidence pending | Installed Chrome/Edge and matching drivers only; public/empty and synthetic fixtures; real DOM/CSP, Blob JSON and native-file resume. Zero generation, no human approval or frozen-runtime change; screenshots require inspection |
| Diagnostic24-browser-failure-followup | `e975d67` / [CI 41211169902](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/41211169902) failed closed; fixture screenshots retained | Narrow-layout and loopback test-transport fixes implemented separately; renewed Windows/Linux CI pending. No model inference, budget activation, frozen experiment migration or human approval |
| Diagnostic24-observed-browser-v2.2 | `49126bf` native steps passed in [CI 41211729105](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/41211729105); artifact digests/screenshots inspected | Chrome actual 390 px; Edge actual 492 px. Fixture-only CSP, all 24 positions, metadata/resume and hard correction validation passed. Separate Arabic typography improvement and renewed CI pending; human review/authorization remain outstanding |
| Diagnostic24-browser-portable-snapshot | Real browser steps passed; full Windows run 41211729105 detected one path-key assertion failure | Canonical relative metadata keys fixed without changing source bytes or protected hashes; renewed full CI pending. No translation result, human approval, budget or frozen-identity change |
| Diagnostic24-native-browser-verified | `f86fec8` / [CI 41212959885](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/41212959885), **477 tests each**, real browser and native Windows guards passed; tasks skipped | [Verified results](DIAGNOSTIC24_BROWSER_RESULTS_V2_2.md), inspected fixture screenshots, portable paths and read-only LF/CRLF replay; frozen identities/data unchanged, human review and separate execution authorization pending |
| Restart observation and v2 QC workload | [e435fa6](https://github.com/the1ZAKK/arabic-english-llm-reasoning/commit/e435fa6e9e2ca07ead8810df7d0155466a0900e9), [CI 41636006966](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/41636006966), [restart checker](WINDOWS_RESTART_CHECK_V1.md), [aggregate replay](CORPUS_QC_WORKLOAD_V2_2.md) | 1,089/2,252 mechanically complete later-batch fields; 1,985 missing slots; 35 early-batch field failures stratified for review. No fresh laptop observation, human review or generation authorization. |
| Windows sync preflight | [Private backup and comparison](WINDOWS_SYNC_PREFLIGHT_V1.md) | Exact older HEAD was an ancestor; dirty files require local review. No checkout update, experiment allowance, generation or human approval. |
| Separate clean development checkout | [Pinned Windows package](WINDOWS_CLEAN_DEVELOPMENT_V1.md) | Offline development environment only; no private evidence migration, diagnostic budget, experiment or human approval. |
| Diagnostic24 prospective analysis v2.3 | [Design audit and scoring plan](DIAGNOSTIC24_DECISION_PACKAGE_V2_3.md) | 12 purposive pairs, seven groups, no outcomes. Dual weighting and missingness bounds; pending genuine design review and separate execution consent. |
| Early v2 selection attrition | [Aggregate mechanical coverage](CORPUS_QC_METHOD_V2_3.md) | Of 722 individually passing fields, 224 are in blocked trajectories. Cohorts remain separate; no semantic labels or approvals. |
| Prospective early-draft probability audit v2.4 | [Frame, workloads and finite-population scenarios](CORPUS_QC_SAMPLING_PLAN_V2_4.md) | No capacity selected, sample drawn or human reviews. Includes mechanical passes and blocks. |
| Downstream PRM / QLoRA | Offline contracts/config/methodology only | No training/export, model download, GPU resource measurement or downstream result |

[Findings](PILOT20_FINDINGS_V2_1.md) and [diagnostic decision](RECOVERY_V2_1_DIAGNOSTIC_DECISION.md) are provisional AI research review. Current all20 review findings are not human labels, held-out accuracy or evidence that v2.1 improves generation. Newly added regression cases are development fixtures. Raw private outputs, approval identities, attempt ledgers, checkpoints and human-review records remain private; Git contains code, deterministic test fixtures, source-bound inactive proposals and permissible aggregate evidence only.

GPT Work AI-review follow-up: the user requested completion by GPT rather than manually filling the human form. [AI-review workflow](AI_REVIEW_WORKFLOW_V2_1.md) records all20 explicit contextual decisions in a separate AI-only report: 14 provisionally acceptable, four clear revision recommendations, two context/style advisories. Human QC remains pending; the AI record cannot validate as human approval or a recovery budget. Original records and the tested launcher remain unchanged; no new Ollama requests are authorized or sent.

Diagnostic24 runner and preparation launcher are verified at `9b002e3665ab4100336ba1cd0e78015676bbcb2f` ([CI 40169998501](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/40169998501)): 335 tests per platform and native Windows hash/mode checks passed. See [the runner workflow](DIAGNOSTIC24_RUNNER_V2_1.md). Local protected-history verification, separate explicit design/budget approval, exact installed model verification and a final laptop execution confirmation remain required. The old 20-request allowance remains closed; no real diagnostic approval or generation exists, and human QC stays pending.
