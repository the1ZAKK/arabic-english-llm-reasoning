# Session handoff

Read this file, then verify the current research branch and CI before resuming. The authoritative project history is GitHub; no work continues indefinitely after a session ends.

Branch: `research/arabicprm-v2-production`. Previous verified execution milestone: `4434b29fdbce65abf13fcbd8ede03223c7e106b1`, [CI 39049708362](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39049708362), Windows and Linux 209 tests each.

Read-only evidence milestone `65e803620919324b89adf88b2e74e1d23365d4ca` is verified: [CI 39053290606](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39053290606), Windows and Linux passed. The next containing commit implements separate context/glossary/risk preparation, exact completion inventory and pending human review; its own CI must pass before marking verified.

Verified baseline: selection 256 records / 2,753 steps; Batch01–08 64 AI drafts pending human QC, 45 pass current strict checks and 35 fields fail; Batch09–32 2,252 fields, 1,075 mechanical complete and 1,177 unresolved / 2,005 slots. Actual private plan gives 9 complete, 176 partial and 7 no-complete-field trajectories. No original files modified.

Blocking evidence: user reports pilot20 completed with 20 accepted fragments; actual report and HTML are not available in Work. They were requested once. Do not repeat semantic claims or counts as verified and do not reset the old allowance. A laptop-only offline tool can ingest them without additional inference.

Source-only preparation successfully reconstructed all 2,005 contexts from the actual private original plan. The 12-slot / 24-request paired experiment remains a proposal with no approval and no execution implementation. Arabic outputs are marked unavailable; no real pilot semantic analysis has been performed.

Prototype commit `270d537965fef20604d993d07afb7ceb9d72ab27`: [CI 39053835394](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39053835394), Windows and Linux passed. Current milestone adds the isolated recovery-v2 runtime/PowerShell package, native CI, two additional audit integration cases and six downstream masking/alignment/metric tests; 244 local offline tests passed. `RESEARCH_PROTOCOL_V2.md` is a methodology and thesis working draft, explicitly without missing experiment results.

Next safe tasks: wait for full Windows/Linux CI including the new native offline package; fix failures if any; only after success pin the offline CMD launcher and verify correct/incorrect hashes on native Windows. Finalize links/checksum/status. The code and docs remain research-branch only. Private `/recovery_artifacts/` is ignored and must not be committed. No model, training, dataset-export or scheduled-task command belongs in the offline runtime.

Gates: actual-pilot semantic review requires authentic outputs; human QC requires genuine reviewer actions; any new inference needs a separately approved budget and runtime; training/export need separate explicit authorization and reviewed eligible data. Global-MGSM remains prohibited. Do not import legacy GPU scripts, run Ollama, download a model, modify scheduled tasks or touch main.
