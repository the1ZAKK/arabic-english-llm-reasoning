# v4.3 — one-file Windows investigation

Diagnosis only. No installer, model load, CUDA import probe, tensor/pickle loader,
inference, scoring, training, budget, Git update or checkpoint migration is included.
The frozen v4.1 proposal and v4.2 executor/release are unchanged.

1. Download [inspect_arabicprm_recovery_windows_v4_3.cmd](../prm_arabic_english/inspect_arabicprm_recovery_windows_v4_3.cmd) from the tested research
   commit. Keep its `.cmd` extension and double-click. It verifies its embedded
   standard-library helper before execution; no adjacent files or download needed.
2. Wait for hashing and metadata inspection. Existing Python 3.11+ is needed for
   the inspector itself; each discovered interpreter is queried separately. Nothing
   is activated, created or installed in those environments.
3. The window prints a new private report folder under Windows TEMP, named
   `ArabicPRM-runtime-recovery-v4-3-*/reports`. **Review and upload only
   `share_status.json` to ChatGPT. Keep `report_private.json` on the laptop.**
4. Keep the original/development checkouts, verified backup and overlap worksheet
   untouched. Running again creates another report, never an installation or budget.

## What the reports mean

The shareable JSON uses E/A/H/R/B identifiers for Python environments, adapters,
heads, training records and bases. It includes versions, static Torch CUDA build
metadata, installed bnb CUDA-library filenames, byte hashes/equality groups,
historical-path candidate pairs, bounded memory accounting and explicit blockers.
Private paths, arbitrary adapter config strings and package dependency records stay
in the private JSON. Use its identifier mapping locally; do not upload the entire
private report or a ZIP of historical artifacts.

`required_metadata_complete` means distributions were found on the inspected site
paths, not that DLLs import or NF4 works. Different versions from the proposed
profile are a review case, not automatically incompatible. `installation_needed`
is deliberately null until actual evidence is reviewed. No single-environment
failure establishes that packages are absent from every Python installation.

Full adapter bundle equality, identical config/weight material and head-file
equality are separate. Identical copies can resolve byte ambiguity while leaving
location choice and training lineage unresolved. Co-location, names, timestamps,
matching metrics and a previous inventory are not proof of a jointly saved epoch.
The historical saver writes adapter/head/history separately. Rejected or ambiguous
formats retain bundle/file hashes in checkpoint_failure_artifacts (X/F identifiers),
without exposing their private paths or selecting a format. Existing manifest
hash mentions are reported for scope/authenticity review, never accepted as an
automatic training-lineage or human approval. Opaque `.pt` heads are hashed and
their ZIP directory may be listed; no member or pickle is opened. Their tensor
shape remains unverified. Safetensors JSON headers are metadata, not tensor loads.

Per-user package metadata is reported separately as
`user_site_packages_excluded_by_isolation`. Python's [-I mode](https://docs.python.org/3.11/using/cmdline.html#cmdoption-I)
hides that site; finding packages there is a possible explanation of the earlier
missing-package result, not proof of the cause or a ready isolated environment.
The probe imports only stdlib [site under -S](https://docs.python.org/3.11/library/site.html)
to locate it; it does not call site.main, activate paths or execute .pth files.

## Discovery coverage and explicit paths

The default covers both known Documents checkouts and their checkpoint trees,
common/named project venvs, PEP514 registry, Python launcher/PATH, common Conda,
Poetry, pyenv-win and per-user Python locations, plus Conda's environment registry.
It reads prior v4.2 TEMP inventories and the known Skywork HF cache pointer for
base identity checks. It does not scan whole drives, follow directory junctions,
launch Store aliases, activate scripts or execute `.pth`/sitecustomize. Failed
probes and duplicate distributions remain visible; discovery is not exhaustive.

If something lies elsewhere, existing Python can run the same helper with repeated
`--repo`, `--python`, `--checkpoint-root`, `--prior-inventory` and a **new**
`--output-dir`. These are read-only scope options, not installation/execution modes.
Do not start by running the old training or evaluation scripts: they have model
operations at module top level. Do not run this tool over network shares.

## Exact evidence needed next

- Map candidate IDs to local paths privately and inspect whether duplicate copies
  are byte-identical. Do not delete either copy or automatically prefer the newest.
- For intended adapter/head pairing, provide an authentic original run/epoch record
  binding their **actual hashes**, if one exists. Otherwise identify which original
  run directory/history produced them and retain the missing cryptographic lineage
  as a limitation. Do not create a retrospective record and call it historical.
- Review the complete metadata environments before deciding to install anything.
  Preserve the historical installation. Read [the conditional plan](INSTALLATION_PLAN_NOT_APPROVED.md).
- Library import/CUDA/NF4 verification, a budgeted model-fit probe and actual
  experiment operations require their own later documented authorization. None is
  granted by this report, candidate path comparison, proposed pins or passing CI.

See [the evidence and feasibility report](../RUNTIME_RECOVERY_V4_3.md).

The adjacent [.cmd.sha256](../prm_arabic_english/inspect_arabicprm_recovery_windows_v4_3.cmd.sha256) pins the complete launcher. The report also records the actual helper source SHA256.
