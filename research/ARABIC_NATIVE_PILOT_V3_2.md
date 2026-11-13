# v3.2: development-only Arabic-native human feasibility pilot

**v3.3 continuation:** [student-led collection](ARABIC_NATIVE_COLLECTION_V3_3.md)
adds four documented source leads and a populated five-domain source screening
to the reused kit. The four-lead source table/counts below describe the v3.2
milestone; current register totals are in the replayable collection status.
One source-located algebra candidate now has metadata in the reused manifest;
transcription, reference, eligibility and human review remain pending.

**Target:** twenty genuinely Arabic-native mathematics problems, four each in
arithmetic/number theory, algebra, geometry, probability/combinatorics and applied
word problems. Each domain has two introductory and two intermediate target
slots. All are development-only. Target slots are not collected examples.

The [collection manifest](native_pilot_v3_2/collection_manifest.csv) is immediately
editable in a **private copy**. It records problem/source identities, exact source
locator, family/lineage, origin evidence, domain/difficulty/register, private text
reference and hashes, provisional reference answer, permissions, overlap audit
and proposed eligibility. No problem text, answer or reviewer identity is invented
in the public template. Import CSV as UTF-8 text so Arabic and mathematical
strings are not silently reformatted by spreadsheet software.

## Actual source-screening evidence

The [source register](native_pilot_v3_2/source_register.json) records an AI technical
screen of primary library/publisher/university evidence on 2026-11-13, Asia/Shanghai.
It is not a qualified human source review or a licence grant.

| Lead | Observed primary evidence | What remains before an item can enter |
|---|---|---|
| ACO/Columbia: *كتاب الجبر والمقابلة*, Egyptian University edition, 1939 | [Library catalogue](https://sites.dlib.nyu.edu/viewer/books/columbia_aco000196/1?embed=1&lang=ar) credits al-Khwarizmi and identifies the edition/provider. [ACO copyright guidance](https://aco.dlib.nyu.edu/about) states NYU's public-domain belief. The title and opening of the privately inspected scan support historical Arabic composition. | Exact problem/page, original text versus modern editorial material, reference validity, family overlap, historical register and applicable item/use scope still need review. Do not treat all Arabic catalogue records as original Arabic. |
| KSU Press: *مبادئ الإحصاء والاحتمالات* | [Official catalogue](https://ksupress.ksu.edu.sa/ar/textbooks) gives title/author credits. Its [rights page](https://ksupress.ksu.edu.sa/ar/node/306) is a coming-soon placeholder; no applicable reuse grant was observed. | Actual edition/items, native derivation history and private-pilot permission are unresolved. Arabic title/author names alone are insufficient. |
| KSU faculty counting exercises | [Official course page](https://faculty.ksu.edu.sa/ar/aalzughibi/course/168645) links the [worksheet](https://faculty.ksu.edu.sa/sites/default/files/tmryn_trq_ld_1_0.pdf); some items refer to a textbook. | Trace the original item/edition and obtain applicable permission. Do not assume the hosting lecturer authored the questions. |
| Hindawi: *الرياضيات: مقدمة قصيرة جدا* | The [publisher's PDF](https://downloads.hindawi.org/books/17075726.pdf), title/copyright pages, credits a translator and explicitly identifies an English original. | **Excluded from native origin.** Arabic publication does not change its English-derived origin. |

Only metadata, limited evidence excerpts and source pointers are in this kit.
One ACO PDF was privately inspected and its actual SHA256 recorded; neither that
book nor an unreviewed problem corpus was committed. Item permissions are not
cleared by a book-level notice in this register. Verify the exact edition and
intended scope; do not infer worldwide legal clearance from a provider belief.
No rightsholder or prospective reviewer was contacted.

## Intake acceptance criteria

1. The original problem was authored in Arabic, with item-specific documentary
   evidence and an independent source assessment. Unknown or translated origin
   does not count. Commissioned original Arabic material is another route, but
   requires an actual author, provenance and permission—not an AI-written example.
2. The full source locator and immutable raw/normalized identities are recorded;
   the problem has an independently checkable reference and no unresolved premise
   or answer ambiguity. Preserve any rejected source and its reason privately.
3. Private development-pilot use is supported by actual applicable permission or
   rights evidence. Public redistribution, training/export and English translation
   are separate scopes and are not authorized by this milestone.
4. Twenty canonical problem lineages remain distinct. Prefer twenty template
   families, with a maximum of two problems per family. Numeric variants cannot
   inflate n. Record source/register clustering; historic Arabic is not evidence
   of representativeness for modern Arabic. Audit known authorized project sources
   for overlap; do not access restricted benchmarks such as Global-MGSM.
5. Pilot families stay development-only and must be excluded from any future
   locked test, including translations, paraphrases and number substitutions.
   Do not silently change a target's domain or split to fill the twenty slots.

The source checks are prerequisites for human review, not completed semantic
validation. Two independent qualified Arabic-speaking mathematics assessors and
a separate adjudicator must supply actual problem/reference, step and final-answer
judgments. No assigned reviewers or completed judgments exist in the current kit.

## Reasoning without model inference

This small human feasibility exercise can use permission-cleared originally
Arabic **source-worked reasoning** or an **independent human's original Arabic
attempts**. Target two traces per problem; never translate English traces and call
them original Arabic. A trace author must not assess or adjudicate their own work.
Do not use AI to populate missing traces, answers or labels. If only correct traces
are available, report missing error-class coverage rather than manufacture negatives.
Such source/human traces measure annotation feasibility; they are not model
generations or a fixed-candidate solver-efficacy experiment. Do not insert checked
reference solutions into a later model candidate pool.

## Current state and software reuse

The reproducible [collection status](native_pilot_v3_2/collection_status.json) has
**20 targets, four screened source leads, zero entered problem records, zero
source-ready problems and no human validation**. Book-level documentary support
does not fill a problem slot. Missing permissions, actual item selection/reference
checking and unassigned qualified reviewers are the immediate blockers.

`native_pilot_v3_2.py` reads only the explicit CSV/register and prints aggregate
intake status. It does not follow private file references or authenticate source
truth. It reuses the v3 identity/validation primitives; the existing benchmark
auditor now accepts an explicit development-only split without relaxing human,
origin or provenance requirements. No model, scoring, budget, training or data
export path is introduced. The separate [human worksheets and instructions](native_pilot_v3_2/HUMAN_ANNOTATION.md)
and `native_pilot_review_v3_2.py` check human-record consistency and timing without
authenticating or inventing human work. The [feasibility report](ARABIC_NATIVE_FEASIBILITY_V3_2.md)
distinguishes current evidence from targets and describes the 100/250/500 decision.
Neither CI nor preparation is human approval.
