# Evidence-gated roadmap

| Priority | Milestone | State | Required evidence |
|---|---|---|---|
| 1 | Frozen-source and baseline inventory | Verified, commit 65e8036; Windows/Linux CI 39053290606 passed | Reproducible aggregate and strict field checks; preserve all originals |
| 2 | Actual recovery-v1 output audit | Blocked on existing laptop report + HTML, requested once | Exact plan/model/20-request accounting, source context, authentic outputs; full reservation chain checked locally |
| 3 | Separate recovery-v2 prototype | Verified, commit 270d537; Windows/Linux CI 39053835394 passed | Context-bound prompt, glossary, risk flags, unchanged structural validators, no execution route |
| 4 | Pending human-review workflow | Prototype verified in CI 39053835394; added integration tests pending CI | Original output separated from proposed correction; actual reviewer actions required; immutable hashes |
| 5 | Windows offline verification launcher | Package installer implemented; native CI pending; CMD pin deferred until success | Native Windows and Linux CI green before pinning; SHA256 package/installer verification; no model calls |
| 6 | Corpus completion inventory | Verified in CI 39053835394 | Slot-to-field reconstruction in memory, record counts, explicit missing evidence; no dataset export |
| 7 | Downstream / thesis protocol | Implemented; own CI pending | Offline split, masking, uncertainty and readiness contracts; inactive design config; methodological draft with missing results marked |
| 8 | New paired diagnostic experiment | Not authorized | Review actual pilot, approve design and a separate fixed budget; do not reuse exhausted allowance |
| 9 | Human QC, corpus completion, training, evaluation | Blocked by genuine review, missing translations and separate execution permissions | Evidence-based decisions, resource feasibility and authorized runs; no unreviewed export |

Next safe action: verify native recovery-v2 packaging and full Windows/Linux CI, then pin and test a single offline CMD launcher. Actual pilot outputs remain the scientific-analysis blocker. No indefinite background execution is implied by this roadmap.
