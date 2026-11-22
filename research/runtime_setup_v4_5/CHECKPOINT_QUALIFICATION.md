# Checkpoint selection remains separate and unverified

The v4.4 owner-supplied inventory reports two matching adapter tensor files with
**different metadata/README and full-bundle identities**, and two identical
reward-head files. This session cannot access those Windows paths. Both copies
remain intact. No pair is selected, merged, re-saved, deserialized or published.

The actual retained `checkpoints/arabicprm_pilot/training_history.json` contains
three epoch records and performance summaries, without adapter/head SHA256 fields.
`train_arabicprm_pilot.py` saves adapter, head, tokenizer and JSON history in
successive operations. `eval_reloaded_pilot.py` references those paths and records
reload metrics; it does not bind saved bytes to an epoch. The v4.3
`historical_source_evidence.json` pins these source conventions. Reinspection found
no contemporaneous joint hash manifest in this retained evidence. Metrics and
filenames do not prove pairing. This does not prove no private record exists.
Private laptop records have not been newly inspected by the cloud in v4.5.

For genuine lineage evidence, use the existing v4.3 read-only investigator to
retain actual A/H identifiers and hashes, then inspect original run/epoch records
for a **contemporaneous link to both exact weight hashes**. Preserve original
records and distinguish their original timestamps from later inventory times.
A later operator attestation or newly written manifest cannot retroactively
establish cryptographic training lineage. Do not upload private paths/inventories.

If no authentic binding is available, a transparent development-only choice can
still be proposed privately, without manufacturing lineage:

1. The owner identifies one existing adapter **complete metadata bundle** and one
   existing head by actual local IDs/hashes. Record both competing bundle IDs too.
   Do not combine metadata from one adapter with weights/config from the other.
2. Retain the frozen base/tokenizer identities, all selected component hashes,
   metadata producer/version fields, config contents and actual evidence used.
   Rank 8/alpha 16/q_proj,v_proj is a compatibility clue, not epoch proof.
3. After authorized library qualification, compare actual config keys against the
   locked PEFT LoraConfig fields reported by that probe. Unknown/incompatible keys
   need explicit review; do not silently remove/rewrite fields or checkpoints.
4. Record the actual choosing person's identity, actual date, reason and disclosure
   `development_only=true; training_lineage_verified=false`. No such selection,
   identity, timestamp or active record has been created by this milestone.
5. Keep every later score under the selected bundle identity and explicit uncertain
   historical pairing. Treat it as exploratory until the research decision accepts
   that limitation. Equal weight bytes alone cannot establish metadata equivalence.

A non-model import check can establish only library/API availability. Opaque head
tensor shapes, actual NF4 load/forward fit, strict head compatibility, tokenizer
step alignment and matched-scoring behavior require separate authorized probes.
No command in the installation kit loads or writes checkpoint tensors.
