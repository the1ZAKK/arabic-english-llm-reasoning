# ArabicPRM-T v2 unattended pipeline audit

## Scope and branch

Repository: `the1ZAKK/arabic-english-llm-reasoning`. Branch:
`research/arabicprm-v2-production`. GitHub access, exact remote branch and push
permission were verified before engineering work and reverified before delivery.
Starting commit: `c909dfa74643f632a0ebebf419e5b366a2698f4e`.
The default `main` was not used for code changes, merges or pushes.

This audit verifies engineering and offline behavior. **No Batch09–32 completion
by real local Qwen inference is verified here.** The Windows localhost and
checkpoint files are inaccessible from this development environment. The user
reported existing Batch09 checkpoints; their current field coverage is unknown.

## Root cause and implemented behavior

The earlier design made a small language model reconstruct fields while emitting
ordered mathematical placeholders. That exposed math, numbers and boundaries to
generation and caused repeat failures. A field exhausting retries also prevented
independent remaining work from progressing.

The new `prose-slots-v1` planner gives Ollama only bounded natural-language
fragments. Python retains exact mathematical and structural literals and inserts
validated Arabic fragments between them. The model cannot invent or reorder a
placeholder because none are supplied. Ordered math/number and whole-batch checks
remain enforced. Undelimited and malformed LaTeX, bare algebra, numeric formatting,
source errors, labels, masks and step boundaries are preserved. English inside
protected LaTeX stays with the expression; human review must assess it in context.
Seven nonlinguistic fields are copied exactly without model requests.

The actual Batch09 failure `train:6:6`, record
`prm800k_78b762b7d6f4a9d910997d77cca8942f080c90aa638d55cd0b51ca628c65bf8f`,
has source SHA256
`7ea977574ce65cec737e7107be911233cc990e6dfc4aac765c0f89d4bcb4c751`.
It now presents two prose slots to the model. Both source fractions and the
displayed expectation equation remain literal, including their original signs.
This is verified with offline regression tests; actual model output is untested.

The original `translation_checkpoint.json` is read-only and retains its exact
bytes. Valid historical entries are reused. New fields are saved separately in
`validated_fields_checkpoint.json`, bound to the original checkpoint SHA256.
An original hash-named backup is retained. Rejected historical entries remain in
the original and failure log. Saved prose fragments and attempt counters survive
interruption. A changed source, model digest, decoding setup, checkpoint binding
or conflicting validated legacy entry fails closed.

Pending fragments receive bounded retries, with individual retries after the
first small-group request. Valid sibling fragments persist independently.
Unresolved fields are logged; independent fields and batches continue. A batch
is complete only after all fields and review artifacts validate. Incomplete,
failed, interrupted and unattempted work prevents a successful exit. Existing
payloads and human decisions are never replaced. No export or training runs.

## Verified checks

`python scripts/check_reproducibility.py`: **99 tests passed** across ten
standard-library suites. The committed
[test log](audits/offline_validation_test_log.txt) and
[machine-readable audit](audits/unattended_pipeline_offline_validation.json)
record code hashes, source hashes, expected field identities and limitations.

Coverage includes actual Batch09 `train:6:6`, all 2,252 frozen fields, mutation
rejection for source math and number formatting, default request budgets, immutable
legacy bytes, partial-slot recovery, retry bounds, independent field/batch
continuation, startup/active interruption, unavailable Ollama, source/runtime
provenance, local mock HTTP schemas/truncation/thinking, concurrency locking,
immutable completed payloads, human-QC preservation and pending-QC export blocking.
Actual-source test responses operate in memory and are not corpus translations.

All 24 fresh Batch09–32 frozen-source preflights passed. Historical Batch01–08
materialization and bilingual rendering also passed in temporary directories;
pending-QC export was rejected. Syntax compilation, the legacy CLI help and
`git diff --check` passed. No frozen corpus or previous review artifact was edited.

GitHub CI for code commit `7cd2ab331a9bfc27e1cd7c029a79c68b2f8c7dc9`
passed **all 11 triggered workflows / 12 jobs**. Linux and Windows each passed
99 tests. The Windows job parsed the PowerShell launcher and executed its native
offline preflight for all 24 batches. Batch01–08 artifact checks, the remaining
batch staging workflow and the compatibility runner check passed. The
[CI evidence](audits/unattended_pipeline_ci_validation.json) records exact run
URLs, commit, branch, job and step results. No inference workflow was dispatched.

PyTorch-dependent `test_reviewed_training_data.py` and
`test_merge_reviewed_corpus.py` could not run because PyTorch is unavailable.
Model-loading, GPU inference, QLoRA and external benchmarks were not run. Actual
Qwen translation quality, speed and memory behavior on the Windows laptop remain
untested. Offline success does not certify semantic equivalence.

## Batch completion and outstanding work

All batches below passed source preflight. Their **real laptop completion and
outstanding field IDs remain unknown** until the local runner reads existing
checkpoints. The machine-readable audit catalogs every expected field and its
source hash; it does not label those fields as missing on the laptop.

| Batch | Expected fields | Source preflight | Local inference completion |
|---|---:|---|---|
| 09 | 93 | passed | unknown; existing checkpoints reported |
| 10 | 89 | passed | unknown |
| 11 | 99 | passed | unknown |
| 12 | 111 | passed | unknown |
| 13 | 87 | passed | unknown |
| 14 | 72 | passed | unknown |
| 15 | 82 | passed | unknown |
| 16 | 94 | passed | unknown |
| 17 | 104 | passed | unknown |
| 18 | 101 | passed | unknown |
| 19 | 95 | passed | unknown |
| 20 | 117 | passed | unknown |
| 21 | 86 | passed | unknown |
| 22 | 98 | passed | unknown |
| 23 | 98 | passed | unknown |
| 24 | 101 | passed | unknown |
| 25 | 82 | passed | unknown |
| 26 | 93 | passed | unknown |
| 27 | 90 | passed | unknown |
| 28 | 100 | passed | unknown |
| 29 | 100 | passed | unknown |
| 30 | 74 | passed | unknown |
| 31 | 104 | passed | unknown |
| 32 | 82 | passed | unknown |

Totals: **192 trajectories, 151 train / 41 dev, 2,060 steps, 2,252 fields**.
Every translated problem and step requires genuine bilingual review for meaning,
fluency, source errors and annotation alignment. Human QC remains pending; no
automated action marks it complete or makes a record training-eligible.

## Remaining local action

Follow [the Windows setup and execution commands](WINDOWS_BATCH09_32.md) in the
existing checkout. Run the offline preflight, then the unattended command with
Ollama running. Repeating that command safely resumes saved work.

Authoritative local evidence is `translated_drafts/preflight_latest.json`,
`resume_summary_latest.json` and `.md`, each batch's `batch_status.json`,
`field_audit.jsonl`, `failures.jsonl` and the hash-bound pending review artifacts.
These reports distinguish completed drafts from unresolved fields, artifact
failures and unattempted work, and include field IDs, source hashes, slot errors
and attempt counts. Only `ai_draft_validated_human_qc_pending` represents a complete
mechanical draft with review artifacts. Human review is a separate requirement.
