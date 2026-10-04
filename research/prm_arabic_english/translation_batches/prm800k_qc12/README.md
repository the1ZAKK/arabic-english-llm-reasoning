# Frozen QC12 translation draft

This batch contains 8 train and 4 dev trajectories (136 annotated steps), inherited
from the earlier inspected source split. `source_lock.json` fixes source IDs,
problem IDs, canonical source-record hashes and complete input-queue hashes.
`translations.json` is a directly authored Codex assistant MSA draft. Exact model
version and sampling settings were not exposed; the provenance explicitly records
this limitation. No separate translation API was called. The payload and prompt
are versioned so the exact draft can be materialized again; this does not promise
that rerunning a generative model produces the same prose.

Protected source math spans and annotation markers are represented by <M0>, <M1>,
etc., numbered separately for each problem or step. Materialization restores them
verbatim and requires the ordered numeric sequence to match the source exactly.
Neutral labels stay masked, source supervision stays unchanged and translations
remain ineligible for training until researcher QC and later export validation.

The source has artifacts: train/0 contains an annotation marker and train/1 has
the malformed LaTeX command `\pod`. Both are deliberately preserved with review
notes. Other source errors are translated, not repaired. Automated checks do not
prove linguistic fidelity or mathematical annotation correctness. In particular,
human QC should review protected natural-language text inside LaTeX (the word
palindrome), meaning of repeated/increasing digits, units, and deliberate errors.

Commands from the repository root (source queues must be regenerated unchanged):

```bat
.venv\Scripts\python.exe research\prm_arabic_english\test_materialize_translation.py
.venv\Scripts\python.exe research\prm_arabic_english\materialize_translation_batch.py
.venv\Scripts\python.exe research\prm_arabic_english\render_translation_review.py --output research\prm_arabic_english\data\prm800k_staging_1000\translation_batch\arabic_draft\review.html
```

Do not rerun `--freeze` on this version: the checked-in source lock is authoritative
and refuses overwriting. Materialization also refuses existing output directories;
use `--output-dir` for a fresh replay. Its report includes translation-payload,
source-lock and review-queue hashes. Human reviewers should record identity, date,
accept/revise/reject decision and reasons per record; leave source annotations
untouched. Global-MGSM was not used. Translation/QC draft only; no training or
final Arabic evaluation was performed.

Upstream source: OpenAI PRM800K, revision
`7ecc794703b2877f63226f2477a49b34f9b25163`; source-problem content originates in
MATH. Retain upstream attribution and licensing when redistributing derivatives.
See the repository ingestion and translation-QC documents for scope and citation.
