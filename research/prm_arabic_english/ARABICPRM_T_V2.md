# ArabicPRM-T v2 — source-selection gate

This milestone creates **English candidates for Arabic translation**, not an Arabic
training set. It rebuilds the exact pinned full-shard 1,000-problem audit, verifies
the source and selected-file checksums, excludes every active source quarantine,
and freezes a deterministic 500-trajectory candidate selection.

## Frozen initial selection budget

| Split | Correct | Incorrect | Total |
|---|---:|---:|---:|
| Train | 200 | 200 | 400 |
| Dev | 50 | 50 | 100 |

Within each split and class, the selector greedily covers underrepresented source
generation, step-length bucket, first-error-position bucket, and problem ID, with
SHA256(seed, record ID) tie-breaking. This is a **diversity heuristic**, not a
claim of domain-stratified representativeness. It does not fabricate domain labels.
The source's problem-level split remains immutable. All neutral masks, incorrect
reasoning, labels, IDs, and English step boundaries are preserved exactly.

The candidate budget is a starting point, not a commitment to pay for or translate
500 trajectories without further cost/quality review. No translation API is invoked
by CI. The source JSONL artifacts are retained temporarily as CI artifacts; only
checksums, selection policy, and non-sensitive summary should be committed.

## Run

From the repository root, with the pinned source-pool directory already created:

```bat
.venv\Scripts\python.exe research\prm_arabic_english\select_arabicprm_t_v2.py --source-dir research\prm_arabic_english\data\prm800k_full_shard_1000 --output-dir research\prm_arabic_english\data\arabicprm_t_v2_selection --seed 42 --train-per-class 200 --dev-per-class 50 --quarantine-catalog research\prm_arabic_english\source_quarantine.json
```

The GitHub Actions workflow `arabicprm-t-v2-selection.yml` also rebuilds the
pinned source pool from scratch and publishes a short-lived English candidate
artifact. Review its manifest before accepting a production translation budget.

## Remaining mandatory gates

1. Translation: choose and document translator/model version, settings, cost,
   prompt and provenance. Translate one-to-one into MSA, preserving errors,
   formulas, numbers, neutral steps and source step boundaries.
2. Materialization: run the existing protected-span, numeric-sequence, Arabic
   presence and exact queue-hash checks. Do not approve an edited queue with
   an earlier hash.
3. Human QC: review all translated trajectories or a pre-registered sampling
   protocol with clear acceptance policy. Reject or quarantine label conflicts
   rather than rewriting source supervision. Human identity/attestation must be
   genuine; AI assistance does not substitute for it.
4. Corpus freeze: export only human-accepted records with mask preservation;
   record exact train/dev SHA256 and source/translation/review lineage.
5. Training: implement and test a mask-aware loss; the older pilot trainer is
   incompatible with neutral labels. Run a small smoke test, then a controlled
   full run, with English retention and held-out Arabic evaluation. Do not
   train on pending translations.
6. Final evaluation: keep Global-MGSM untouched until the final pre-registered
   model comparison. Do not tune after opening it.

No v2 translation, human QC, corpus freeze, or model training is claimed by this
selection milestone.
