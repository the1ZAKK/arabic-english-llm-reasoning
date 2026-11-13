# v3.4 — first private source-backed problem capture

**2026-11-13.** Continued from `50b43967722c73ced5faee067c745b0ded18fd5b`.
Actual Arabic page images were inspected; no model generation, scoring or training
was performed. This is AI technical collection, not qualified human validation.
The existing v3.2 kit and validators are reused; no new collection application.

| Work | Evidence actually inspected | Capture / remaining gap |
|---|---|---|
| Algebra: **كتاب الجبر والمقابلة**, al-Khwarizmi | [ACO/Columbia catalogue](https://sites.dlib.nyu.edu/viewer/books/columbia_aco000196/1?embed=1&lang=ar); Egyptian University Faculty of Science, Cairo, 1939; [PDF p.34 / printed p.20](https://mc.dlib.nyu.edu/files/books/columbia_aco000196/columbia_aco000196_lo.pdf#page=34) | **One private capture**, `DEV:KHW-1939:P20:01`, original main-body equation statement. Both branches and the requested square quantity were checked by exact offline arithmetic. Human transcription/origin/reference/difficulty and overlap checks remain pending. |
| Arithmetic: **خلاصة الحساب**, al-Amili | QDL / British Library **IO Islamic 1748**, [f.3r, image24/90](https://www.qdl.qa/en/archive/81055/vdc_100141531730.0x000019) and [f.4r, image26/90](https://www.qdl.qa/en/archive/81055/vdc_100141531730.0x00001b); authored work 1595, copy 1636 as catalogued | **Pending, zero captures.** Dense later marginal/interlinear material and small numerical working prevent a dependable complete transcription. The multiplication table on f.4r is not counted as a separately posed problem. |
| Geometry: **مفتاح الحساب**, al-Kashi | QDL / British Library **Add MS7470**, [f.30r, image72/240](https://www.qdl.qa/en/archive/81055/vdc_100066015376.0x000049) and [f.45v, image103/240](https://www.qdl.qa/en/archive/81055/vdc_100066015376.0x000068); copy 1589 as catalogued | **Pending, zero captures.** Triangle-altitude examples and diagrams are visible at f.30r, but letter-based numerical notation, fractions and diagram labels cannot all be read confidently. No modern values, units or answer are inferred. |

## What is preserved in the private packet

The algebra packet keeps the short verbatim statement, its exact UTF-8 and
NFKC/whitespace-normalized hashes, attribution, source-worked summary, modern
mathematical interpretation and checked reference separate. The source asks for
**مال**, distinct from its **جذر**; returning roots alone changes the requested
quantity. Both original branches are retained. The original body above the
horizontal rule is distinguished from modern editorial footnotes below it.
The reference summary is assistant-written and is not a diplomatic transcription
of all source workings, a human label, or an original student reasoning trace.
No new PDF-byte hash is asserted; the old v3.2 hash remains prior evidence only.

The private kit has **one metadata-complete capture and zero source-ready/eligible
problems**. The public manifest retains hashes and a private pointer, withholding
the answer; its unchanged validator therefore reports **zero complete public
metadata records**, explicitly `missing:reference_answer`. Neither count means
human approval. There are **zero student traces, zero assigned reviewers, zero
independent annotations and zero measured human timing sessions**. Forty planned
trace positions remain missing. The three pending screening entries include the
old algebra screen and two incomplete manuscript candidates, not three enrolled
problems or an estimate of source yield.

A private **blank Arabic exercise** asks the student to write personally, preserve
the original attempt and record actual assistance/exposure. The source solution
is visible on the same page; the packet has a separate answer-key folder and this
conversation disclosed reference information. Do not claim an unseen first attempt
when answers were seen. No AI-written or source-copied trace is registered as
developer-authored. Existing human worksheets remain header-only.

## Provenance, rights and eligibility

The [new technical evidence](native_pilot_v3_2/source_capture_status_v3_4.json)
records locators, identities, source-family uncertainty and remaining checks;
the old v3.3 screen and source register remain byte-identical. The existing
screening ledger retains its first entry and appends the two pending inspections.
QDL's selected witness notices explicitly mark **Public Domain**. [QDL's policy](https://www.qdl.qa/en/copyright-ethical-terms-reuse)
describes a most-territories belief and user responsibilities; [ACO](https://aco.dlib.nyu.edu/about)
states its public-domain belief. These are real provider evidence, not invented
permission letters or worldwide warranties. Intended private development use is
recorded; project use clearance and any future dataset release remain separate.

The algebra item stays development-only in the same family/lineage. A famous
historical quadratic example may occur in pretraining or later translations;
there is no contamination-free or modern-representative benchmark claim. Unknown
origin/overlap and pending permission declarations are not silently promoted.
Public Git contains metadata/status only, not the captured question, answer key,
student worksheet contents or a new problem dataset.

## Immediate human work

1. A qualified Arabic/mathematics reader verifies the algebra capture against
   the original page, all branches, requested quantity and provisional difficulty;
   records exact use scope and known-project/family overlap before intake.
2. A manuscript reader resolves the arithmetic operands and geometry numerical
   letters/fractions/diagram; incomplete readings remain pending until then.
3. The student saves an honestly disclosed original Arabic attempt. Qualified
   external assessors personally assign Arabic step/final judgments. A disclosed
   single-reviewer development start is possible; full v3.2 completion still needs
   independent A/B and a distinct C for disputes. Self-checks are not labels.

The supervisor's larger native benchmark, performance-gap explanation and
downstream solving improvement remain unmet scientific dependencies. This one
capture is measurable sourcing progress, not evidence of model efficacy.

Validation uses the existing `native_pilot_v3_2.py` and
`native_pilot_review_v3_2.py` on both public and private views, direct private
file/reference identity checks, and exact reference arithmetic. The published
revision's Windows/Linux Actions are software evidence only. Frozen42, original
outputs, checkpoints, attempt histories and human-QC records are preserved;
diagnostic24 remains inactive and pilot20 permanently exhausted.
