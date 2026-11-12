# Arabic-native pilot intake materials

Read [the v3.2 pilot plan](../ARABIC_NATIVE_PILOT_V3_2.md) first.

- `source_register.json`: observed source/rights metadata and explicit unknowns;
  four leads are not four enrolled problems.
- `collection_manifest.csv`: twenty planned development slots, four/domain;
  actual problem IDs, sources, answers and evidence remain empty.
- `collection_status.json`: reproducible current intake counts and blockers.
- [HUMAN_ANNOTATION.md](HUMAN_ANNOTATION.md): short Arabic/English instructions.
- `screening_log.csv`: every actual item considered, including rejected/pending
  candidates, so source yield cannot be inferred only from selected successes.
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
