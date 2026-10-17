# Windows offline recovery-v2 review preparation

Download `prm_arabic_english/verify_semantic_recovery_windows_v2.cmd` from the containing GitHub commit, keep its `.cmd` extension and double-click it. No CMD or PowerShell commands are needed. The existing repository must be on `research/arabicprm-v2-production` under your Windows Documents directory, with Git and Python 3.11+ available. It fetches verified code from GitHub; it never contacts Ollama. There is no inference confirmation because this launcher cannot execute inference.

The launcher pins implementation commit **`2ce19a17570829495856da1f732d96b06694f402`**, after [Windows/Linux CI 39055459666](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/39055459666) passed 244 tests each and native Windows recovery-v2 packaging verified 2,252 frozen fields, 25 glossary terms and unchanged original code hashes. The publication commit adds the CMD exact-hash regression and native positive/negative hash checks; inspect the Actions run attached to that commit before treating the publication as verified. CI establishes software behavior, not real translation accuracy or completed human QC.

Exact launcher SHA256 (CRLF bytes):

```text
67320c2326cb109e8697b31b43eddf14c0772ab7c016ec3926c86ce1415335f5
```

Pinned PowerShell installer SHA256:

```text
0a13839d25de50216a1c0e2e7f2a2ce31838c9f155eff406b18c0fee0948a249
```

The CMD computes the downloaded installer's SHA256 before execution. The installer independently verifies its Python helpers, then installs an immutable package from canonical Git blobs and records every file's SHA256. It does not check out files or update the worktree, model, original supervisor or scheduled tasks. Existing packages must match exactly; corruption stops the run without replacement or reset.

The audit reads the fixed original plan and verifies its raw and canonical identities, 13 original runner hashes, all 814 protected snapshot entries, original history/checkpoint reconstruction, model digest recorded in the plan/approval/report, the permanently exhausted 20-request ledger, dispatch witnesses and external checkpoint. It auto-discovers the existing `report.json` and `pilot_review.html` through the original `LATEST_REPORT.txt` pointer and compares them against the local immutable ledger. It does not query the currently installed Ollama model: this is an audit of recorded results, not a new execution preflight. No model needs to run.

Any failed integrity check stops preparation. Do not delete or change original records to bypass it. New immutable artifacts are written only to:

```text
recovery_artifacts/recovery-v2/<original-plan-sha256>/<audit-sha256>/
```

| Artifact | Purpose |
|---|---|
| `semantic_audit.json` | Verified report accounting, source/context/output hashes, exact remaining jobs, baseline and post-pilot field/trajectory counts, provisional risks |
| `provisional_bilingual_QC.md` | English context and recorded Arabic, AI suggestions, categories/severity, explanations and separate source-reasoning warnings |
| `human_review.html` | Offline bilingual form; all human states start pending; opens automatically when a browser is available |
| `human_decisions_PENDING.json` | Blank, hash-bound initial human decision template; no invented identity or timestamp |
| `experiment_proposal_NOT_APPROVED.json` | Provisional 12-slot / 24-request paired proposal; approved false, zero requests authorized, no inference implementation |
| `review_manifest.json` | SHA256 of the immutable review files |

The console prints the exact paths and stays open. Review the original candidate in context, then choose pending/approved/rejected/needs_correction. Enter your actual reviewer identity, category/severity and explicit attestation before saving any non-pending human decisions. Save the separate JSON before closing; the form deliberately has no automatic persistence or overwrite of previous records. An approval concerns the **original** output. A different proposed correction remains separate and requires later independent review. Keep reviewer files private; no training eligibility is granted. Optional validation/import by the Python review tool writes to a separate immutable `human_reviews/<audit>/<decision-hash>/` directory, never to old QC files.

The runtime receipt is under `recovery_artifacts/recovery-v2/runtimes/2ce19a17570829495856da1f732d96b06694f402/semantic_runtime_sha256.json`. All generated recovery artifacts are Git-ignored to help keep approvals, raw ledgers, reviewer identities and unreviewed Arabic private. Do not force-add them.

Real pilot artifacts were not accessible in Work. The source-only development audit therefore labels Arabic outputs unavailable, keeps all semantic judgments unsupported and makes no post-pilot completion claim. The laptop launcher is how to verify those local files without additional inference. Share actual evidence for a full provisional bilingual analysis before making scientific claims. Genuine human QC still must be performed.

The original 20-request allowance remains closed forever. The next possible inference decision is a **separate** diagnostic design/budget review: at most 24 new requests across 12 source-paired slots, one request per slot per arm, 512 generated tokens per request, exact original qwen3 digest. First review the authentic pilot and proposed sample; then explicitly authorize a separate budget and reviewed execution runtime if desired. This offline launcher cannot activate that proposal. Training and dataset export remain separately gated.
