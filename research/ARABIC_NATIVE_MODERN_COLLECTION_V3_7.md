# v3.7 — three modern source-backed problem captures

**13 November 2026, Asia/Shanghai.** Continued from `1f2603a` and its
[630-test Windows/Linux CI](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/43441942994).
This is actual source collection and technical checking, not native-origin or
human-label approval. The v3.6 student submission and private packet are unchanged.

| Private capture | Exact original source location, PDF pages 1-based | Technical finding | Remaining decision |
|---|---|---|---|
| Probability/combinatorics, `AN32-PRO-01` | [Tlemcen probability course](https://fseg.univ-tlemcen.dz/assets/uploads/fseg/formations/postegraduations/Rerecherche/L1-stat2%20Probabilit%C3%A9s.pdf#page=13), PDF p.13/107, printed p.9, chapter 2 example 2; correction PDF p.14 / printed p.10 | Complete short question visually transcribed; exhaustive combinatorial enumeration agrees with the printed correction. | Item-original language, use basis, family/overlap and qualified independent reference review. |
| Algebra, `AN32-ALG-01` | [Constantine Mathematics 2](https://fac.umc.edu.dz/fstech/cours/G%20Transport/math.pdf#page=15), PDF p.15/102, printed p.10, inverse section example 2 | Complete short question visually transcribed; exact left/right inverse checks support the final source answer. **An intermediate coefficient-assignment line is inconsistent.** Preserve it as a source concern, not a translation error. | Same provenance/use/human checks; retain the source discrepancy without silently repairing source reasoning. |
| Geometry, `AN32-GEO-03` | [Same course](https://fac.umc.edu.dz/fstech/cours/G%20Transport/math.pdf#page=95), PDF p.95/102, printed p.86, area section example 4 | Mathematical setting and both questions captured with declared layout normalization and omitted redundant introductory prose. Real square-root domain, boundary inclusion and polar-coordinate area agree with the source answer. | Source notation/difficulty review in addition to provenance/use/overlap. Polar integration is university material; provisional intermediate placement is not calibrated human difficulty. |

Source PDFs were downloaded from the official university hosts, hashed and rendered
locally. The [sanitized evidence](native_pilot_v3_2/modern_capture_status_v3_7.json)
records actual document/capture identities, precise locators and limitations.
Private reference answers and a small standard-library checking script accompany
the separately delivered source-evidence packet. Source PDFs/page images are not
redistributed. Raw question/reference text remains private and is not committed.
The packet contains short text captures only; it is not an approved benchmark/training export.

## What provenance is established

Tlemcen's 2021 cover credits **د. جمعة زكرياء**; Constantine's 2016–2017 cover
credits **ركاب صورية، بوشقوف مسعودة، وعرعار نورية**. Arabic course text and local
pedagogical introductions are visible. These facts do **not** establish that each
exercise was first composed in Arabic. Tlemcen's printed p.99 references include
translated Schaum routes. Constantine's printed pp.88–91 include Arabic, French
and English sources. Mixed references neither prove individual translation nor
clear original authorship; exact exercise derivation remains pending.

No applicable reuse grant was located in the inspected title/preface/reference
material; no rightsholder was contacted. All three intended-use permissions remain
**pending**, not granted or denied. Previously documented English-primary and
explicit-translation exclusions remain excluded. No new rejected item is invented.
The two Constantine items share a conservative source-course family and stay in
development; they are not independent source groups or future held-out examples.

## Actual counts and next scientific dependency

**Three new captures across three domains; four total including the preserved
historical algebra capture. Three new technically checked references; zero new
verified Arabic-original items, permissions, independent judgments, Arabic traces
or human step labels; zero benchmark-eligible problems.** The reused public
manifest has four answer-redacted candidate rows, so its metadata-complete count
is zero. The new private worksheet has three metadata-complete modern records;
the earlier private problem/answer and student trace remain in their original
packet rather than being migrated. Intake-ready count is zero in both views.

The existing screening log appends three pending records while preserving its
old bytes. Prior twelve source entries are unchanged; only the new Constantine
course lead is appended. Human CSV templates remain empty. Source-backed capture
yield must not be reported as verified native-origin yield or semantic accuracy.

For the controlled language-gap diagnosis, the existing
[160-item/320-cell scope](SCORING_DEVELOPMENT_SCOPE_V3_6.md) still needs actual
PRM/tokenizer/head/adapter, device/dtype and token/step alignment identities,
matched quantization, verified family grouping and separate scoring authorization.
Blank-line aggregates can be compared on the same eventual recorded vector.
This scope and all scores remain unchanged/unattempted; these source-worked,
assistant-exposed examples do not supply new model observations.

For [downstream reranking](RERANKING_OPERATIONS_V3_1.md), obtain a larger
permission/provenance-cleared native source frame, independent Arabic step/final
labels, leakage-resistant held-out source families, separately authorized fixed
candidate pools and scores, and blind final-answer judgments. Compare matched
candidates using final-answer accuracy and problem/family uncertainty, not reward
margins. These three development captures establish none of those outcomes.
First resolve item-origin/use and actual human feasibility before claiming a
realistic 100/250/500 collection or any solving improvement.

No inference, scoring, model download, training, active budget, scheduled execution,
unreviewed dataset release, frozen artifact or `main` change occurred. CI checks
software and evidence-accounting behavior; it is not qualified human mathematics QC.
