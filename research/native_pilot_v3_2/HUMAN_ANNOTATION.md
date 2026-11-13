# Human pilot: short coordinator and assessor instructions

**Purpose / الهدف:** test whether twenty evidenced original-Arabic problems can
be collected and independently annotated at a realistic cost. This is a human
development exercise, not a model-performance experiment. All people are currently
unassigned; reviewer, trace, assessor, adjudication and timing CSVs contain headers
only. Software checks cannot confirm
that an actual person performed a review.

## Before review / قبل التقييم

The coordinator makes a private working copy. Keep original evidence, source text,
reference derivations and any personal crosswalk outside the public repository.
Import CSV as UTF-8 **text**, preserving formulas, hashes, leading zeros and Arabic.
Do not open untrusted source text as spreadsheet formulas. Do not publish populated
worksheets, private paths, names or problem/trace text with a status summary.

1. Record **every** screened item in `screening_log.csv`, including rejected and
   unresolved items. A source-book lead is not an item. Keep the original rejection
   history when replacing a target candidate. `candidate_ref` equals `problem_id`
   if that item enters the twenty-slot manifest. Origin requires item-specific
   documentary evidence; Arabic script and an Arabic author name do not prove it.
2. Use `collection_manifest.csv` for the selected candidates. Record exact source
   edition/page/item, family and canonical lineage; hash the actual private files.
   Do not replace actual answers/hashes with plausible values. Assessed difficulty
   must match the slot; introductory means routine single-concept work, intermediate
   means linked concepts or a non-obvious choice. Assign one primary domain, record
   secondary concepts in notes. Domain/difficulty disagreements require review.
3. Obtain two qualified Arabic-speaking mathematics assessors (A, B) and a distinct
   qualified adjudicator (C). Verify actual qualifications and availability privately.
   Record actual pseudonymous refs and evidence hashes in `reviewers.csv`. Each
   real person has one stable random private person key across aliases; hash that
   key, not a guessable name. Maintain the private crosswalk. A/B/C must be distinct
   and independent of trace authorship; disclose relevant conflicts privately.
4. Register two distinct, permission-cleared originally Arabic source-worked or
   independently human-authored traces per problem in `traces.csv`. Preserve trace
   wording, step order and all existing mistakes. No model or English translation
   is allowed for this pilot. A human author cannot assess/adjudicate pilot traces.
   Correct-only traces are allowed but cannot establish error-discrimination coverage.
5. Freeze shared problem/reference/trace/step identities before A/B start. Hash
   `reference_answer` as exact UTF-8 bytes (`reference_hash` in the offline checker).
   Hash exact private step texts; `step_sha256_json` is an ordered JSON hash array.
   Index steps from **0**. The coordinator copies identity columns into each person's
   worksheet; each person supplies their own judgments and actual UTC review times.

## Independent judgments / أحكام مستقلة

تعملان بصورة مستقلة، ولا يطّلع أي مقيم على أحكام المقيم الآخر أو درجات PRM أو
اقتراحات الذكاء الاصطناعي قبل تسليم ورقته. لا تنقلوا تسميات من PRM800K أو من
حل إنجليزي. لا تفترضوا صحة الحل لأن جوابه النهائي صحيح، ولا تعتبروا جودة العربية
دليلا على صحة الرياضيات. احتفظوا بالنص الأصلي ولا تصلحوا أخطاءه بصمت.

Use only your assigned `assessor_a.csv` or `assessor_b.csv`. Retain dated submitted
originals privately; do not edit an original to make it agree with another reviewer.

| `kind` | Judgment to supply | Required distinction |
|---|---|---|
| `problem` (one per item) | `decision`: valid / invalid / uncertain; `origin_decision`: arabic_native / translated / uncertain; `reference_decision`: correct / incorrect / uncertain | Independently check premises, domain/difficulty, native-origin evidence and reference derivation. A collection declaration is not your answer. |
| `step` (every step of each registered trace) | `decision`: correct / incorrect / neutral / uncertain; `global_consistency`: consistent / inconsistent / uncertain; `depends_on_prior_error`: yes / no / uncertain | Local validity is evaluated given the stated previous claims; global consistency tracks the original problem. Error propagation is not automatically a new local error. Neutral is non-inferential text and remains masked; uncertainty is not a positive label. |
| `final` (one per trace, after its steps) | `decision`: correct / incorrect / uncertain; `first_error_step`: 0-based index / none / uncertain | Judge the actual final answer independently of step validity. Identify the earliest locally incorrect step; earlier uncertainty prevents a definite first-error index. |

Leave fields for other unit kinds blank. Record concise mathematical reasons for
errors, invalidity, translated origin or uncertainty in `notes`. Use actual review
times in `recorded_at_utc`; the tool supplies no identity, label or timestamp.

أمثلة تعليمية فقط، وليست بيانات للمعيار أو تسميات بشرية مكتملة:

- «٣ × ٤ = ١١» خطأ حسابي؛ لا تُغيّروا ١١ إلى ١٢ داخل المحاولة الأصلية.
- الانتقال من «سالب» إلى «موجب» أو عكس `<` و`>` خطأ رياضي، حتى مع عربية سليمة.
- محيط الدائرة يختلف عن مساحتها، ونصف القطر يختلف عن القطر؛ راجعوا الكمية والوحدة.
- إذا كانت خطوة سابقة قد أعطت `x=3` خطأ، فقد تكون الخطوة `2x=6` صحيحة محليا
  اعتمادا على تلك الفرضية، لكنها غير متسقة مع المسألة الأصلية. سجّلوا الاعتماد.
- الوصول إلى جواب صحيح بالصدفة لا يجعل الاستدلال صحيحا. الجواب النهائي حكم مستقل.
- خطأ لغوي لا يغيّر المعنى الرياضي يسجل في الملاحظات؛ الغموض الذي يغيّر الكمية
  أو العلاقة يستلزم `uncertain`. في مراجعة ترجمة منفصلة، الحفاظ على خطأ المصدر
  ليس خطأ ترجمة. هذا الدليل لا يحوّل أمثلة مترجمة إلى مسائل عربية الأصل.

## Adjudication / التحكيم

After both original worksheets are submitted, the coordinator compares their
judgments. C independently examines disagreements, uncertainty and any inconsistent
first-error/propagation account against the original evidence. C records a separate
reasoned row in `adjudication.csv` with both **exact original row digests**
(`native_study_v1.digest` of the CSV row dictionaries). Keep A/B unchanged. C must
not fill in an absent independent assessment; obtain the missing assessment first.
Unresolved decisions remain uncertain or cause exclusion, with reasons. Agreement
and a hash-consistent C row are not automatic human/corpus approval.

## Timing / قياس الوقت

Record actual sessions in `timing.csv`: UTC start/end, active minutes, interruptions,
task and observed unit count. Never estimate a session retrospectively as an actual
measurement. One person's sessions may not overlap. Count **checks**, not unique
problems, for the two independent reference checks; count individual step/final
judgments for annotation. Count underlying adjudicated units once, separately from
A/B judgments. Record permission work, transcription and trace creation separately;
do not hide them inside fast step-labeling rates. Preserve rejected-source work.

The checker reports total active person-hours and weighted minutes/unit, with the
observed event-rate range explicitly **not** a confidence interval. It lists the
existing v3.1 planner parameters not measured here (including English mirror work).
No timing automatically changes assumptions, approves a size or grants a budget.
It also reports pre-adjudication exact agreement separately for problem, step and
final units, including paired/missing denominators and uncertain ties. Agreement
includes uncertain ties and must not be called annotation accuracy. Actual step
lengths and resolved correct/incorrect/neutral counts remain separately visible.

Coordinator checks (offline, explicit private directory only):

```text
python -B research/prm_arabic_english/native_pilot_v3_2.py --directory PRIVATE_KIT
python -B research/prm_arabic_english/native_pilot_review_v3_2.py --directory PRIVATE_KIT
```

The scripts read these metadata worksheets only. They never follow evidence file
pointers, contact a model, authenticate people, export text or grant eligibility.
Share only an intentionally sanitized aggregate report; examine any private IDs in
error messages before sharing. Retain private originals and evidence for human audit.
