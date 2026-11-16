# ArMATH — unchanged original dataset and ArabicPRM-T audit

The complete **6,000-record upstream ArMATH dataset** is in [original/](original/):
five original JSON folds, **1,200 records each**, copied byte-for-byte from
`reem-codes/ArMATH` revision `260850e0510e95f709d0806b5fbdd9dc553e4458`.
The original statements, equations, tags, ordering, whitespace and known errors
are preserved. No cleaned subset, generated solution or human annotation is
substituted for the originals.

## Attribution and redistribution basis

ArMATH is the work of **Reem Alghamdi, Zhenwen Liang and Xiangliang Zhang**:
*ArMATH: a Dataset for Solving Arabic Math Word Problems*, LREC 2022, pp. 351–362.
See the [paper](https://aclanthology.org/2022.lrec-1.37/),
[upstream repository](https://github.com/reem-codes/ArMATH), and
[attribution, citation and permission record](ATTRIBUTION.md).

The repository owner reports direct written permission from ArMATH co-author
Reem Alghamdi to redistribute all 6,000 records in this public research repository
with citation, in reply to that specific request. The original email is retained
privately by the owner; it was not independently inspected by the publication
workflow. No email, address, headers, correspondence date or personal metadata
is published. This records the reported permission; **no standard licence is
invented and no broader rights are inferred**. The repository's software licence
does not relicense these upstream data. The historical audit's undeclared-licence
finding remains an accurate description of the pinned upstream repository.

## Files, identities and origin tags

- [Publication manifest](PUBLIC_DATASET_MANIFEST.json): upstream/local paths,
  byte sizes, Git blob identities, per-file counts and SHA256 hashes.
- [SHA256 checksums](SHA256SUMS.json).
- [Original acquisition/source manifest](../../research/armath_audit_v1/source_manifest.json), unchanged.
- Original fields: `question`, `segmented`, `equation`, `tag`.

| Source tag | Records | Interpretation |
|---|---:|---|
| `novel` | 3,533 | Source-declared original-Arabic candidates; per-item authorship/book lineage is not independently authenticated. |
| `translated` | 2,467 | Derived/translated records; excluded from the Arabic-native candidate pool. The paper describes its derived group as inspired. |
| Total | **6,000** | Complete original release, including both tags. |

Publishing the complete source does not make all 6,000 records Arabic-native.
The original random folds are preserved for reproduction, not endorsed as
leakage-resistant source-family splits. Template similarity is not proof of
common authorship or translation; genuine source-family identities remain unknown.

## Scientific verification and limitations

The [historical audit](../../research/ARMATH_AUDIT_V1.md) and
[measured results](../../research/armath_audit_v1/SUMMARY.json) remain unchanged:

| Measure | Actual result |
|---|---:|
| Source-declared `novel` equations safely parsed | 3,533 |
| Exact rational values numerically crosschecked | 3,512 |
| Irrational results requiring exact/rounding interpretation | 21 |
| Narrow independent question/equation agreements | 897 |
| Clear question/equation discrepancy | 1 |
| Native-tagged records requiring further review | 2,635 |
| Automatically screened, deduplicated development candidates | 882 |
| Independently validated Arabic PRM benchmark problems | **0** |

There is **no separate reference-answer column and no original reasoning traces
or Arabic process-step labels**. Equation evaluation does not establish question
correctness; the dataset is not claimed error-free. The 882 automatic candidates
span only 11 conservative components, not 882 verified independent source families.
Source-reported historical checking is not this project's independent Arabic
step annotation. The original mathematical problems are **not equivalent to
independently human-validated PRM reasoning-step labels**.

The future cleaned, provenance-reviewed and independently annotated ArabicPRM-T
benchmark is a separate deliverable. No human review, eligibility promotion,
model generation/scoring, training or budget activation is implied by publication.

## Reproduce and verify offline

From the research checkout, Python 3.11+ and the standard library suffice:

```sh
python -B research/prm_arabic_english/verify_armath_originals.py
```

This read-only check verifies every original file against the unchanged source
manifest, including byte length, SHA256, Git blob, schema, fold and origin counts.
`data/armath/original/*.json -text` preserves exact bytes on Windows checkouts.

For an independent upstream acquisition and the full historical audit, use two
new private directories outside every Git checkout:

```sh
python -B research/prm_arabic_english/armath_audit_v1.py acquire --destination PRIVATE_SOURCE
python -B research/prm_arabic_english/armath_audit_v1.py audit --source-dir PRIVATE_SOURCE --output-dir PRIVATE_AUDIT --overlap-repository . --expected-output-sha256 research/armath_audit_v1/expected_artifacts.json --quiet
```

Only the five authorized upstream folds are mirrored here. Keep calculated
reference ledgers, proposed test allocations, student work, permission email,
populated human-review sheets and private provenance outside public Git.
