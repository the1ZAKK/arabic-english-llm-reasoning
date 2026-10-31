# Verified offline reviewer-browser results v2.2

**Decision: the software/browser verification milestone passed. Genuine human design review and separate diagnostic execution authorization remain pending.** This report is AI technical verification of public/synthetic fixtures; it is not a human assessment or a translation-quality result.

## Tested implementation and CI

Implementation commit: `f86fec853dfcca696d2b33ef2069ab14a730914a` on `research/arabicprm-v2-production`.

[Completed CI 41212959885](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/41212959885) passed:

- **477 tests on Linux**, 86.623 s; actual Chrome checks passed.
- **477 tests on Windows**, 467.797 s; actual Edge checks passed.
- Native Windows canonical package, 2,252 source fields, twelve contexts/24 exact payloads and original thirteen runtime bindings verified.
- Native Windows launcher parsing, correct/wrong-hash checks, tamper rejection and CI approval/execution guards passed.
- Scheduled-task integration and its legacy CRLF installation companion were skipped. No scheduling was performed.

Earlier failures are preserved: `e975d67` exposed Chrome narrow-layout overflow and a Windows fixture/controller transport collision; the full Windows run at `49126bf` caught browser-evidence path separators. The separate v2.2 fixes retain text/validator/source bindings and use canonical relative metadata paths. `cd4137a` additionally improved candidate/correction typography after actual screenshot inspection. The final complete run above verifies the combined changes; no tests were weakened to promote protected data or permit inference.

## Observed browser evidence

The artifact ZIPs were downloaded through GitHub, their archive digests and every inner SHA256 sum checked, and screenshots from both platforms visually inspected. Evidence is attached to the completed run as `reviewer-browser-evidence-Linux` and `reviewer-browser-evidence-Windows`, with finite 14-day retention. The committed checker, exact code commit and hashes preserve the verification/provenance after artifact expiry; future browser pixels may vary with installed browser/font versions.

| Observed browser | Actual narrow viewport / page width | Browser-report SHA256 | Artifact ZIP SHA256 |
|---|---|---|---|
| Linux / chrome 156.0.8078.47 | 390 / 375 px | `24bb75798a2fada3e21b010fb5aa6994bfc2eb3c04fc6c362c660e8535713bdc` | `34f7b2fda9af50ef71392bdb80557ebd4a0f43cf7a8bd0a8522dda1ed3bb587d` |
| Windows / MicrosoftEdge 155.0.4283.62 | 492 / 477 px | `26ae92ac2f19e34c42db35c604a89e6653625c75ef9e203f78ed34768d6eb069` | `966f351d0c670e205b396e45db026aacd1d5796406162cbd6b24e8256393b5db` |

Both platforms retained all twelve pairs/24 positions, with no overflowing controls or external page resources in these fixtures. Chrome actually used 390 CSS pixels. Edge's minimum headless window used 492 despite the requested 390; this is not phone emulation or a 390-pixel Edge claim. Candidate/correction controls used the body font at 17 px; English/math retained LTR presentation and Arabic candidates RTL.

The unchanged source-only design form exported/resumed a pending task without identity/time and blocked an incomplete approval. Public-empty blind fixtures kept missing candidates locked pending. Synthetic partial-run fixtures exercised actual browser Blob JSON construction and native file-input resume, wrong-kind rejection, fresh attestations, zero duration and unchanged-clock preservation. A numerical correction that passed browser draft-format checks was rejected by the unchanged Python validator. Original script CSP rejected an unapproved inline script. No seal, actual reviewer record or correction application was created.

The test probe suppresses the anchor's OS download action while capturing real Blob bytes. A person's Save dialog/download folder, screen-reader compatibility, comprehension, authenticated identity and genuine independence remain outside these automated checks. Fixture screenshots display explicit source-only/synthetic notices. They are not actual diagnostic outputs or training examples approved for export.

## Raw-source checkout audit

The canonical relative path keys are portable. Raw helper bytes can still differ by checkout line endings, and the checker deliberately records those actual bytes rather than silently normalize files:

| CI checkout | Raw 51-entry source-snapshot SHA256 |
|---|---|
| Linux LF | `fbb892d96e19ab5c27e08d376426a94bd72256dc096c1d2d156e119ec024aa5b` |
| Windows CRLF where allowed | `eaf5ec5438b18072a629205bcb8ba689c9d89d6c9676511aaa80a9fc69bc10ae` |

A read-only replay using the repository's Git text attributes reproduced both digests exactly. Five unprotected helper/test files explain the CRLF-only difference: `review_browser_probe_v2_2.js`, `check_review_browsers_v2_2.py`, `review_browser_driver_v2_2.py`, `test_diagnostic_assessment_v2_1.py` and `test_diagnostic_v2_1.py`. Conversion was performed in memory for this audit; no file or lock was rewritten. **Every one of the 42 frozen execution hashes remained identical.** The raw before/after preservation check is still enforced on each platform.

## Preservation and human boundary

The original plan's 2,005 historical counters remain at nine. The frozen proposal `4327d769e30fdf2324d0d8000b4c828d3d311917993987af23c98687f1e0aa6d`, execution release `4ab6aca826555d7e0583840a0edcefd3606d796adc9727870ab0340f6facbb85`, 42-file map, original launchers, source/checkpoint locks, translations and human-QC records are unchanged. The original design ZIP SHA256 remains `1ae9f61d0c9d9179f6dca3b4143f92e3b4eaef8090dbd36881fb4ce44414dd89`. No production recovery artifacts or active diagnostic budget were created in this workspace; the old20 allowance was not renewed.

Only the owned temporary loopback WebDriver control channel was used; it is separate from Ollama generation and cannot target the model port. No new inference, model/browser download, scheduled task, training, data export, Global-MGSM access, main change or human approval occurred.

Next: a qualified Arabic–English mathematics reviewer must complete the [pending human design checklist](DIAGNOSTIC24_HUMAN_DECISION_CHECKLIST_V2_2.md) and disclose exposure/conflicts, with independent outcome-review/adjudication roles arranged. The [decision package](DIAGNOSTIC24_REVIEW_READINESS_V2_2.md) retains exact experiment limits and identities. Any later execution still needs separate explicit owner consent, a valid bound budget, local protected-history/model checks and final laptop confirmation. No new execution authorization is requested or implied here. The user-reported laptop preparation is preserved as reported, not converted into a new cloud ledger replay or installed-model observation.
