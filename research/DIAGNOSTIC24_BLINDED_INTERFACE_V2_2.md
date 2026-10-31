# Blinded reviewer interface v2.2 — offline, unsealed drafts

This separate interface lets an Arabic–English mathematics assessor review the exact diagnostic blind queue and save or resume a draft without manually editing JSON. It changes neither the frozen experiment nor the existing assessment, comparison or adjudication validators. It has no model, budget, execution, mapping, training or corpus-update action.

**Current evidence:** the user's handoff reports successful zero-request local preparation. Its 24 observations are `not_attempted`, not Arabic translations. The actual private diagnostic files are not present in this workspace. No actual assessment or reviewer identity has been created here. The interface tests use disposable synthetic candidates or the twelve public source contexts with empty outputs.

## Give each assessor a neutral blind package

An operator or GPT can prepare this interface from **only the original `blind_review.json`**. Do not supply `report.json`, the operator HTML, `unblinding_key.json`, AI risk notes, the glossary or design examples to the primary outcome assessor before sealing. A design reviewer who has seen the policies or pilot examples must disclose that exposure; independent outcome-review and third-person adjudication roles need to be arranged separately.

The preparation tool checks the authorized research repository, unchanged tested release, exact twelve source contexts and original candidate bindings. It does not search sibling directories, read an operator bundle, query the model or activate approval. It writes a new immutable private directory:

`recovery_artifacts/diagnostic-assessment-ui-v2.2/<source-kind-code-identity>/`

| File | Purpose |
|---|---|
| `assessment.html` | Self-contained offline review form; original English context and A/B candidates, no arm mapping or AI advice |
| `assessment_PENDING.json` | Exact unchanged v2.1 schema; identity/time absent and all judgments pending |
| `blind_review.json` | Separate canonical copy of the supplied original queue |
| `SHA256SUMS.txt`, `README.txt` | Artifact hashes and short instructions; verification is not an authenticated signature |

Choose the assessor kind when preparing the package. The default is **AI**. A separate human-mode file is for the actual person who performs that assessment; it is not a way for AI to claim human review. The mode cannot be switched by the form. GPT can do this preparation from a supplied blind file, avoiding repeated terminal commands for the project owner. The developer entry point is `research/prm_arabic_english/diagnostic_assessment_ui_v2_2.py`, with `--repo-root`, `--blind-review` and optional `--assessor-kind ai|human` only. There is no operator, approval or execution flag.

Give the assessor this generated directory and neutral instructions only. Keep private identity-bearing drafts and imported assessment records out of Git. Preserve the original source and report files.

## Instructions for the actual assessor / تعليمات المقيم

1. Open `assessment.html` locally in a browser. It needs no server, installation, network or Ollama. All twelve pairs and all 24 observation positions remain visible. Missing outputs are locked pending; they are not failures of translation quality or successful translations. Available mechanically rejected text can be judged erroneous or uncertain, never promoted to faithful.
2. Read the exact English target, full field, original problem and complete reasoning. Judge each A/B output independently. Source ratings are evidence of the original annotation, not proof that the reasoning is correct. Record a separate source concern when the English itself is flawed. A faithful translation of a source error preserves that error.
3. Use `faithful`, `translation_error` or `uncertain`, with a concrete explanation. Check operations, relations, entities, intervals, grammar, mathematics, numerical fidelity and reasoning boundaries. Errors need a category and severity. Local grammar may be minor; material meaning changes are major; unusable reasoning corruption is critical. Do not force uncertain or ambiguous observations into a success label.
4. Put any correction in its own proposal field. Never replace an original candidate or silently repair the English. Browser checks cover draft format only. The unchanged Python importer must still validate Arabic, mathematical expressions, numbers, full-field splicing and boundaries before sealing; semantic correctness and independent correction approval remain human tasks.
5. When saving non-pending work, supply your actual identity and affirm blinding. Human mode also requires your personal-human-review attestation. The form records the browser's actual UTC clock; check that your device clock is accurate. Leave review seconds blank if unknown, or enter your measured duration, including zero if that is the actual measurement. Identity, clock and independence are assertions, not authenticated facts.
6. Save a separate unsealed JSON draft. Resume by selecting that exact-source saved file. Unchanged records preserve the original identity, time and duration. Saving or resuming clears the visible attestations: changed records require fresh ones. Closing the page before saving loses unsaved edits; there is no silent autosave or inference action. Keep successive drafts separately rather than overwriting evidence.
7. Return the saved JSON for the [unchanged assessment validator and sealer](DIAGNOSTIC24_ASSESSMENT_V2_1.md). Partial drafts remain partial. Every available candidate needs a decision or explicit uncertainty before any operator mapping can be read. Seal both independent assessments before comparing them. Retain unavailable observations and original judgments throughout comparison and [independent adjudication](DIAGNOSTIC24_ADJUDICATION_V2_1.md).

قيّم أمانة الترجمة العربية في السياق، لا صحة الاستدلال الإنجليزي وحدها. سجّل مشكلات المصدر مستقلة، ولا تخترع ترجمة مفقودة أو تصلح نصا مجمدا. احفظ مسودة منفصلة باسمك الفعلي؛ لا تعادل المسودة أو موافقة المقيمين اعتمادا بشريا نهائيا أو إذنا بالتنفيذ.

## Integrity, usability and limits

The exact embedded script is bound by a SHA256 content-security policy; external connections and assets are denied. Source and candidate text are escaped and cannot inject markup. English and formulas retain left-to-right presentation, while Arabic candidate/correction fields use automatic direction. The form exposes source context without disclosing which policy generated A or B. Do not use the design-review ZIP as a neutral outcome-review packet: it intentionally reveals prospective policies and examples.

Deterministic tests execute the actual embedded JavaScript through a Node DOM mock, including save/resume events, source/candidate tampering, AI/human separation, metadata, zero duration and fresh-attestation rules. A native Python subprocess denies sockets and operator-file reads. Invalid correction drafts cannot bypass the unchanged Python validator or seal. The full shared suite runs these tests on Windows and Linux; existing native Windows package/hash/mode guards remain in place. These are not a full browser-rendering, screen-reader or human-usability study. Actual browser appearance and reviewer comprehension remain to be checked locally with the supplied neutral package.

An HTML draft is editable evidence, not a seal or signature. No browser interface can authenticate who reviewed it or prove that an assessor never viewed a key elsewhere. The two-assessor comparison preserves disagreements and matching errors without granting approval. No response, correction, review consensus or AI note changes frozen data, source labels, training eligibility or the budget.

For the separate design decision, use the [standalone AI follow-up](DIAGNOSTIC24_AI_HANDOFF_REVIEW_V2_2.md), [pending human checklist](DIAGNOSTIC24_HUMAN_DECISION_CHECKLIST_V2_2.md) and unchanged [self-contained bilingual design package](DIAGNOSTIC24_DESIGN_REVIEW_V2_1.md). This interface helps prospective outcome assessment; it does not complete genuine human design review or request new execution authorization.
