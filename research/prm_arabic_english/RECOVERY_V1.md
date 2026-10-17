# ArabicPRM-T v2 recovery-v1

This is a separate recovery implementation for the exhausted Batch09–32 run. It does not change the original generator, terminal supervisor state, nine-attempt history, validators, source locks, translations or human-QC records. It never publishes to GitHub, exports training data, trains a model or reads other corpora. The existing monitoring automation remains unchanged.

## Evidence and scope

The historical audit reports 1,075 of 2,252 mechanically validated fields, leaving 1,177 fields and 2,005 unresolved prose slots. These are historical figures, not results of this recovery implementation. The Batch10 investigation found 814 English-only outputs among 824 script/boundary rejections, plus nine mixed-language outputs and one other-script output. Connection-refusal events remain separate from translation quality. See `BATCH10_REJECTION_ROOT_CAUSE.md`.

The original runtime is preserved. Recovery requests use `msa-single-fragment-v1`: one fragment per HTTP request, an explicit English-to-Arabic example, and one `arabic` JSON string rather than returning an English-keyed collection. Rejected English echoes and mixed-language values receive different retry instructions. Values are never trimmed, extracted, transliterated, partially accepted or repaired. The unchanged `validate_slot`, source-owned assembly and ordered checkpoint/math/number checks still decide acceptance. Actual semantic equivalence still requires human review. Offline tests cannot establish this prompt's success rate on Qwen3.

## Offline preparation

The Windows installer accepts only a pinned commit on the research branch. It reads the recovery allowlist from canonical Git blobs, verifies each blob identity, records SHA256 for every installed file, and installs a separate immutable runtime. It rejects changed, missing or additional runtime files. No checkout, reset, task installation, supervisor configuration change, Ollama start, metadata probe or inference occurs. PowerShell never decodes or rewrites JSONL. Existing CRLF draft-copy envelopes are verified using the original exact-envelope checks; canonical frozen sources retain exact-byte hashes.

Default installation then inventories the laptop's actual `translated_drafts/unattended_agent/state.json`, `latest_audit.json`, legacy checkpoints, validated-field checkpoints, prose slots and counters. Every audited unresolved slot must match the current source, batch, field, slot and historical attempts. The full 24-batch/2,252-field coverage and original exhausted terminal state are required. Existing protected files are hashed before and after preparation.

New files are confined to `recovery_artifacts/recovery-v1/`. A content-addressed `plan.json` binds the original file snapshot, source and slot hashes, generator/dependency hashes, model digest and prior accepted fields. A `budget_NOT_APPROVED.json` is created with `approved: false` and **zero new requests**. Running the preparation launcher never activates that template.

If the actual laptop state disagrees with its audit, preparation fails closed and preserves the files. It does not fall back to the historical GitHub aggregate or silently reset an exhausted run.

## Separate budget approval and execution

**No recovery budget has been approved by the user. Development and CI do not authorize model calls.** The approval fixture used in tests exists only in disposable synthetic repositories.

A future approval must identify the exact prepared plan, historical model digest, budget ID, approving person and time, maximum total HTTP generation requests, maximum new attempts per slot, and the fixed 512-token ceiling per request. Both caps must be explicit integers; at most three new attempts per slot are supported. One immutable approved budget is allowed per plan. Increasing its caps, changing its ID, copying the plan, restarting, reinstalling or changing output paths cannot renew it. A further grant requires a separately reviewed version.

The development entry point requires all three flags `--execute`, `--plan` and `--approval`. The Windows preparation installer deliberately exposes none of them. Before even constructing a model client, execution checks branch/origin, code and plan hashes, the entire protected snapshot, and the approval. Runtime metadata uses GET `/api/tags` and `/api/version`; there is no inference-based readiness probe or automatic model download. A mismatching installed model digest blocks generation.

Each generation request gets a durable reservation in a new hash-chained append-only `attempts.jsonl` **before** the request. Every reservation consumes the new budget, including process crashes and connection refusal. Original counters are never decremented or updated. Each outcome records its category, candidate, error and response hash. Truncation, thinking content, duplicate/extra JSON keys, script/math/boundary violations and altered journal chains fail validation. A transport outage stops dispatch immediately. Resume revalidates successful slots and never requests them again.

Recovered full fields are saved as new bilingual JSON inspection artifacts. Fully complete batches receive a separately validated draft payload and bilingual HTML/JSON review artifacts, with all human decisions pending and training eligibility false. Incomplete batches are never marked complete. The original draft, review and QC directories remain byte-for-byte unchanged.

## Verification and remaining local limits

The standard offline suite includes recovery protocol, language/script/math/boundary, consent/cap/crash/restart, journal, source snapshot and preservation regressions. A complete 2,252-field synthetic preparation fixture reproduces Batch09 `dev:0:4` unresolved `s1`/`s2` and legacy Windows CRLF copies. Packaging tests exercise paths beyond Windows MAX_PATH, canonical Git bytes, immutable-runtime tampering and the file allowlist. No synthetic Arabic response is committed to a corpus.

The CI matrix runs on Ubuntu and Windows with Python 3.11. Native Windows CI also parses the installer under PowerShell and packages the pinned runtime using Windows PowerShell 5.1, verifying all 2,252 canonical frozen fields without inference. Once these checks pass, a single preparation launcher can be pinned to that tested commit and installer SHA256; its download/hash rejection path is tested separately before delivery.

This environment cannot inspect the laptop's private checkpoint bytes, installed Ollama behavior, GPU or live prompt quality. Those remain unverified until local preparation and a separately approved inference budget. Automated checks never constitute human QC.
