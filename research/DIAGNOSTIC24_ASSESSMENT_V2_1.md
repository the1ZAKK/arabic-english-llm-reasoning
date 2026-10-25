# Offline diagnostic24 assessment workflow

This is the next offline development step after the verified diagnostic runner. It implements assessment import and paired reporting **before any diagnostic data have been generated**. No actual diagnostic assessment, human approval, new request allowance or translation-quality result is created by this milestone.

The existing [preparation launcher and execution release](DIAGNOSTIC24_RUNNER_V2_1.md) remain unchanged. The proposed diagnostic still needs separate explicit design/budget approval, laptop integrity/model checks and a final local execution confirmation. The original exhausted pilot20 is never reused as a prospective control.

## Three separate actions

| Action | Input | Output and boundary |
|---|---|---|
| Prepare a blinded task | Original `blind_review.json` only | `assessment_PENDING.json` and instructions; AI by default; all decisions pending, identity/time absent; operator files are not read |
| Seal an assessment | The same blind file plus actual assessment JSON and explicit AI/human kind | New immutable assessment, blind copy and seal receipt; earlier assessments and original report files are preserved |
| Produce the operator comparison | Sealed assessment and the original five-file report bundle | Separate paired JSON/HTML; every available candidate must have a decision or explicit uncertainty before the tool reads the mapping |

Use `diagnostic_assessment_v2_1.py` for these operations. The CLI accepts `--repo-root`, `--blind-review`, optional `--assessment`, explicit `--assessor-kind ai|human`, and optional `--operator-bundle` after an assessment. It has no execution, approval, model, reset, refund or training mode. It refuses an operator bundle without an assessment. All writes are confined to `recovery_artifacts/diagnostic-assessments-v2.1/<blind_sha256>/`, outside the original runner, its charges/guards and every historical workflow.

The current Windows preparation launcher continues to prepare only. The new assessment tool does not alter or replace it, or change the pinned execution runtime. After an eventual authorized run, you can give GPT **only `blind_review.json` first**. GPT can complete the explicit AI assessment, which this importer validates and seals. The operator bundle is supplied afterward for accounting and comparison. This avoids asking you to fill another pilot20 form; it does not substitute for independent human QC.

## Source, output and assessor integrity

Each pair must match the fixed proposal's full frozen context hash, source-slot hash, record identity and order. The schema admits A/B only, with no arm annotations or inherited human decisions. Every assessment binds the blind-file identity, prepared spec, plan, proposal and original candidate hashes. It cannot drop pairs, replace candidates, promote a hard-rejected output to faithful or judge an unavailable response as correct. A source reasoning concern is recorded separately; original English, native source ratings and source labels are never edited.

Default tasks have no assessor identity, assessment timestamp, blinding attestation or human attestation. Non-pending decisions require the assessor's actual identity, actual recorded UTC time, explanation and blinding declaration. An error also needs severity and categories. The importer does not invent missing identities, times or measured review duration. A seal's actual processing time is explicitly separate from the supplied assessment time. Identity, clock, measured duration and blinding are recorded assertions, not authenticated facts.

AI and asserted human records use an explicit kind. An AI document cannot validate through the human import mode or attest human review. Human imports require an actual personal-review attestation. Neither kind grants global human-QC completion, source-label adjudication, independent correction approval or training eligibility. Human authentication and independent adjudication cannot be established by a JSON validator.

Corrections are separate proposals. The original Arabic fragment, full source field and reasoning boundary remain unchanged. Every correction passes the existing Arabic, mathematical, numerical and reasoning-boundary validators plus the full-field literal-splice check. Corrections that pass still require independent review and are never inserted into corpus/checkpoint files by this tool.

## Paired report and evidence limits

The operator input is the original five-file bundle: `report.json`, `blind_review.json`, `blind_review.html`, `unblinding_key.json` and `diagnostic_results.html`. The importer checks canonical JSON, rendered HTML bytes, exact plan/model/execution release/limits, public approval-schema fields, observed runtime metadata, original outcome hashes, fixed dispatch indices, the balanced A/B mapping and every candidate/status/count association.

These are **bundle consistency checks**. A portable bundle does not replay the laptop's raw immutable reservation ledger, authenticate the device, prove absence of coordinated rollback, or independently authenticate approval. The analysis records that limitation. The existing runner remains responsible for read-only local ledger/protected-history verification before generation. No portable review document can authorize a request.

The report includes:

- All twelve pairs in the denominator, including failed, interrupted, unattempted, pending and uncertain observations.
- Control wins, contextual wins, ties and unresolved pairs from the actual supplied assessments. Ties distinguish both faithful from both erroneous; an error tie is not success.
- Mechanical acceptance per **charged** reservation, with rejected, interrupted and unattempted counts shown separately for each arm.
- Original consumed/remaining allowance and rejection categories, without refunds or replacement observations.
- Strata and source-problem clusters, assessor-reported major/critical errors, separate English-source concerns, and corrections awaiting independent review.
- Explicit assessor kind, supplied review time or unknown duration, pending human QC, false training eligibility and zero inference authorization.

The tool seals the supplied assessment before loading the operator mapping and blocks early unblinding while any available candidate remains pending. It cannot prove that an assessor never viewed a mapping elsewhere. Unblinding a partial run reveals the stable mapping for that experiment: the same assessor must not later claim resumed outputs were assessed blind. Keep the key away from future independent assessors. Missing responses remain unresolved and consume their reservations.

Twelve purposive pairs across seven source problems remain a small clustered development diagnostic. There is no held-out efficacy estimate, causal attribution to one prompt component, automated development-gate pass, corpus accuracy claim or training/export permission. The [scientific decision criteria](RECOVERY_V2_1_DIAGNOSTIC_DECISION.md) still require genuine independent human review and adjudication.

## Verification

Regression tests use disposable non-production plan/model/proposal identities and synthetic outcomes. They cover source/candidate/order tampering, AI/human separation, missing metadata, hard-failure promotion, correction mathematics/numbers/language/boundaries, missing-response accounting, error ties, source-label separation, approval/runtime/counter corruption, seal tampering, idempotent import, source-file races and early unblinding. Public-source tests reconstruct the real twelve contexts/seven groups as empty pending tasks. An actual CLI subprocess denies socket access and preserves a synthetic nine-attempt checkpoint.

The shared Windows/Linux offline suite includes this module. Existing native Windows diagnostic package, correct/wrong-hash launcher and CI mode guards remain in force. The original 42 execution fingerprints, proposal, launchers, frozen sources, validated translations, historical ledgers and human-QC records remain unchanged.
