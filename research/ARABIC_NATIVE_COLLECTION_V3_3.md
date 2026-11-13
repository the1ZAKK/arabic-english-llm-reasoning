# v3.3: student-led native collection — current progress

**2026-11-13, Asia/Shanghai.** Reuses the [v3.2 kit](native_pilot_v3_2/README.md).
The student organizes collection and writes Arabic attempts; external people supply
independent mathematical labels. No new application or annotation framework.

## Five domain-specific source screenings

The populated [source screening CSV](native_pilot_v3_2/domain_source_screening_v3_3.csv)
contains **source-level records**. The [register](native_pilot_v3_2/source_register.json)
preserves four v3.2 records and adds four. One algebra candidate was subsequently
located by visual inspection; the other leads remain catalogue-level.

| Domain | Original Arabic work / witness | Evidence and rights status | Next student action |
|---|---|---|---|
| Arithmetic / number theory | **خلاصة الحساب**, بهاء الدين محمد بن حسين العاملي; IO Islamic 1748 | [QDL catalogue](https://www.qdl.qa/en/archive/81055/vdc_100106886354.0x000001) identifies Arabic authorship and distinguishes authorial from scribal colophons. Item marked **Public Domain**. | Open integer/fraction chapters, ff. 2v–9v / 9v–13r. Select one explicit numerical exercise; separate the main text from later annotations. |
| Algebra | **كتاب الجبر والمقابلة**, محمد بن موسى الخوارزمي; Egyptian University edition, 1939 | [ACO/Columbia catalogue](https://sites.dlib.nyu.edu/viewer/books/columbia_aco000196/1?embed=1&lang=ar) rechecked; NYU states its **public-domain belief**. Browser inspection located an original-text worked example on **PDF p. 34 / printed p. 20**. | Transcribe the original paragraph privately, excluding editorial footnotes. Verify the requested quantity and all branches; record same-page worked-solution exposure honestly. |
| Geometry | **مفتاح الحساب**, جمشيد بن مسعود الكاشي; Add MS 7470 | [QDL catalogue](https://www.qdl.qa/en/archive/81055/vdc_100040164536.0x000001) identifies the authored Arabic work and mensuration section. Item marked **Public Domain**. | Inspect ff. 28v–61r; select one readable numerical geometry problem with its complete diagram and units. |
| Probability / combinatorics | **فقه الحساب**, ابن منعم العبدري; Dar al-Aman, Rabat, 2005; ISBN **9981941522** | [National-library record](https://www.bibliotheque.nat.tn/BNTK/doc/SYRACUSE/5473401/%D9%81%D9%82%D9%87-%D8%A7%D9%84%D8%AD%D8%B3%D8%A7%D8%A8?_lg=ar-TN) verifies Arabic edition/credits. Indexed excerpts of the [institutional journal study](https://www.almajidcenter.org/wp-content/uploads/2022/05/Publication/Attachments/Afaq%20Magazine/Issue%2049.pdf), pp. 172–181, support a combinatorial section. **Edition access and reuse permission pending**. | Obtain lawful access and inspect the Arabic combinatorial text and rights page. Do not convert a modern foreign-language study into a purported native question. |
| Applied word problems | Arabic inheritance-share commentary attributed to **محمد ابن المرحوم الشيخ يوسف الفرضي**, inserted in Add MS 7469 | [QDL catalogue](https://www.qdl.qa/en/archive/81055/vdc_100040139973.0x000001) separately credits this insert; host marked **Public Domain**. Catalogue says ff. **181–182**, but its signature reference says **102r**: **locator unresolved**. | First verify the images/author/folio. Then choose arithmetic distribution with explicitly stated shares. Exclude unclear legal premises. Do not credit this insert to the host work's author, Ibn al-Majdi. |

The fifth title is descriptive. The probability/combinatorics lead supports
**combinatorics**; the applied lead remains conditional on resolving its locator.

Use the matching QDL item notice as rights evidence; no permission letter is
invented or automatically required for public-domain material. Its [reuse policy](https://www.qdl.qa/en/copyright-ethical-terms-reuse)
describes a most-territories belief, not a worldwide warranty. Retain the exact
notice, witness and intended scope. The old Hindawi translation stays **rejected
for native origin**; KSU leads remain pending. No dataset-release rights are granted.

## What was actually collected

**Five source screenings; eight register records; three explicit QDL public-domain
marks, one ACO belief and one shortlisted edition with reuse pending.** Actual
fully transcribed/eligible questions, answers, developer traces, reviewer assignments,
human labels and timing records: **zero**. The existing manifest and item ledger now
contain **one pending source-located algebra candidate**, `DEV:KHW-1939:P20:01`,
with [AI technical inspection evidence](native_pilot_v3_2/algebra_item_screen_v3_3.json).
It has no raw/normalized problem hash, captured text or verified reference answer;
collection origin, permissions, difficulty and overlap remain unresolved.

Following the publisher's link made the NYU PDF reachable; the cloud browser then
displayed the actual Arabic page. This updates the initial failed retrieval, without
claiming a new PDF-byte hash. Other image/text access remains limited (QDL direct
probe HTTP 403; large-PDF reader limits). Student transcription and independent
review are still needed. Historical register and manuscript reading cost limit
these leads' suitability for a modern Arabic benchmark.

## Student's next collection session

1. Privately copy the kit. Start with arithmetic/algebra/geometry; resolve the other
   two leads in parallel. Inspect actual items, retain source/rights/reference and
   family evidence, and fill the existing manifest/item ledger with real metadata.
2. Use the [trace sheet](native_pilot_v3_2/DEVELOPER_TRACE_TEMPLATE.md) and
   [workflow](native_pilot_v3_2/STUDENT_WORKFLOW_V3_3.md) to preserve your original
   Arabic attempt before self-checking. Record **developer_authored** explicitly;
   revisions and self-checks are not independent candidates or external labels.
3. Start authentic external review and timing on a small batch before scaling.
   If archival sourcing fails, genuinely original student-written Arabic questions
   are a manual alternative with honest provenance and independent validity review;
   none has been authored here.

## Minimum outside involvement

The supervisor's stated label-origin requirement specifies no count. Its literal
minimum is **one qualified external Arabic-mathematics human personally labeling
every included step and checking references/final answers**, independently of the
student author. This is a **single-reviewer development stage**, with no inter-rater
reliability claim or completed two-reviewer gate.

Unchanged v3.2 completion still requires **two independent external assessors A/B
and a distinct qualified C**. A/B review all included steps/finals; C handles disputes
and uncertainty, not a third full pass. Reserve a real C; do not fabricate reviews.
The student does not assess/adjudicate their own traces. Nobody is assigned here.

**Next measurable milestone:** actual selected questions and preserved student-authored
Arabic attempts, followed by authentic external labels and observed work rates.
No inference/scoring, training, active budget, unreviewed export, frozen-artifact
change or benchmark-approval claim is part of this milestone.
