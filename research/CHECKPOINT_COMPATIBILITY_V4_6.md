# v4.6 — checkpoint compatibility, model-free preparation

26 November 2026. The owner's uploaded sanitized reports record successful
installation (`installed_not_qualified`) followed by
`libraries_cuda_metadata_qualified_no_model_fit`; both record zero model
operations. The completed model-free qualification is not rerun. These are
owner-supplied local results, not observations of the laptop by the cloud.
The historical v4.3 missing-dependency flags do not describe the new environment.

## Evidence reviewed and exact limitation

The uploaded private v4.3 inventory reproduces its sanitized summary exactly,
and its inspector-source hash matches the retained source. Two adapter copies
have identical weight bytes and equivalent parsed config values, with different
raw metadata/full-bundle identities. Both head copies have identical bytes.
The histories have equivalent values. No inspected authentic record joins the
adapter and head weight hashes to the original save/epoch. Neither copy was
selected, combined, altered, deserialized or uploaded.

The inventory lists a `.bin` base with no safetensors file. The frozen v4.2
backend's pretrained-head extraction accepts only safetensors. Consequently,
successful library/CUDA qualification alone cannot make that executor ready.
Whether the `.bin` contains the required head shapes and compatible body-key
namespace remains to be observed on the laptop. No absent head is inferred from
an opaque file, and no random replacement head is permitted.

The configs declare producer PEFT 0.21.2, while the resolved environment uses
0.18.0. Static comparison against the pinned 0.18.0 implementation finds five
extra null fields: `kasa_config`, `lora_ga_config`, `monteclora_config`,
`use_bdlora`, `velora_config`. This does not prove a failed load or a compatible
load. Their original bytes remain unchanged; warning behavior needs explicit
review before a later loader uses them.

## Implemented safe improvement

[The practical Windows check](checkpoint_compat_v4_6/README.md) reuses the existing
inventory and stdlib fingerprint implementation. It adds bounded, nonexecuting
PyTorch ZIP metadata interpretation, exact reward-head layout/storage checks,
body-key namespace reporting and PEFT schema comparison. A separately callable
verified-head-byte primitive is tested for future integration; it creates no
tensors and is never invoked by the diagnosis CLI.

All candidates, unsupported cases and byte mismatches remain visible. A fresh
outside-checkout report is the only local write. There is no install, model
execution, format conversion, checkpoint selection, active budget, repair or
rewrite path. The old executor, proposal, installation profile, launchers and
protected data are unchanged. The new report always retains experiment NO-GO.

The tests use fabricated state dictionaries and byte arrays, including metadata
written by Python Pickler protocols 2–5 with fake storage/tensor descriptors.
No Torch/PEFT import or tensor is needed. Native Windows launcher checks exercise
payload/hash rejection and synthetic-only execution; Linux checks execute the
same isolated ZIP application. Actual checkpoint/GPU compatibility is not a CI
result. Inspect the exact delivery commit's Actions results before using the CMD.

Local validation after the packaging correction: **860 offline tests passed**, including 35 new metadata,
immutability, isolated-package and guard regressions. The full local run took
78.690 seconds. Windows/Linux Actions, including the new native Windows CMD
check, remain the delivery gate; these local results do not substitute for them.

The initial [505f01d CI run](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/45684722034)
passed all 859 Linux tests and native Windows CMD guards, but Windows failed one
of 859 tests: reproducible ZIP packaging. Windows's default ZIP creator-system
byte differed from Linux's. The builder now sets that field explicitly to 3;
the delivered CMD's bytes and SHA256 are unchanged. A new cross-host regression
reproduced the exact failure before the fix and passes after it. No byte-exact
comparison or payload guard was relaxed. The corrected source requires its own
Windows/Linux CI before delivery; the failed run remains preserved as evidence.

## Next bounded model-fit proposal — inactive, not an approval

The next local action is the single metadata check. If its results support
continuing, the owner must explicitly choose one complete adapter bundle and
head, retain the alternatives, and disclose `development_only=true` and
`training_lineage_verified=false` unless authentic lineage evidence is found.
The private selection must bind actual hashes, identity/date and the original
evidence; AI does not create that selection.

Only after the actual metadata/config/body-namespace issues are resolved should
a separate probe release be prepared for review. A reasonable proposed bound is
two condition loads (one base and one adapted condition, each including its
required checkpoint reads) and four forward passes total: 32- and 1,024-token
synthetic input once per condition, batch one, NF4/FP16, no offload or fallback.
All component reads must be disclosed; these are not merely two file loads.
Stop on a failure, cancellation, mismatch or OOM; no hidden retry/warm-up.
Report actual input/weight/runtime hashes, strict head/adapter loading results,
output shapes/finiteness and measured peak VRAM, retaining private paths locally.
This is a proposed resource scope, not an implemented fit runner or an allowance.

That probe requires separate explicit model-loading/forward authorization and
final local confirmation. It must not reuse the installation or model-free
qualification consent, exhausted pilot20, inactive diagnostic24, or the unapproved
96-generation/240-score proposal. No real problem responses, candidate scoring,
training, model download, exported dataset or scientific accuracy result is part
of this milestone. Genuine human mathematical/step judgments remain separate.
