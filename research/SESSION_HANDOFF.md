# Session handoff

Read this file, then verify the current research branch and CI before resuming. The authoritative project history is GitHub; no work continues indefinitely after a session ends.

Branch: `research/arabicprm-v2-production`. Previous verified execution milestone: `4434b29fdbce65abf13fcbd8ede03223c7e106b1`, [CI 39049708362](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39049708362), Windows and Linux 209 tests each.

Current milestone adds the read-only project evidence collector, public aggregate and five durable project records. Its CI must pass before marking verified. See the commit history for the containing SHA; do not embed a self-referential commit hash.

Verified baseline: selection 256 records / 2,753 steps; Batch01–08 64 AI drafts pending human QC, 45 pass current strict checks and 35 fields fail; Batch09–32 2,252 fields, 1,075 mechanical complete and 1,177 unresolved / 2,005 slots. Actual private plan gives 9 complete, 176 partial and 7 no-complete-field trajectories. No original files modified.

Blocking evidence: user reports pilot20 completed with 20 accepted fragments; actual report and HTML are not available in Work. They were requested once. Do not repeat semantic claims or counts as verified and do not reset the old allowance. A laptop-only offline tool can ingest them without additional inference.

Next safe tasks: finish the separate recovery-v2 context/glossary/risk prototype and pending bilingual review interface; add offline regression tests; run Windows/Linux CI; pin an offline SHA256 Windows launcher after success; prepare downstream masking/evaluation and thesis protocols. Update roadmap/status as each milestone is verified.

Gates: actual-pilot semantic review requires authentic outputs; human QC requires genuine reviewer actions; any new inference needs a separately approved budget and runtime; training/export need separate explicit authorization and reviewed eligible data. Global-MGSM remains prohibited. Do not import legacy GPU scripts, run Ollama, download a model, modify scheduled tasks or touch main.
