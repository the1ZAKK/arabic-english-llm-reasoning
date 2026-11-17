# v4.2 operating handoff

Read [the scientific readiness decision](../ARMATH_READINESS_V4_2.md).
**No execution authorization exists. The current user action is read-only inspection.**
The executor is implemented and tested with synthetic clients; real model APIs,
weights, library compatibility and GPU forward fit remain unverified.

## Pinned identities

- Frozen v4.1 proposal (canonical SHA256):
  `da757e5b75c1c0ee9d7b1687ed26b8c50192cfc5cb56c89fe532e484316952cf`.
- New reference policy (canonical SHA256):
  `3999913efbd839a5ed9e5723154a652d44293fc4298f14d723c65d8d2b1cb86d`.
- Tested executor release manifest (canonical SHA256):
  `6d296ceda21e795f815db99aaf958509309c25fbe1ce555c917b4513ee7d2847`.
- Read-only Windows CMD file SHA256:
  `fc485cd5b323155d58b1737098e3a72e69debedcaa10e3555351f34eab3e6110`.

These source/reference identities are not model fingerprints or human approval.
Actual runtime/model/checkpoint hashes are collected only from local bytes. Artifact
bundle hashes cover canonical sorted relative-name/size/file-SHA256 manifests;
individual raw file hashes are also retained. The pretrained head identity covers
its two actual safetensors byte slices; the adapted head covers its actual file.
Do not invent or substitute hashes for missing files. The software identity hashes
observed Python/package/CUDA metadata and pinned project code; it is not a full
cryptographic attestation of every installed library binary.

## Current read-only laptop step

Download and double-click
[inspect_armath_runtime_windows_v4_2.cmd](../prm_arabic_english/inspect_armath_runtime_windows_v4_2.cmd).
It contains a hash-verified payload; no adjacent source file or download installer
is needed. A compatible existing Python3.11+ is selected. Large local model files
are read for hashing. No model is loaded or run, and nothing is copied into either
checkout. Only new temporary report files are written.

Review and share **share_status.json only** from the printed report directory.
Keep report_private.json private. It contains paths, full cache manifests and
metadata. Known checkpoint locations in the original sibling checkout are checked
read-only if absent from the clean checkout. Multiple locations require an explicit
choice; none is silently preferred. A custom cache/path can be inspected using
the Python script's --base / --adapter / --reward-head / --ollama-models-dir options.
Missing components are reported without installing or downloading them.

Do not run the later execution modes as part of this readiness directive.

## Later engineering/operator reference — separate authorization required

The following is documentation of the guarded modes, not permission to use them.
Use only a clean committed research checkout at the tested source identity. Leave
the original dirty checkout, verified backup and overlap worksheet untouched.
All new state, reports and mirrors must be outside every Git checkout.

1. Prepare a private unapproved draft, optionally binding a real inventory:

   ```text
   python -B research/prm_arabic_english/armath_executor_v4_2.py --repo-root CLEAN_REPO --state-dir NEW_PRIVATE_STATE --inventory PRIVATE_INVENTORY.json
   ```

   Without --inventory the draft is explicitly unbound and cannot be approved.
   Prepared specs are immutable: use a new empty state directory when binding an
   earlier unapproved draft; never overwrite an approved or spent state. One global
   guard for this proposal prevents a different state directory/checkout from
   creating another allowance. The original sibling checkout is included read-only
   in protected snapshots when present, or can be supplied by --original-repo.

2. Only after actual separate owner authorization, --approve displays the source,
   reference, runtime/release and fixed limits, then requires an actual identity
   and exact `AUTHORIZE ARMATH96 PRM240` input. It records the real local UTC/account
   and creates immutable consent/anchor copies; **it sends no model request**.
   Old pilot20/diagnostic24 approvals and unapproved templates are rejected. No
   --yes, reset, refund, budget-size or retry option exists. CI blocks this mode.

3. --generate requires the existing bound consent, freshly verified local files,
   code/history and model metadata, plus final `RUN ARMATH GENERATION` confirmation.
   Every frozen request/seed is used once, at most96 requests ×512 generated tokens.
   Reservations/dispatch witnesses are durable before POST. Raw HTTP response bytes,
   actual counts, exact payload hashes and parsed/protocol outcomes are preserved.
   No inference probe, extra warm-up, translation, repair or model pull occurs.

4. Once all96 generation reservations are spent, the report directory includes
   `mirrors_template_NOT_REVIEWED.json`. It copies only the actually recorded Arabic
   questions/steps/final strings into a private input worksheet. English fields and
   fidelity evidence are blank, not generated or human-approved. Preserve it and
   fill a separate copy with genuine faithful English mirrors and actual fidelity
   evidence hashes. Preserve mistakes, quantities, formula/digit strings, units and
   step boundaries. Do not insert equal sharing into the boat question. Mechanical
   checks cannot authenticate semantic fidelity or a human identity.

5. --score --mirrors PRIVATE_COMPLETED_MIRRORS.json displays/pins the mirror bundle,
   requires final `RUN ARMATH SCORING`, and waits for metadata to show no resident
   Ollama model (no unload generation is sent). At most240 cells ×1024 input tokens,
   one attempt per cell, matched base/adapter NF4 with one resident condition.
   Token/offset evidence is committed before forwarding. Missing/invalid candidates
   retain unavailable cells; they do not authorize replacements. Failures consume
   reservations, stop the phase and never trigger automatic retries/offload/dtype
   changes. Resuming requires another local confirmation and skips every consumed
   operation, including interrupted reservations without outcomes.

6. --report performs offline analysis only. It works before approval with all
   slots explicitly unattempted and null accuracy. After model operations it writes
   an immutable `reports/<report-hash>/report.json`, showing phase spend/remaining,
   missing/failed operations, all96 slots/all240 cells, original-five and new-eleven
   technical analyses, selection seals, baselines, paired shifts and human-QC status.
   Preserve each report and raw outcomes. Nothing is exported as training data.

The fixed local guard is under LOCALAPPDATA/ArabicPRM/armath-v4.2-guards/<proposal>
(or the analogous Linux user data directory). Keep it with the private state.
Deleting or moving state/guard/records is not a recovery mechanism. A changed
approval/runtime/source or missing historical witness stops the runner.

## Interpretation and remaining genuine evidence

There are11 AI/automatic technical keys, one conditional exclusion and zero new
independent human validations. An exact numerical/protocol proxy is not a qualified
human benchmark result. Two independent qualified Arabic mathematics reviewers,
real bilingual fidelity/semantic-step evidence and separate disagreement adjudication
remain necessary for the respective scientific claims. Human labels are never
inherited from the English PRM dataset or assigned by this executor.

Original native authorship, source-family independence, pretraining overlap and
larger held-out efficacy remain unproved. Confirm the actual adapter/base revision
lineage before attributing results to the historical adaptation; matching model-family
names alone does not establish that lineage. The current contrast always compares
the supplied adaptation bundle and reward head against the same chosen base.

First-versus-PRM accuracy is descriptive; compare same-K majority and random/oracle
outcomes and report scoring/generation costs. Scoring shifts cannot establish semantic
step discrimination without actual correct/incorrect/neutral maps, nor quantization
causality without a matched precision contrast. Never manufacture errors or extra
requests to fill missing observations or obtain a preferred result.
