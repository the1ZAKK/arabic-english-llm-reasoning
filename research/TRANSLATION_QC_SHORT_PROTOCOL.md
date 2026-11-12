# Supporting translation QC: short protocol

Translation QC supports the corpus work; it is not the native-benchmark or
downstream-solving endpoint. Keep existing human records, frozen sources,
translations, labels, masks, checkpoints and histories unchanged.

1. Apply the existing deterministic structural checks to every candidate: hashes,
   numbers, formulas, notation, step boundaries, labels/masks and missing text.
2. Before review, freeze the original-translation frame and draw a reproducible
   stratified **problem-group** sample across split, source batch and mechanical
   pass/fail status. A qualified bilingual mathematics human reviews full context.
   For a short first audit, propose 32 of the 64 early-draft groups using the
   already implemented [sampling plan](CORPUS_QC_SAMPLING_PLAN_V2_4.md). This is
   a proposed capacity choice; **no sample has been drawn or human review done**.
   The 192 later groups and earlier approved corpus are separate frames.
3. Record ACCEPT / REVISE / REJECT / unresolved for translation fidelity and these
   five standard categories: **MATH** (operation, entity, logic, interval), **NUM**
   (number/unit), **LANG** (terminology, agreement, meaning), **BOUNDARY** (missing,
   added or moved reasoning), **SOURCE** (original reasoning/annotation concern).
   Multiple tags are allowed. SOURCE is separate from a translation error; a
   faithful rendering of a wrong English argument must remain wrong in Arabic.
4. Retain original outputs and decisions. A second qualified person checks proposed
   corrections and disagreements. Report unresolved reviews and inclusion weights;
   never replace an observed error with its correction in the original error rate.
   Weighted estimates apply only to the sampled frame, with family/stratum-aware
   uncertainty and unresolved-review bounds. High-risk targeted cases are separate
   qualitative findings, not a prevalence estimate.

One current evidence table is enough; add measured human sample findings only
when authentic assessments exist:

| Scope / denominator | Mechanical evidence retained | Semantic / human evidence and limit |
|---|---|---|
| Historical approved v1, 32 trajectories / 298 steps | Prior approved corpus remains unchanged | Historical approval is preserved; it does not approve the expansion or prove native origin |
| Early expansion, 64 trajectories / 757 fields | 45 whole trajectories pass; 35 field failures in 19 trajectories | Sampled qualified-human audit pending; no semantic error prevalence estimate |
| Later expansion, 192 trajectories / 2,252 fields | 1,089 fields mechanically complete, 1,163 incomplete; 1,985 missing prose slots | Separate incomplete frame, not automatically eligible for training |
| Closed pilot20, 20 fragments | Recorded 20 consumed requests / 20 mechanically accepted fragments | Provisional AI review found semantic concerns; not independent human QC |
| Proposed diagnostic24, 12 selected pairs | Software prepared; 24 outputs not attempted, no active budget | Deferred supporting experiment; cannot establish benchmark-wide quality |
| Proposed early-draft human sample, 32/64 groups | No draw or new corrections applied | All human fidelity decisions and resulting estimates still missing |

Do not combine these denominators, extrapolate purposive pilot findings, or add
reviewer infrastructure unless a concrete scientific need appears. Existing
artifacts remain available for reproducibility. Native Arabic human **mathematical
step labeling** follows its own [benchmark rubric](ARABIC_NATIVE_BENCHMARK_V1.md)
and cannot be replaced by this fidelity protocol.
