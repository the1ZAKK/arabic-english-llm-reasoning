# ArabicPRM-T v2 research protocol and thesis working draft

Status: evidence-grounded methodology plus **planned** experiments. No new inference, human semantic acceptance, training, model download or corpus export occurred in this work. Preserve all earlier experiment files and genuine recorded QC decisions. Current safe aggregates are in [PROJECT_STATUS.md](PROJECT_STATUS.md); unknown results stay unknown.

## Questions and hypotheses

RQ1: Can strict script, numerical, mathematical and reasoning-boundary checks produce auditable Arabic translations while retaining native PRM labels? Verified software checks establish structural constraints, not semantic equivalence. RQ2: Does source sentence/context plus a curated terminology glossary reduce mathematical translation errors relative to isolated fragments for the same local model? Hypothesis only; the 24-request source-risk proposal has not run. RQ3: How do bilingual agreement, correction burden and source-reasoning defects affect usable corpus yield? Genuine review evidence is missing. RQ4: Does a separately authorized PRM adaptation on reviewed aligned Arabic improve held-out process scoring relative to English/unaltered baselines? Not tested here.

## Corpus construction and provenance

Frozen selection is 256 trajectories, 204 train and 52 dev, 2,753 annotated steps from unique problem groups. Source revision, full-shard hash, selection hashes and per-record identities are recorded in `RECOVERY_V2_EVIDENCE.json`. Respect existing problem-group splits; do not reshuffle related English/Arabic variants across train/dev. The 32-record historical accepted v1 registry is a separate cohort and cannot be added to v2 completion. Preserve native ratings and source error steps even when the English reasoning is wrong; source defect and translation defect are different axes.

Batch01–08 includes 64 AI assistant drafts pending human QC. Current strict validation finds 45 fully passing records and 35 field failures across the other 19; this is a revalidation backlog, not a semantic-error rate. Batch09–32 has 2,252 fields: original 1,075 mechanically complete / 1,177 unresolved, 2,005 missing prose slots. Original-plan record status is 9 complete / 176 partial / 7 no-complete-field. An accepted slot only completes a field if all other slots are present and exact source literals validate. Full trajectories require every problem/step field. Actual post-pilot counts need the authentic report, not arithmetic applied to the user-reported 20 fragments.

## Translation/recovery method

Freeze English, slot boundaries, math expressions, numerical order, checkpoint hashes and original nine-attempt history. Recovery-v1 `msa-single-fragment-v1` solved a script-compliance engineering problem; user reports 20/20 Arabic fragments accepted, but its outputs have not been independently read in Work. The original model digest is fixed and the 20-request allowance permanently closed. The separate `msa-context-glossary-v2` prototype quotes source context, suggests mathematical terminology, and flags operation, relation, geometry, ordinal and quantity risks. See [RECOVERY_V2_METHOD.md](RECOVERY_V2_METHOD.md). No actual superiority claim is justified before paired results.

For any future run, pre-register exact model/revision or digest, prompt/glossary/payload hashes, plan identity, sample IDs, request/token/per-slot limits, ordering, timeout, seed and decoding settings. Failures/crashes consume reservations; fsync before HTTP, preserve an external dispatch witness and fail closed on corrupt or rolled-back state. Use a separate approved budget and reviewed execution runtime. Do not reactivate the old template or completed pilot.

## Semantic review and adjudication

First perform a provisional AI audit against the authentic source-context/output pair, then two independent bilingual mathematical reviewers where available. Show full problem, all reasoning steps, exact target, recorded Arabic, risk flags and provenance; blind prompt arm and randomize presentation within source-paired blocks for a future experiment. Keep decisions pending until the reviewer acts. Record original-output decision, five-category error class, severity, justification, actual reviewer identity/time, optional measured duration and separately proposed correction. Approving a different corrected string requires a later independent review of that new string. Never overwrite the original model output or earlier decision.

Report agreement as the full category/severity confusion matrix plus raw agreement and chance-adjusted agreement where denominators support it. Retain both reviewers' initial decisions and a separate adjudication event with rationale; abstentions and unavailable outputs remain unsupported. Source-reasoning warnings are reviewed independently and never silently repaired. A reviewer attestation is a provenance record, not an authenticated identity system. Human semantic approval alone does not authorize training/export.

## Diagnostic design and metrics

The deterministic proposal selects up to 12 distinct risk-stratified source slots and compares isolated and context/glossary payloads in a **new** experiment: 24 proposed requests, one per slot/arm, 512 generated tokens each, no automatic retries. This is provisional until actual pilot audit and human design review. It is an engineering diagnostic, not a random accuracy sample. Existing pilot outputs may inform failure discovery but cannot substitute for paired new-arm baseline outputs with matching conditions. A later ablation could separate context alone, glossary alone and their combination; it is not included in the proposed 24 requests.

Primary diagnostic endpoint: human semantic acceptability of the original candidate. Secondary endpoints: script/boundary compliance per charged request, exact literal fidelity after source-owned assembly, operation/relation/entity preservation, correction/abstention rates and median review duration. Include failed and interrupted requests in the request denominator; report partial slot and full-field yield separately. Count a budgeted request once even if retried elsewhere. Report every stratum, source ID, outcome and missing review instead of only successful cases.

The offline statistical helpers implement Wilson intervals and an exact two-sided McNemar calculation for **independent paired units**. Multiple slots from one problem are correlated: use source-problem aggregation or a pre-registered problem-cluster bootstrap for inferential reporting, and clearly state the small sample and deliberate selection. Do not apply a slot-level binomial p-value to a clustered sample as proof of improvement. The 12-slot diagnostic will often have little power; failure discovery and estimates with limitations are its purpose. Do not interpret a possible 20/20 mechanical result as universal compliance or semantic accuracy.

## Downstream PRM preparation

`research_contracts_v2.py` implements standard-library alignment, neutral masking, numerically stable masked BCE, read-only split leakage checks, supervised-step confusion counts, balanced accuracy, per-class recalls, Brier score and clipped log loss. Tests use synthetic logits/probabilities plus frozen source alignment only. These are offline contracts, not a trainer or evidence of learned performance. Native +1 -> target 1/mask 1; -1 -> target 0/mask 1; neutral 0 -> null/mask 0. Never coerce null into a negative label. No later unannotated source step receives a fabricated label. A future tokenizer must align reward positions with original annotated steps; reject length truncation that loses targets rather than silently dropping labels. Aggregate loss over supervised steps, not padded or neutral positions.

The legacy training/evaluation scripts instantiate models at module scope and do not support the neutral-mask/variable-trajectory contract documented by the original corpus README. They were inspected with AST, never imported. A future import-safe trainer needs an explicit main entry point, exact model/tokenizer revision, locked GPU environment, reward-head/position compatibility tests, supervised loss-mask implementation, reproducible checkpoints/seeds and genuine human-approved derived data. Reserve dev for evaluation; select hyperparameters through a documented group-aware training-side protocol. Pre-register the PRM threshold and first-error localization method before reading final dev results. Report source group/trajectory counts, class balance, masked counts, calibration and paired English/Arabic comparisons. No Global-MGSM or other prohibited dataset is needed or accessed.

`prm_research_config_v2.json` is an inactive design contract, not a runnable framework configuration. It records unvalidated resource-probe candidates for the historically used 1.5B PRM, distinct from the qwen3 translation model. Actual revision and environment locks are deliberately null until verified. A 4-bit weight lower bound is not total training memory: adapters, unquantized layers, activations, gradients, optimizer state and framework allocations also matter. No 4 GB fit is established. After separate authorization, measure peak allocated/reserved VRAM and wall time at batch 1 and short aligned sequences before choosing a configuration; don't assume CPU offload or BF16 works on this laptop. No resource probe is authorized by this document.

Primary software references: [PEFT quantization](https://huggingface.co/docs/peft/main/developer_guides/quantization) describes 4-bit base weights with trainable adapters, `prepare_model_for_kbit_training` and QLoRA-style linear-layer targets; [Transformers bitsandbytes](https://huggingface.co/docs/transformers/main/quantization/bitsandbytes) documents quantization and hardware support. Documentation was inspected, not installed or executed. Actual GPU-version pins must be chosen and tested in a future authorized environment, rather than invented here.

## Results ledger and thesis placeholders

| Analysis | Evidence / value | Interpretation |
|---|---|---|
| Frozen source inventory | 256 records; 2,753 steps; 204/52 train/dev; zero group overlap | Verified provenance, not translation quality |
| Current draft strict checks | 45/64 whole records; 35 field failures | Software policy revalidation, not semantic-error count |
| Original Batch09–32 complete fields | 1,075/2,252 | Baseline mechanical completeness only |
| Actual pilot requests and outputs | User reports 20 requests / 20 accepted; actual files unavailable | Unverified in Work; no invented bilingual judgments |
| Pilot semantic accuracy / correction rate | Unknown | Requires authentic outputs and genuine review |
| Recovery-v2 versus v1 | Not run | No efficacy claim |
| Human inter-reviewer agreement | Not measured | Human QC remains pending |
| QLoRA memory/performance | Not measured here | Preparation only; no training/export |
| PRM held-out gains | Unknown | No new evaluation result |

Discussion draft: source-preserving assembly can make literal changes observable while allowing lexical semantic errors to pass. Context and terminology are plausible interventions whose effect remains untested. Source reasoning errors complicate QC and must remain distinguishable from translation failures. Limitations include selected small samples, sparse negative labels, pending bilingual judgments, context-window blocking, heuristic false positives/negatives, unmeasured hardware feasibility and missing real pilot evidence. Conclusions must remain limited to reproducible engineering behavior until authorized experiments and genuine reviews supply results.

## Reproduction and completion gates

Use only `research/arabicprm-v2-production`; preserve main and original research records. Run the selected standard-library tests on Windows and Linux, plus native PowerShell/CMD hash rejection and frozen-source packaging checks. No CI job contacts Ollama or runs GPU code. Pinned launcher receipts bind canonical Git blobs by SHA256 and leave worktree/checkpoints unchanged. Local reports, reviewer identities and raw ledgers stay private; publish only permissible aggregate summaries. Update the five durable project records after verified milestones.

Next indispensable evidence: authentic pilot report and HTML (already requested once), then actual bilingual review. Next execution gate: separately approve the proposed diagnostic design/budget and a reviewed bounded runtime. Training and reviewed dataset export each require explicit authorization and fulfilled readiness gates. Until then, conclusions, review decisions, results and feasibility remain unestablished.
