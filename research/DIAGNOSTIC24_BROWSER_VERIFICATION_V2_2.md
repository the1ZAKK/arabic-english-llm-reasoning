# Native browser verification for offline review forms

This separate development check closes the gap between the existing Node DOM mocks and actual browser behavior. It uses installed Chrome/ChromeDriver on Linux and Edge/EdgeDriver on Windows, with no browser installer, Selenium Manager, model endpoint or production input. The frozen reviewer ZIP, original launchers, proposal, 42 execution fingerprints, checkpoints, translations and QC records remain unchanged.

The implementation is `prm_arabic_english/check_review_browsers_v2_2.py`. Its only options are `--browser auto|chrome|edge` and `--output-dir`. It requires a fresh evidence directory. Inside the repository, outputs are restricted to a separate `recovery_artifacts/diagnostic-browser-checks-v2.2/<new-directory>/` namespace. It cannot accept private reports, mappings, real assessment files, approvals, inference commands or training/export modes.

## What the checks exercise

| Case | Actual browser checks | Evidence boundary |
|---|---|---|
| Original source-only design form | Twelve slots/seven original problems render; pending export has no identity/time/approval; incomplete approval is blocked; native file-input resume preserves the pending task; original script CSP blocks an unauthorized inline script | No human review is performed; design decisions stay pending |
| Public empty blind form | All twelve real contexts/24 positions remain visible; unavailable outputs are locked pending; human mode exports the exact empty task; accessible control names and narrow layout are checked; desktop/narrow screenshots are captured | Synthetic zero spec, absent candidates; this is not the user's laptop report or generated translations |
| Synthetic partial-run AI form | Missing/failed/rejected observations retained; hard rejections lack a faithful option; actual Blob JSON content is captured; identity/blinding and fresh attestations required; zero duration and unchanged timestamps preserved; native saved-file resume works; wrong-kind resume is rejected; Arabic uses RTL | Disposable synthetic candidates, identities and draft judgments only; no actual AI or human outcome assessment is published |
| Mandatory Python validation | An invalid numerical correction can be saved as an unsealed browser draft, but the unchanged Python validator rejects it | Browser format checks are not semantic approval; no correction is applied or seal created |
| Preservation | Compare exact public/code hashes before and after; preserve existing evidence rather than overwrite it | No protected data, historical counters or frozen identity is migrated |

The controller uses standard-library WebDriver HTTP **only on its own newly allocated loopback port**, never the model port. It launches a fresh temporary browser profile, disables background networking and remote hostname resolution, navigates only to disposable local HTML files and closes its own driver/session afterward. The forms' original content-security policies still apply. The injected test probe captures real browser Blob contents and suppresses the anchor's OS download action; these tests do not verify a person's native Save dialog, download folder or device security. Native file-input resume is exercised with temporary fixture JSON files.

The output report distinguishes WebDriver control requests from generation: `webdriver_loopback_requests` is a browser-test count; `generation_requests_authorized` remains zero. Page resource metrics cover the page, not every background packet of an installed browser. No Ollama client, generation request, model download, scheduled task, training or corpus write is part of this check.

## Findings from the first native run

[Commit e975d67](https://github.com/the1ZAKK/arabic-english-llm-reasoning/commit/e975d67517e48b8a263ed144c88507b19d211795) / [CI 41211169902](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/41211169902) failed closed and retained screenshot evidence. Installed Chrome rendered a horizontal overflow at the narrow viewport; the separate v2.2 form now constrains control widths and fieldset sizing, without hiding text or altering source/candidate bytes. Existing generated artifacts remain immutable; the changed tool hash gives a new interface identity. The frozen design ZIP and experiment do not change.

The Windows case reached the synthetic fixture, whose global `urllib` prohibition also blocked the legitimate loopback WebDriver control request. The controller now uses a dedicated `http.client` connection fixed to its own allocated loopback port, rejects redirects/model-port routes and remains separate from the unchanged model-network prohibition. No model request caused that failure. Screenshots now return explicitly to the intended page/card region, and layout diagnostics retain overflow-control IDs. New CI must pass before these fixes are marked verified.

## CI and evidence

The shared offline workflow runs this check before the full Python suite and existing native Windows launcher/hash/mode guards. Browser failures fail the job; absent installed binaries fail closed rather than silently skip or download. The upload action is pinned to the observed official v7.0.2 commit `cf430e030ddbb5b0abf93d22962f4752f3646cd9`.

Only the dedicated fixture evidence directory is uploaded, under `reviewer-browser-evidence-Linux` or `reviewer-browser-evidence-Windows`, with 14-day retention. It contains screenshots, a machine-readable report, observed browser version/driver hash, source-snapshot identity and SHA256 sums. Temporary profiles, operator keys, private laptop provenance, actual reviewer records and saved fixture drafts are excluded. CI artifacts can expire; the committed code and source bindings reproduce the check with an installed matching browser/driver.

Local boundary/contract tests remain standard-library only. This cloud workspace has no installed browser/driver; the native entry point was observed to fail closed without creating evidence. Real-browser success and screenshots must therefore be established from completed Windows/Linux CI and visually inspected before describing the gap as resolved. The earlier 465-test milestone remains the verified baseline until those new CI checks pass.

Even successful browser tests are not an accessibility certification, human-comprehension study, translation-quality result, authenticated blinding proof or human design approval. A qualified reviewer must still inspect the [design package](DIAGNOSTIC24_DESIGN_REVIEW_V2_1.md), disclose exposure/conflicts and make an actual decision. The [decision package](DIAGNOSTIC24_REVIEW_READINESS_V2_2.md) retains the separate owner-authorization and final laptop-confirmation gates.

Implementation references: [W3C WebDriver](https://www.w3.org/TR/webdriver2/), [Microsoft's Edge capabilities](https://learn.microsoft.com/en-us/microsoft-edge/webdriver/capabilities-edge-options), [Chrome's official headless documentation](https://developer.chrome.com/docs/automation-and-testing/headless-cli) and the official [Windows](https://github.com/actions/runner-images/blob/main/images/windows/Windows2025-Readme.md) / [Linux](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md) runner inventories. Installed versions are observed during CI rather than inferred from a changing inventory page.
