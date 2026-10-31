# Offline comparison of sealed diagnostic assessments

This separate workflow prepares for the diagnostic's independent-review stage. It compares two recorded assessments without opening an operator report or the arm mapping. It creates no diagnostic observations, actual reviewer judgments, execution allowance, correction approval or human-QC completion. The prospective diagnostic remains unapproved and unexecuted.

The existing [assessment importer](DIAGNOSTIC24_ASSESSMENT_V2_1.md) still prepares and seals each review separately. The new `prm_arabic_english/diagnostic_review_comparison_v2_1.py` accepts two exact three-file assessment directories, each containing `assessment.json`, `blind_review.json` and `seal.json`. It verifies canonical bytes, source/context/candidate identities, assessor kind, actual supplied metadata and the existing assessment-tool seal. Both inputs must bind the exact same blind snapshot. An operator bundle or an analysis directory is rejected.

## What the comparison shows

- All twelve source-bound pairs and all twenty-four planned outputs, including missing, interrupted and unattempted replies.
- The original candidate and each assessor's unchanged label, severity, categories, explanation and separate correction proposal.
- Distinct counts for unavailable, incomplete, uncertain, label disagreement, error-detail disagreement and label agreement. Error-detail disagreement includes differing severity or error categories even when both reviewers identify a translation error.
- A full decision cross-tabulation for available outputs, its explicit denominator, jointly resolved counts and agreements. Agreement on faithful outputs is separated from agreement on erroneous outputs; neither establishes semantic truth.
- Full frozen source context and separate English-source concerns. A source concern never changes the original English, PRM800K rating, or Arabic fidelity judgment.
- Every proposed correction, including identical proposals from two reviewers, still marked as requiring independent review. Existing Arabic, mathematical, numerical and reasoning-boundary validators are re-run on the supplied assessments and corrections.

Different recorded assessor identities are required. Case, repeated internal spaces and Unicode compatibility variants cannot make the same recorded name count twice. Two asserted human records are described explicitly; a comparison containing an AI record is always labeled as including AI evidence. Names, clocks, personal-review declarations and prior blinding remain unauthenticated assertions. This tool cannot establish that two names represent different people or that either reviewer avoided the arm mapping elsewhere.

No agreement coefficient, confidence interval, efficacy estimate or automatic development-gate decision is produced. Twelve purposive pairs across seven clustered problems are insufficient to establish corpus accuracy or prompt effectiveness. Missing responses stay visible rather than disappearing from a favorable denominator.

## Separate immutable outputs

The CLI accepts only `--repo-root`, `--left-assessment` and `--right-assessment`. It has no operator/unblinding, approval, execution, reset, budget, training or export mode. Outputs are confined to:

`recovery_artifacts/diagnostic-review-comparisons-v2.1/<blind_sha256>/<comparison_sha256>/`

| File | Purpose |
|---|---|
| `comparison.html` | Self-contained readable comparison; escaped reviewer text; no scripts, network requests or remote assets |
| `comparison.json` | Bound source/candidate/assessment identities, denominators, cross-tabulation, differences and evidence limitations |
| `adjudication_PENDING.json` | Planning checklist for all candidates and correction proposals; identity/time absent and every decision pending |
| `blind_review.json`, `left_assessment.json`, `right_assessment.json`, `left_seal.json`, `right_seal.json` | Exact canonical copies of the original evidence, never replacements for it |

The pending checklist is **not an importable approval**. Actual adjudication and any future correction-import tooling require a separate reviewed workflow; this milestone does not manufacture their completion. Agreement never inserts a candidate or correction into a checkpoint or training corpus. Human QC and training eligibility remain pending/false, and generation authorization remains zero.

The subsequent [separate adjudication workflow](DIAGNOSTIC24_ADJUDICATION_V2_1.md) now prepares a distinct strict schema and imports actually supplied third-person human judgments. This original checklist stays a planning artifact and is not silently activated. Neither workflow applies corrections, grants corpus approval or authorizes requests.

Re-running identical inputs verifies the existing directory. Changed or additional output files block reuse without being overwritten. Original inputs, assessment directories, protected history and diagnostic ledger/guard roots are checked before and after processing. Portable assessment seals are consistency evidence, not device authentication or a replay of the private laptop reservation ledger.

## Use after eventual authorized generation

Keep operator results and the unblinding key away from assessors. First have each assessor review the same original `blind_review.json`, then validate and seal each assessment using the existing importer. GPT can process the two sealed bundles and produce the comparison without additional terminal work by the user. AI reviews stay AI; independent bilingual human review remains a separate actual action.

Inspect disagreements, uncertainty, missing responses, source concerns and every correction proposal before any scientific decision. Preserve both original records during independent adjudication. If a partial experiment has already been unblinded, the same assessor must not claim later resumed outputs were assessed blind. This comparison does not renew the exhausted pilot20, authorize diagnostic24, or change the existing preparation launcher and execution-release identities.

## Verification scope

Deterministic tests use disposable synthetic identities and decisions. They check reviewer duplication, AI/human separation, missing-output denominators, label/severity disagreements, error agreements, correction validation, source-label separation, seal/source/candidate tampering, immutable resume, input races, HTML escaping and unsupported CLI modes. A native CLI subprocess on Windows and Linux reconstructs the twelve real frozen source contexts as empty outputs, denies socket access, preserves a synthetic nine-attempt checkpoint and verifies idempotent comparison. These checks establish software behavior only; no actual diagnostic or human-QC results are created.

The shared suite now contains **381 tests**, including **23 new comparison tests**. The full local suite passed in 62.194 seconds; the final focused comparison suite passed separately. Per-commit Windows/Linux evidence is recorded by [Offline research checks](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/workflows/offline-checks.yml), including the existing native Windows package/hash and authorization-mode guards. Scheduled-task integration remains excluded from the default workflow. HTML checks parse its structure and escaping; they do not establish real browser rendering or semantic translation quality.
