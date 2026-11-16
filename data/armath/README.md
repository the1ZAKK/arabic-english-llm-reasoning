# ArabicPRM-T — Public ArMATH dataset metadata

**Release type:** Research metadata and reproducibility guide, **not** a redistributed ArMATH dataset or an independently validated PRM benchmark.

This directory is the discoverable public dataset entry point for the supervisor and other readers. The original ArMATH Arabic question text is **not copied** here because its redistribution permissions were not established in the audited revision. A public source repository is not by itself a redistribution licence.

## Where the dataset actually lives

- Original research dataset: https://github.com/reem-codes/ArMATH
- Pinned upstream revision: `260850e0510e95f709d0806b5fbdd9dc553e4458`
- Research paper: https://aclanthology.org/2022.lrec-1.37/
- [Public metadata manifest](PUBLIC_DATASET_MANIFEST.json)
- [Source file SHA256, Git identities, and origin evidence](../../research/armath_audit_v1/source_manifest.json)
- [Scientific audit with limitations](../../research/ARMATH_AUDIT_V1.md)
- [Aggregate numerical results](../../research/armath_audit_v1/SUMMARY.json)
- [Reproduction instructions](../../research/armath_audit_v1/README.md)

## Measured audit scope (2026-11-16)

| Measure | Count |
|---|---:|
| ArMATH source records | 6,000 |
| Source-tagged `novel` (Arabic-origin *candidates*) | 3,533 |
| Source-tagged `translated` (excluded from native pool) | 2,467 |
| Independent narrow question/equation checks agreeing | 897 |
| Clear mismatch | 1 |
| Native-tagged records requiring further semantic review | 2,635 |
| Deduplicated strictly automatic development candidates | 882 |
| Independently human-reviewed / step-annotated problems | 0 |
| Released or locked-benchmark eligible problems | **0** |

The 882 candidates are **not** error-free, licensed for redistribution, or eligible benchmark problems. The upstream records have equations but no independent answer column or Arabic process-step labels. Original fold splits are not family-separated. See the audit report for grouping and leakage limitations.

## Reproduce locally without copying the source into this repository

From a checkout containing the project audit tooling, create **new private directories outside every Git checkout**, then run with Python 3.11+:

```sh
python -B research/prm_arabic_english/armath_audit_v1.py acquire --destination PRIVATE_SOURCE
python -B research/prm_arabic_english/armath_audit_v1.py audit --source-dir PRIVATE_SOURCE --output-dir PRIVATE_AUDIT --overlap-repository . --expected-output-sha256 research/armath_audit_v1/expected_artifacts.json --quiet
```

The acquisition checks the pinned upstream bytes against recorded SHA256 hashes. Keep acquired source files and private per-record results outside the public repository. Do not commit the acquired dataset, answer computations, populated review worksheets, source-book extracts, or proposed locked test allocations.

## What still needs to happen

Resolve intended-use and redistribution permissions; document item-level provenance and semantic/math checks; refine meaningful source-family splits; collect originally Arabic reasoning traces and genuine qualified Arabic step/final-outcome annotations; separately authorize any model scoring/generation. None of those approvals, reviews, or model outcomes are implied by this metadata-only publication.

This entry point preserves the historical audit and does not modify frozen experiment inputs, counters, or the `main` branch.
