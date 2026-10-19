# ArabicPRM-T v2 project evidence

Current evidence update (2026-10-19): [recorded pilot findings](PILOT20_FINDINGS_V2_1.md) supersede the historical missing-output statements below. All 20 authentic recorded fragments are available in the private derived audit; no new inference or human QC occurred.

Working branch: `research/arabicprm-v2-production`. This inventory supersedes older completion summaries without changing their historical files. Machine-readable evidence: [RECOVERY_V2_EVIDENCE.json](RECOVERY_V2_EVIDENCE.json), reproduced by `prm_arabic_english/project_evidence_v2.py`.

| Scope | Verified state | Completion criterion / limitation |
|---|---|---|
| Frozen selection | 256 trajectories, 204 train / 52 dev, 2,753 reasoning steps; 3,009 source fields; unique problem groups, no train/dev group overlap | Frozen queue hashes and selection manifest verified; 757 fields in Batch01–08 plus 2,252 in Batch09–32 reconcile exactly |
| Batch01–08 drafts | 64 records, AI assistant recorded as translator; human QC pending | 45 records pass the **current** strict source-preserving checks; 35 fields in the other 19 require investigation. These are validator failures, not established semantic-error counts. Original drafts unchanged |
| Batch09–32 original recovery plan | 192 records; 2,252 fields: 1,075 mechanically validated, 1,177 unresolved; 2,005 missing prose slots | Original plan identity verified; historical nine attempts per missing slot preserved |
| Baseline trajectory completion in Batch09–32 | 9 all-fields-mechanical / 176 partial / 7 with no complete fields | Mechanical completeness does not establish semantic correctness |
| Recovery-v1 pilot20 | Derived actual laptop audit + exact Markdown independently revalidated; 20 candidate/context hashes and completion inventories reproduce | 1,089 complete fields (+14), 11 complete trajectories (+2), 1,985 missing slots. Laptop reports 20 spent / zero remaining and ledger verification; raw ledger not uploaded. Human QC pending |
| Historical v1 accepted registry | Recorded 32 accepted records / 298 steps, separate cohort | Existing recorded decisions preserved; do not add to v2 completion; manifest says pilot trainer incompatible |
| Recovery-v2 | Separate context/glossary/risk prototype, pending review UI and native offline Windows package/launcher verified | 245 tests passed on Windows and Linux at 0ef991f, including native CMD positive/negative hash checks; zero inference authorized |
| Training / evaluation | Historical GPU scripts inspected using AST only; new pure offline masking/alignment/metric contracts tested | No trainer/export implemented. Real human QC, resource measurements, model/environment pins and explicit authorization remain required |
| Thesis / conclusions | Provenance and methodological evidence available; semantic and downstream results missing | No invented accuracy, training results, overall completion percentage or human QC |

Original execution workflow: commit `4434b29fdbce65abf13fcbd8ede03223c7e106b1`, [Windows/Linux CI 39049708362](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39049708362), 209 offline tests per platform. This does not prove translation quality.

Read-only audit milestone: `65e803620919324b89adf88b2e74e1d23365d4ca`, [CI 39053290606](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39053290606), both Windows and Linux passed. Source-only recovery-v2 preparation verified all 2,005 original unresolved contexts; actual Arabic outputs remain unavailable. Its deterministic source-risk proposal contains 12 paired slots / 24 proposed requests, not an approved allowance.

Prototype milestone: `270d537965fef20604d993d07afb7ceb9d72ab27`, [CI 39053835394](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39053835394), both platforms passed. See [RESEARCH_PROTOCOL_V2.md](RESEARCH_PROTOCOL_V2.md) for the thesis methodology draft, source/translation error distinction, paired diagnostic and downstream gates.

Packaging/contracts milestone `2ce19a17570829495856da1f732d96b06694f402` passed [CI 39055459666](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39055459666): Linux 244 tests in 52.176 s; Windows 244 in 383.270 s, plus native frozen-source package verification. Legacy scheduled-task steps were skipped. The [single offline Windows launcher](RECOVERY_V2_WINDOWS.md) is pinned to this tested implementation; its publication commit adds one exact-hash regression and native CMD success/tampered-hash checks. No real pilot semantic results have been established in Work.

Launcher publication `0ef991fdbf2a0fe3cf0269aabfcc3665637ee870` passed [CI 39056158971](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39056158971): Linux 245 tests in 56.168 s; Windows 245 in 241.689 s, plus native package and CMD checks. Exact CMD SHA256: `67320c2326cb109e8697b31b43eddf14c0772ab7c016ec3926c86ce1415335f5`. No code or launcher bytes change in the final documentation handoff.

[Strict revalidation notes](STRICT_REVALIDATION_NOTES_V2.md) document three inspected cases: an English compound misclassified as a source math literal and translated annotation prose inside frozen LaTeX environments. These qualify the current-policy failures; they are not human semantic judgments or a classification of all 35 cases. The frozen parser/plan remain unchanged.

Plan: `446191b88e072c291ff34388a7fbb4166a6813639a63bb2ef54896431c6e7e4e`. Model: `qwen3:4b`, digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`. The old 20-request allowance is closed; this work authorizes zero new requests. No training, export, scheduled tasks, model downloads or Global-MGSM access.

Recovery-v2.1 development: separate glossary/policy/context payloads, all-20 provisional case review, resumable offline human QC, inactive revised diagnostic and native offline package. [Decision report](RECOVERY_V2_1_DIAGNOSTIC_DECISION.md): design-review candidate only; no executor, approval or inference. Evidence milestone aceacd47 passed [CI 39219153070](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39219153070): Linux 249 tests in 41.346 s, Windows 249 in 358.591 s plus existing native launcher checks; scheduled-task execution skipped. New v2.1 changes require their own CI.
