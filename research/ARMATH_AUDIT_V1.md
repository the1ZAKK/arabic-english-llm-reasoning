# ArMATH v1 — source and mathematical screening decision

**Publication addendum, 16 November 2026:** Five unchanged upstream folds are now
[mirrored with attribution](../data/armath/README.md) following the owner's report
of direct author permission for this repository with citation. The historical
audit measurements, source identities, human-review and eligibility counts below
remain unchanged. Earlier metadata-only/rights-pending statements describe the
audit snapshot; the reported publication permission does not complete PRM labels,
item provenance, family separation or semantic review.

**16 November 2026, Asia/Shanghai.** Acquisition milestone:
[`4ff4e13`](https://github.com/the1ZAKK/arabic-english-llm-reasoning/commit/4ff4e13f3837c059b74e61c48fd089ff3550098f).
Source revision: `260850e0510e95f709d0806b5fbdd9dc553e4458`.
See [inventory/rights evidence](ARMATH_ACQUISITION_V1.md),
[checksums](armath_audit_v1/source_manifest.json), [measured summary](armath_audit_v1/SUMMARY.json)
and [reproduction instructions](armath_audit_v1/README.md).

## Measured results

| Question | Actual finding |
|---|---|
| Original-Arabic population downloaded? | **3,533 source-tagged `novel` / 6,000 (58.88%)**. Exclude all **2,467 `translated`** records; the paper describes this group as inspired. `novel` is a documented source declaration, not independent item-authorship authentication. |
| Expressions and recomputable values? | All 3,533 native-tagged equations parse safely. **3,512 / 3,533 (99.41%)** have exact rational values crosschecked with 80-digit Decimal arithmetic. **21 (0.59%)** contain irrational results: 60/80-digit approximations agree, but exact/rounding interpretation remains pending. These are not 3,533 verified question answers. |
| Numerical failures? | No separate answer field exists: **zero comparisons against independent supplied answers**, failure rate **undefined**, not 0%. The separate complete-question grammar covers **898 / 3,533 (25.42%)**: **897 agree, one disagrees**. One omitted-addend source equation is excluded from automatic selection. |
| Possible semantic problems? | **437 / 3,533 (12.37%)** trigger at least one risk flag. This is heuristic triage, not semantic error prevalence. **2,635 / 3,533 (74.58%)** remain `needs_review`, including unparsed wording. No-flag word problems are not thereby correct. |
| Duplicates? | Zero exact raw/NFKC question duplicates. Arabic/punctuation folding links **170 native records in 83 groups**, **87 excess**; source `segmented` text has **93 members / 46 groups / 47 excess**. Numerical masking links **1,823 members / 370 groups / 1,453 excess**. Near-text screening finds **168 links involving 278 representative records**, after 19,887 candidate comparisons; it is incomplete and does not prove duplicate absence. |
| Families? | **213 native canonical equation templates**; conservative text/template/operation links produce **52 native-containing components**. The largest contains **2,757 / 3,533 (78.04%)** native records. **117 native canonical-template groups cross the original random folds**. These are algorithmic components, not independently established author/book families. |
| Automatic/developer/independent review? | Native status: **897 `verified_automatic` (25.39%)**, **2,635 `needs_review`**, **one `rejected` (0.028%)**. Remove 15 normalization duplicates from automatic selection: **882 / 3,533 (24.96%)** strict automatic candidates, only **11 components**. **Zero** developer assessments, independent human reviews or Arabic step labels are created. |
| Eligible development release / locked benchmark? | **Zero / zero** under this workflow's rights/human/contamination requirements. The 882 are source-declared, automatically screened development candidates, not cleared data or a PRM benchmark. No problem text or locked-test member list is published. |

The paper's reported 883 templates and our 955 all-record canonical templates
use different definitions; this is not a reproduction of the authors' template
counter. We canonicalize commutativity and signed addition/subtraction, and link
broader operator skeletons and near text conservatively. Full algebraic equivalence
and genuine source lineage are not solved. Shared arithmetic with translated
records does not prove a `novel` record was translated.

## Source fidelity and semantic review

Original JSON bytes are unchanged. Each ledger row retains its source-file SHA256,
revision, JSON pointer, exact original line permalink, canonical record and text
hashes, equation check, missingness, uncertainty and selection reason. Original
records are neither corrected nor dropped. The clear numerical discrepancy and
possible integer-purchase/rounding issues have separate **AI technical proposals**;
they are not human labels or applied corrections. Valid negative arithmetic,
reordered signed sums and fractional ticket prices are regression controls against
false accusations. Ambiguous natural-language operation scope remains uncertain.

The private packet supplies **32 purposively selected development review records**,
source permalinks, separate blank A/B/adjudication worksheets and a compact rubric.
It does not redistribute the dataset. Reviewers record actual identities/types,
qualifications, independence, judgments, concerns and dates; student self-assessment
is developer review. Preserve primary judgments before exposing AI notes or the
other assessor's decisions. Problem-quality review is separate from future Arabic
reasoning-step annotation. No independent reviewer has been appointed or simulated.

No explicit dataset redistribution grant was located. Keep raw problem text out
of GitHub pending licence/source-book clarification. Source-reported prior teacher
checking does not supply this project's independent Arabic step labels.

## Split and feasibility decision

All inspected/QA-reserved records and connected components are development-only.
The **unlocked** conservative proposal yields **3,470 development / 63 future-test
candidates** across the native pool; only **four** of the strict automatic
candidates fall in the latter partition. No known component crosses partitions.
This is not a balanced or ready benchmark; do not silently change the grouping or
seed to manufacture 500 test items. Coarse links can overmerge, and unknown source
lineage or undetected semantic duplicates can still leak.

| Proposed size | Decision from existing evidence |
|---|---|
| 100 | Reasonable **human collection/annotation feasibility target**, not 100 currently eligible items. Review across templates and word-problem types; measure real effort and obtain actual use evidence. Current conservative test proposal is smaller. |
| 250 | Raw pool is large enough, but topic/family coverage, qualified human workload, rights and meaningful held-out separation are unverified. |
| 500 | Headcount alone is insufficient. The automatic subset is predominantly bare arithmetic with 11 linked components; no probability/combinatorics coverage was identified by the limited keyword screen. Supplementary native sources and expert family/topic review are needed before committing to this scope. |

The current exact/NFKC overlap check covers **59 distinct accessible Arabic
problem hashes** from retained development examples, archived translations and
the manual-source manifest: zero matches. It does not exhaust all project data or
exclude translated, paraphrased, template or pretraining overlap. No restricted
benchmark was accessed.

## Required before model conclusions

1. Clarify source licence/intended use and item lineage; obtain genuine qualified
   Arabic problem/reference review and separately authored/generated Arabic traces.
2. Assign actual Arabic step/final labels independently (A/B, separate adjudication
   as needed); never inherit English PRM800K labels or equation evaluations.
3. Refine and freeze a defensible, leakage-audited source-family split. Keep any
   future locked reference answers outside tuning/model-input processes.
4. For gap diagnosis, bind matched PRM weights/tokenizer/quantization and semantic
   step/reward alignment, preserving blank-line controls. The existing
   [320-cell instrument scope](SCORING_DEVELOPMENT_SCOPE_V3_6.md) remains unchanged.
5. For [downstream solving](RERANKING_OPERATIONS_V3_1.md), separately authorize fixed
   Arabic-original candidate generation/scoring on held-out native problems;
   compare selection methods on the **same candidates** using independent final
   correctness, problem/family uncertainty and retained failures. No solving gain
   can be inferred from this audit or reward margins.

Two full-data runs produced identical artifact fingerprints. Windows/Linux CI
also reacquires only pinned Arabic JSON, recomputes every audit offline and checks
all output fingerprints; source files/results are not uploaded as CI artifacts.
CI establishes reproducibility and software guards, not native authorship or
semantic accuracy. No inference, model download, scoring, training, allowance,
scheduled task, original-data/human-QC change, Global-MGSM or `main` change occurs.
