# Arabic-native pilot intake materials

Read [the v3.2 pilot plan](../ARABIC_NATIVE_PILOT_V3_2.md) first.

**v3.3 student-led continuation:** read the [short collection progress report](../ARABIC_NATIVE_COLLECTION_V3_3.md),
the populated [five-domain source screening](domain_source_screening_v3_3.csv),
and [student workflow](STUDENT_WORKFLOW_V3_3.md). Use a private copy of the
[developer trace sheet](DEVELOPER_TRACE_TEMPLATE.md) when actually writing Arabic
attempts. The source register now contains eight leads: four preserved v3.2
records and four new records. One original-text algebra candidate is now located
on PDF page 34 / printed page 20, with [technical evidence](algebra_item_screen_v3_3.json).
It is pending in the existing manifest/item ledger; no source question text, answer,
developer attempt or human review has been supplied.

- `source_register.json`: observed source/rights metadata and explicit unknowns;
  source leads are not enrolled problems. Three new QDL items have explicit
  provider public-domain marks; selected-item clearance remains pending.
- `collection_manifest.csv`: twenty development slots, four/domain; one algebra
  slot has source-candidate metadata, with transcription, reference and eligibility
  pending. Other slots remain empty targets.
- `collection_status.json`: reproducible current intake counts and blockers.
- [HUMAN_ANNOTATION.md](HUMAN_ANNOTATION.md): short Arabic/English instructions.
- `screening_log.csv`: every actual item considered, including rejected/pending
  candidates; currently one pending AI technical source inspection, not a human
  judgment. Source yield cannot be inferred only from selected successes.
- `reviewers.csv` and `traces.csv`: actual private role/evidence and original-Arabic
  trace identities, without public personal or mathematical content.
- `assessor_a.csv`, `assessor_b.csv`, `adjudication.csv`: separate independent
  problem, step and final judgments. All currently contain headers only.
- `timing.csv`: actual contributor sessions and units; no assumed times prefilled.
- `review_status.json`: reproducible zero-human-evidence status and missingness.

Make a private working copy before entering real problem text references,
permissions or personal identities. Never commit populated private materials,
copyrighted text or unreviewed datasets to the public branch. Actual source items
and qualified independent human review remain necessary. The kit has no model,
scoring, scheduling, training, approval or export action.

Maintainer check: `python -B research/prm_arabic_english/native_pilot_v3_2.py`.
This checks metadata only and does not acquire material or confer native status.
`native_pilot_review_v3_2.py --directory PRIVATE_KIT` checks completed private
worksheet records and timing arithmetic. See the [feasibility finding](../ARABIC_NATIVE_FEASIBILITY_V3_2.md)
for the measured evidence still needed before selecting a 100/250/500 scope.
