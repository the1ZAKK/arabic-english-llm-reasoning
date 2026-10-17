# Interpreting the 35 strict revalidation failures

This read-only investigation qualifies the aggregate audit; it does not repair drafts, relax a validator, change a frozen plan or provide human QC. All original source locks, translations and mathematical literals remain unchanged. The 45/64 whole-record result means **passing the current strict software policy**, not a semantic accuracy estimate.

Three failing Batch01 fields were inspected against their frozen English and materialized committed draft. Two distinct policy effects were observed:

| Field | Observed evidence | Interpretation / next gate |
|---|---|---|
| Batch01 `train:0:0` | The source phrase “represents a two-digit number” produces a protected `fingerprint` literal `a two-`, alongside the actual LaTeX expressions | This literal is ordinary English compound-word prose misclassified by the current math-span parser. Its exact-literal mismatch is not itself a changed mathematical equation. Full translation meaning remains unreviewed |
| Batch01 `train:4:4` | The entire `align*` environment is source-owned. Its English `\tag{...}` annotations have translated prose in the draft | The strict whole-environment literal differs. This observation does not prove a changed algebraic operation. Current policy still rejects it; bilingual and mathematical review must assess any future separately versioned representation |
| Batch01 `train:4:8` | The frozen `align*` environment contains English coefficient/constant annotations in `\tag{...}`; the corresponding draft annotation prose differs | Same whole-environment policy issue. Preserve both original artifacts; do not call this completed human review |

The diagnostic compared `source_preserving_translation.fingerprint(english)` and the committed draft's literal list after the existing `resume_v2_local.materialize(..., preserve_source_errors=True)` restoration. Only three cases were examined in detail. No category totals or corpus-wide frequency are inferred from them. The other strict failures remain unresolved; some may be actual literal changes and others may be policy or segmentation cases.

The source-only investigation is reproducible from the existing Batch01 `source_lock.json`, `translations.json`, frozen selection and unchanged modules. No model call or training-data export is needed. Raw target strings are intentionally not republished in this note; inspect the existing authoritative files and local bilingual review artifacts.

The original recovery-v1 plan binds the existing segmentation and 13 runner hashes. Editing that parser would invalidate the prepared plan and original checkpoints, so this work does not do so. The recovery-v2 prototype uses the existing strict assembler/validators and marks the limitation; it cannot silently reinterpret an original accepted span. A future segmentation study would require a separate versioned specification, source-span provenance, annotation-aware tests, human review of proposed boundaries and an explicit migration design that preserves every original record. Any subsequent generation would still need its own approved budget. No such migration, approval or inference is implemented here.

For scientific reporting, keep four issues separate: script compliance of generated fragments, literal compliance under a named parser version, translation semantic fidelity, and source reasoning correctness. Neither a strict rejection nor a strict acceptance supplies a human semantic verdict.
