# ArabicPRM-T v2 completion gates

## Verified state

- Frozen selection: 256 trajectories, 204 train / 52 dev, 2,753 steps.
- Batch01–Batch05: 40 AI-drafted Arabic trajectories / 464 steps, automated preservation QC passed.
- Batch06–Batch32: 216 frozen English trajectories; AI translation **not yet performed**.
- The 29 remaining source queues are reproducibly staged by `stage_v2_remaining_batches.py`.
- No human review attestation has been supplied for Batch01–05.
- No full v2 export or QLoRA training has occurred.

## Bulk AI drafting (never human approval)

Use the opt-in GitHub Actions workflow `.github/workflows/v2-bulk-draft.yml`
on the `research/arabicprm-v2-production` branch. The `syntax-check` job
requires no secrets. The manual `draft-and-validate` job needs a repository
Actions secret `OPENAI_API_KEY`. Optionally set repository variable
`ARABICPRM_TRANSLATION_MODEL` (default `gpt-4.1`); inference can incur cost.
Start with Batch06 only; then move through successive batches to Batch32.
The model endpoint is configurable locally through `OPENAI_BASE_URL`.

The generator refuses silent overwrites, checks each source queue against its
hash-bound lock, and verifies per-string math placeholders and numeric sequences.
The workflow materializes drafts, renders bilingual review pages, and creates
pending human-QC decision templates. It does **not** set any review decision
or call the training exporter. Artifacts must be downloaded and reviewed;
workflow output alone does not add immutable final files to the repository.

## Mandatory completion sequence

1. Complete and independently validate AI drafts for Batch06–32.
2. Have a genuine human review the bilingual pages for **all 32 batches**,
   recording accept/reject/revise decisions tied to the exact review queue SHA.
3. Re-draft revised/rejected items as appropriate; re-render and re-review.
4. Run `export_reviewed_arabic.py` only with genuine named reviewer attestation,
   complete decisions, and exactly matching review queue SHA.
5. Merge only reviewed, non-quarantined accepted records into v2 train/dev,
   prove group-level train/dev separation and lineage, and audit proportions.
6. Run a bounded QLoRA smoke check on the approved corpus, then full training
   and isolated evaluation with frozen baselines and untouched Global-MGSM.

A request to complete the project is **not** a human record-by-record QC decision.
Do not set `human_review: true`, fabricate reviewer metadata, bypass guards,
or claim translation/training completion before the corresponding evidence exists.
