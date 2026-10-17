# Batch10 rejected-output root-cause investigation

Evidence: user-supplied local `translated_drafts/prm800k_v2_batch10/failures.jsonl`, analyzed without modifying it. This is a historical log, not a new inference run. No source records or verbatim sensitive draft payloads are committed here.

## Findings

- 1,042 logged events: 824 `translation_attempt_failed` entries classified as "Unexpected script or control/line boundary in prose slot", 188 `field_unresolved`, and 30 translation attempts recording localhost Ollama connection refusal (`WinError 10061`).
- Of those **824 script/boundary rejections**: **814** contained ASCII-only English draft outputs, **9** contained both Arabic and Latin script, and **1** contained Arabic plus Cyrillic characters.
- Representative rejected ASCII-only draft: `What is the smallest whole number` (source unchanged). This is a model output failure, not an over-strict Arabic validator.
- The transport connection-refusal events must be kept separate from translation quality events. The existing transport outage fix remains appropriate for future runs but cannot refund historical attempts.
- Failure event counts represent attempted prose slots, *not* unique outstanding fields; the latest historical aggregate remains 1,075/2,252 validated fields across Batch09–32.
- A preliminary stricter prompt experiment was reverted when the full offline suite failed. No validated runtime change is authorized by this report.

## Safe recovery design (not yet authorized)

1. Preserve all source queues, source locks, completed translation fields, attempt ledgers, and QC records byte-for-byte.
2. Prepare offline targeted tests of the complete Ollama request/response contract on representative synthetic English-echo, mixed-Latin, and Cyrillic outputs. Reject them without weakening `validate_slot`.
3. Develop **a separate, consent-gated recovery generation** for exhausted slots: versioned prompt/provenance, explicit hard caps, new append-only attempt ledger, never changing prior counters; no automatic inference on install.
4. Reassemble only fully validated fields using the existing source-owned math and ordered checkpoint validation, and keep human QC pending.
5. Run Linux and Windows tests and require approval before any local model requests. Do not export unreviewed training data, train, or access Global-MGSM.

**Do not** reset `state.json`, increase old `max_total_attempts_per_slot`, override failed drafts, or turn `completed_with_unresolved` into a non-terminal state by editing the saved state.
