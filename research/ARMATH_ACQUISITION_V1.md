# ArMATH — pinned acquisition inventory

**Publication addendum, 16 November 2026:** The owner subsequently reported direct
written author permission for complete redistribution in this research repository
with citation. See [current dataset attribution](../data/armath/ATTRIBUTION.md)
and the [byte-exact original mirror](../data/armath/original/). The email remains
private/uninspected here; no standard licence is assigned. The inventory and
upstream no-licence observation below are historical, unchanged findings.

**16 November 2026, Asia/Shanghai.** Research branch continuation from `b002beb`.
Official source: [reem-codes/ArMATH](https://github.com/reem-codes/ArMATH), revision
`260850e0510e95f709d0806b5fbdd9dc553e4458`.
[Paper](https://aclanthology.org/2022.lrec-1.37/): Alghamdi, Liang and Zhang, LREC 2022.

All five actual Arabic JSON folds were acquired and checked against their Git
blob identities and recorded SHA256 checksums in the
[source manifest](armath_audit_v1/source_manifest.json). Each fold contains 1,200
records: **6,000 total, 3,533 `novel` and 2,467 `translated`**. The novel counts
per fold are 698, 697, 695, 733 and 710. These match the paper's reported
creative/inspired population; the actual derived tag is `translated`, not `inspired`.
All derived records are excluded from the native candidate pool.

Records have exactly four string fields: `question`, `segmented`, `equation`,
`tag`. There is **no separate answer, item author/book lineage, topic/difficulty,
reasoning trace or step-label column**. An evaluated equation is a derived
reference, not an independent supplied answer or a verified reading of the question.
The five random folds are not a family-separated locked benchmark.

The paper describes native Arabic creative writers, some source-book material,
adapted Chinese-derived questions and prior question/equation checking. Treat
`novel` as documented source-declared origin, not independently authenticated
item provenance or new qualified Arabic step annotations for this project.

No licence file exists in the inspected 22-entry revision tree; GitHub reports
`license: null`. The README/paper's availability statements do not supply an
observed dataset redistribution grant. **No problem text or source JSON is
published here.** Licensing and underlying source-book rights remain unresolved;
only metadata, checksums and original analysis code/aggregate facts may be published
in this continuation. No rightsholder was contacted or permission invented.

This acquisition inventory establishes source population and identity. Subsequent
offline numerical, wording, duplicate, family and eligibility findings require
their own versioned audit; this document makes no correctness/efficacy claim.
The original student packet, frozen research artifacts, counters, human QC and
exhausted/inactive budgets are preserved. No model, training or scoring code was
run; source solver files were inspected as text only, with no model download.
