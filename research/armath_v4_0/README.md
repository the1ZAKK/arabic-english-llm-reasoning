# Reproduce and use the v4.0 review packet

Read [the scientific report](../ARMATH_FEASIBILITY_V4_0.md) and
[measured summary](SUMMARY.json). The original source remains in
[`data/armath/original`](../../data/armath/original/) at its published hashes.
This workflow creates only a private development review packet; it has no model
execution, budget or benchmark-approval path.

## Reproduce

Python 3.11+ and the standard library suffice. Use new private output directories
outside **every** Git checkout; existing destinations are never replaced.

```text
python -B research/prm_arabic_english/verify_armath_originals.py
python -B research/prm_arabic_english/armath_audit_v1.py acquire --destination PRIVATE_SOURCE
python -B research/prm_arabic_english/armath_audit_v1.py audit --source-dir PRIVATE_SOURCE --output-dir PRIVATE_AUDIT --overlap-repository . --expected-output-sha256 research/armath_audit_v1/expected_artifacts.json --quiet
python -B research/prm_arabic_english/armath_feasibility_v4.py --audit-dir PRIVATE_AUDIT --output-dir PRIVATE_REVIEW --expected-output-sha256 research/armath_v4_0/expected_artifacts.json --quiet
```

Only acquisition contacts the pinned original dataset, never a model. Packet
preparation is offline and reads the already published originals. It verifies all
nine historical audit hashes and every selected source identity. The old selection
seed/order is retained: 32 existing cases + 68 extension cases, all development-only.
Sixteen output hashes are fixed in `expected_artifacts.json`; Windows/Linux CI
reproduces them without uploading the private question/reference packet.
The historical audit module, output hashes, proposed partitions and source bytes
are unchanged. `armath_quality_v4.py` adds separate narrow relation checks and link
ablation, not corrections or human judgments.

## Review without commands

Extract the delivered ZIP and double-click **START_HERE.html**. This is an offline
HTML/CSV packet; source citations need internet only when opened. No installation
or launcher execution is needed.

- `questions.html`: all 100 original questions, in fixed review order, with source
  citations. Derive and record the answer before reading references.
- `developer.csv`: actual student/developer review only.
- `reviewer_a.csv`, `reviewer_b.csv`: distinct qualified independent human records.
- `adjudicator.csv`: separate qualified resolution, preserving both original row
  hashes and uncertainty. Disagreement never becomes automatic approval.
- `coordinator_references.html`, `review_records.jsonl`: unchanged equations,
  computed values, original audit status, separate new relation checks and flags.
- `selection_private.json`: 32/68 membership, topic signals, template identities
  and review order; `grouping_sensitivity.json` keeps the old split unchanged.
- `SEMANTIC_REVIEW.md`: short criteria; `timing.csv` and `reviewers.csv`: reused
  private metadata templates with no people or events filled in.

The source link can expose an equation, and reference files remain accessible.
First-pass independence therefore depends on actual reviewer conduct; no enforced
blinding or sealed assessment is claimed. Save initial files separately and return
them without changing someone else's decisions. Actual human identities/evidence
remain private. This package is source-problem review, not original-Arabic reasoning
trace collection or PRM step annotation. The old fixed-20-slot v3.2 validator must
not be presented as validation of these 100 problem-quality worksheets.

All 100 are deliberately development-exposed. Do not copy computed reference
ledgers into tuning/model inputs or create a locked-test split from these items.
Keep populated sheets, AI notes, private lineage and full per-record review outputs
out of public Git. Publish only intentionally sanitized aggregate findings.
