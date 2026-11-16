# ArMATH offline source audit v1

Start with the [scientific findings](../ARMATH_AUDIT_V1.md). This is a problem-source
audit, not a PRM-label dataset, model runner, release approval or locked evaluation.
Only standard-library Python 3.11+ is required. Source solver code is never imported.

## Reproduce

Use the research checkout at the tested commit. Choose two **new private folders
outside every Git checkout**; the tool refuses existing destinations and protects
source/derived-reference files from accidental Git publication.

```text
python -B research/prm_arabic_english/armath_audit_v1.py acquire --destination PRIVATE_SOURCE
python -B research/prm_arabic_english/armath_audit_v1.py audit --source-dir PRIVATE_SOURCE --output-dir PRIVATE_AUDIT --overlap-repository . --expected-output-sha256 research/armath_audit_v1/expected_artifacts.json --quiet
```

Acquisition makes explicit HTTPS GETs to the pinned upstream Arabic folds and
README, checking exact bytes/SHA256. It does not download Chinese data, models or
solver dependencies. `audit` is offline and never follows source permalinks or
executes source equations as Python. Cancellation/failure preserves existing files;
no automatic retry, overwrite, generation, training, budget or export action exists.

`source_manifest.json` binds original file/Git identities, actual origin tags,
missing answer/step fields, licence findings and development-inspection scope.
`SUMMARY.json` is the measured aggregate, not raw questions or hidden reference
answers. `expected_artifacts.json` contains hashes of the private outputs, enabling
full-data Windows/Linux checks without publishing them. All original JSON stays
unchanged. No candidate is silently repaired.

## Calculation and grouping scope

- Whitelisted AST nodes only: finite decimal/integer literals, signs, +, -, *, /,
  bounded integer powers and square roots. `^` is power, never XOR. Fraction uses
  literal text, preserving decimal exactness. No `eval`, untrusted imports/calls,
  variables on the RHS, implicit multiplication or ambiguous mixed-fraction syntax.
- Fraction arithmetic is crosschecked with 80-digit Decimal calculation. The
  methods share a validated parse tree. Irrational values have 60/80-digit
  approximations but stay pending exact/rounding interpretation. Domain errors,
  parser/operation limits and semantic uncertainty are distinct categories.
- A separate **complete-question** grammar handles explicit arithmetic, percentages
  and reciprocal wording. It does not extract a convenient expression from an
  arbitrary word problem. Unparsed wording stays pending; agreeing numeric values
  do not excuse conflicting operation structures. No independent source answers
  are invented from equations.
- Raw/NFKC, Arabic/punctuation folding, segmented text, numeric variants,
  commutative/signed-sum templates, broad operator skeletons and blocked near-text
  links remain separate. First-occurrence numeric binding is ambiguous for repeated
  quantities. Near-text detection is incomplete; skeletons can overmerge. No source
  author/book identities or full algebraic-equivalence result is fabricated.
- Grouping includes derived records to expose cross-origin relationships, without
  declaring native records translated merely because arithmetic templates match.
  Only `novel` can enter candidate selection. All ledgers retain rejected/pending
  rows; strict selection picks one automatic record per folded-question identity.
- QA-reserved and previously inspected components are development-only. Other
  proposal assignments use a fixed hash rule. No split is locked or promoted.

## Status meanings and human review

| Status | Meaning here |
|---|---|
| `verified_automatic` | Applicable narrow question/equation numerical checks passed with no detected flag. No independent semantic, authorship or rights approval. |
| `needs_review` | Unparsed/ambiguous wording, rounding/domain/unit questions, computational limits or other uncertainty. |
| `rejected` | Derived/unknown source origin excluded, or a documented technical criterion fails. Original record is retained. |
| `developer_reviewed` | Requires an actual subsequent student assessment; none exists in this audit. |
| `independently_reviewed` | Requires genuine qualified independent evidence; none exists in this audit. |

The private `review_sources.html` links 32 exact original record ranges on the
pinned official repository. No source text or calculated answer is embedded.
`reviewer_a.csv`, `reviewer_b.csv` and `adjudicator.csv` contain source identities
and **blank judgment/person fields**. Follow the seven criteria in
[SEMANTIC_REVIEW.md](SEMANTIC_REVIEW.md). Existing ACCEPT/REVISE/REJECT conventions
are reused; these problem-quality worksheets do not masquerade as completed v3.2
fixed-cohort judgments or PRM step annotations. Authentic human evidence would need
its own validation before final benchmark metadata can pass `native_study_v1`.

Private `per_record_audit.jsonl` includes computed values and all missingness.
Keep it and the unlocked split proposal out of tuning/model-input folders and
public Git. Source/semantic concerns and correction proposals remain separate.
Do not infer translation accuracy, human approval, training eligibility or solving
improvement from arithmetic passes, missing flags, hashes or CI.
