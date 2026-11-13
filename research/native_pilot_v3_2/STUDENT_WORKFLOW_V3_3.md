# Student-led collection and Arabic trace writing

Use the existing twenty-slot manifest, trace CSV, assessor worksheets and timing
log. Start with one actual question per available domain, then expand gradually.
The [source shortlist](domain_source_screening_v3_3.csv) contains sources only;
the student must inspect actual question text before treating one as collected.
One source-located [algebra candidate](algebra_item_screen_v3_3.json) is recorded
at PDF page 34 / printed page 20. Its original problem quantity and solution
branches need checking. A worked solution is visible on the same page: disclose
exposure, and do not call a reference-informed attempt an unseen first solution.

1. **Select and preserve.** Read the original Arabic question, record its exact
   witness/page/item, and save permissible source/evidence privately. Keep the
   original wording, quantities, diagrams and any ambiguity. Record the real
   family/lineage; numeric variants and later corrections are not new independent
   problems. Check rights and known-project overlap before proposing eligibility.
2. **Attempt in Arabic first.** Hide worked solutions/answers until the first
   attempt is saved. Write your own reasoning in Arabic, one assessable claim or
   transition per numbered step. Mathematical notation is allowed. Do not ask AI
   to write, translate, complete or repair a trace and then claim it as your own.
   Record actual exposure/assistance honestly, including accidental answer exposure.
3. **Preserve before checking.** Save the original attempt and actual authorship
   date in a private copy of [the trace sheet](DEVELOPER_TRACE_TEMPLATE.md). Then
   self-check separately. Do not overwrite errors. Link a correction as a new
   revision of the same trace; do not count it as a new independent candidate.
   Do not deliberately insert errors merely to fill a class quota. Report missing
   negative-step coverage when it occurs.
4. **Register actual authorship.** In `traces.csv`, use the existing
   `trace_origin=human_original_arabic`, your actual private `provider_ref` and
   `provider_person_key_sha256`. The hashed private origin-evidence sheet must
   explicitly say **student_developer / developer_authored**, with actual writing
   language, date, assistance/exposure and revision lineage. This is not an expert
   annotation or a model output. Hash actual trace/step/evidence bytes, never
   placeholders. The source/reference authoring and trace provider roles remain
   disclosed. Use trace positions 1/2 only for actual prespecified traces.
   Copying/paraphrasing the source's worked steps belongs under
   `trace_origin=source_worked_arabic`, not developer-authored original reasoning.
5. **Separate self-checks from labels.** Keep your self-check in the evidence
   folder. Leave `assessor_a.csv`, `assessor_b.csv` and `adjudication.csv` to the
   actual independent qualified people. They must not see your proposed labels,
   each other's judgments, AI suggestions or PRM scores during independent work.
6. **Record actual effort.** Use `timing.csv` for real source screening, permissions,
   transcription and `trace_creation` sessions (`role=provider`). Record actual
   units, start/end and interruptions. Do not turn an estimate into measured time.

البداية العملية: اختر مسألة عربية الأصل ذات مصدر واضح، واحفظ نصها كما هو، ثم
اكتب محاولة بالعربية بنفسك قبل الاطلاع على الحل. احفظ المحاولة الأصلية بأخطائها
إن وجدت، وبعدها سجّل فحصك الذاتي منفصلا. لا تسمّ فحصك الذاتي «تقييما مستقلا».
المقيم الخارجي المؤهل هو من يضع تسميات الخطوات فعليا؛ ولا يُنشئها هذا الملف أو
المساعد. عند تصحيح محاولة قديمة، احتفظ بها واربط النسخة الجديدة بها.

One qualified external reviewer can begin a clearly labeled single-reviewer
development batch. The unchanged full pilot protocol still requires independent
A/B and a separate C. The student's responsibility is to organize and deliver the
evidence, not to fabricate independence by reviewing their own authored traces.

Run the existing read-only checks against the **private** working directory, as
described in [HUMAN_ANNOTATION.md](HUMAN_ANNOTATION.md). No new launcher, inference,
automatic labeling, budget or data-release action is introduced. Human-authored
examples cannot be inserted into future fixed model pools as model generations.
