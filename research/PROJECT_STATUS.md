# ArabicPRM-T v2 project evidence

Working branch: `research/arabicprm-v2-production`. This inventory supersedes older completion summaries without changing their historical files. Machine-readable evidence: [RECOVERY_V2_EVIDENCE.json](RECOVERY_V2_EVIDENCE.json), reproduced by `prm_arabic_english/project_evidence_v2.py`.

| Scope | Verified state | Completion criterion / limitation |
|---|---|---|
| Frozen selection | 256 trajectories, 204 train / 52 dev, 2,753 reasoning steps; unique problem groups, no train/dev group overlap | Frozen queue hashes and selection manifest verified |
| Batch01–08 drafts | 64 records, AI assistant recorded as translator; human QC pending | 45 records pass the **current** strict source-preserving checks; 35 fields in the other 19 require investigation. These are validator failures, not established semantic-error counts. Original drafts unchanged |
| Batch09–32 original recovery plan | 192 records; 2,252 fields: 1,075 mechanically validated, 1,177 unresolved; 2,005 missing prose slots | Original plan identity verified; historical nine attempts per missing slot preserved |
| Baseline trajectory completion in Batch09–32 | 9 all-fields-mechanical / 176 partial / 7 with no complete fields | Mechanical completeness does not establish semantic correctness |
| Recovery-v1 pilot | User reports 20/20 requests, 20 accepted fragments, no requests left | Actual `report.json` and `pilot_review.html` unavailable in this session. Counts, output semantics and post-pilot complete-field counts remain unverified |
| Historical v1 accepted registry | Recorded 32 accepted records / 298 steps, separate cohort | Existing recorded decisions preserved; do not add to v2 completion; manifest says pilot trainer incompatible |
| Recovery-v2 | Separate contextual/glossary/semantic-risk prototype in development | Offline tests, review interface, Windows packaging and CI required; zero new inference authorized |
| Training / evaluation | Historical GPU scripts inspected using AST only; model loads occur at top level | Do not import them for offline checks. New masked-label and evaluation contracts, real human QC, resource measurements and explicit authorization required |
| Thesis / conclusions | Provenance and methodological evidence available; semantic and downstream results missing | No invented accuracy, training results, overall completion percentage or human QC |

Original execution workflow: commit `4434b29fdbce65abf13fcbd8ede03223c7e106b1`, [Windows/Linux CI 39049708362](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39049708362), 209 offline tests per platform. This does not prove translation quality.

Plan: `446191b88e072c291ff34388a7fbb4166a6813639a63bb2ef54896431c6e7e4e`. Model: `qwen3:4b`, digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`. The old 20-request allowance is closed; this work authorizes zero new requests. No training, export, scheduled tasks, model downloads or Global-MGSM access.
