# ArabicPRM-T v4.4 — runtime compatibility and checkpoint qualification

**18 November 2026.** Offline evidence assessment only. **Experiment decision: NO-GO.** The owner supplied a local v4.3 runtime-recovery private inventory for analysis. This public report deliberately excludes local usernames, directories, private package inventories, checkpoint SHA256 identities, original report bodies, and correspondence. It does **not** publish the private report or transform its claims into independent machine inspection by this repository.

## Evidence and compatibility decision

The v4.3 read-only inventory describes three discovered CPython installations. The Python 3.11 and 3.14 installations did not expose the required PRM dependency stack. The Python 3.13 installation did enumerate Torch 2.12.0, Transformers 5.9.0, PEFT 0.19.1, bitsandbytes 0.49.2, Accelerate 1.13.0, safetensors 0.7.0 and tokenizers 0.22.2. Its statically inspected Torch build string was **2.12.0+cpu**, and the CUDA field was null. The inspector did **not** import these packages or perform a CUDA or model forward probe.

Accordingly **an installed Python PRM stack is not an authorized, compatible CUDA/NF4 runtime**. Its Transformers major version is also outside the v4.3 proposed legacy-API candidate (4.57.3). Discovered package metadata alone does not validate actual import compatibility, CUDA DLL linkage, quantization kernels, tokenizer offsets or model forward behavior. The historical PRM environment was not recovered as an exact version lock. A new isolated Python 3.11 x64 environment with the conditional v4.3 proposal is a **candidate recovery strategy**, not an approved or installed solution.

## Checkpoint evidence

The private inventory lists two adapter candidates whose **adapter model tensor-file bytes agree**, but whose adapter metadata and README bytes differ; therefore their **complete adapter bundles are not byte-identical**. Both have LoRA rank 8, alpha 16 and q_proj/v_proj targets in their metadata. It also lists two **byte-identical** saved reward-head candidates. Historical training-history records and co-location/path conventions exist. Their presence provides circumstantial context, **not a contemporaneous hash-bound run/epoch manifest joining the precise adapter and reward-head files**. No pair has authenticated training lineage. Do not merge the adapter bundles, automatically select one, deserialize the opaque .pt head for static assessment, or delete copies.

Original training-save code recorded components successively, rather than committing an atomic adapter-plus-head hash manifest. The pairing decision requires either authentic contemporaneous run/epoch evidence identifying both saved files, or an explicit operator-selected development-only candidate with **unverified provenance** disclosed in every subsequent analysis. The latter must not be described as verification of the original training lineage.

## Hardware and scientific boundaries

The earlier laptop inspection reported an NVIDIA RTX 2060 Max-Q with **6 GiB VRAM**, approximately 16 GiB system RAM and driver 592.82. The frozen scoring wrapper retains complete hidden states and full-vocabulary logits: at 1,024 tokens the FP32 output logits alone were estimated at approximately 0.58 GiB, with other allocations additional. A six-GiB GPU is a plausible *candidate* for sequential batch-1 NF4 scoring, but the available evidence does **not** demonstrate that the saved base-plus-reward-head configuration loads, computes correct aligned rewards or fits memory.

No new Arabic-native inference, PRM scoring, training, hardware fit probe, package install, model download or budget activation was performed. Existing v4.1/v4.2 experiment allowances remain unapproved. The 11 technical answer keys are not independent human validations.

## Minimum path to a qualified runtime

1. Preserve the source and private v4.3 inventory unchanged. Retain both adapter bundles and reward-head copies, recording the difference between equal model weights and differing metadata. Do not publish the private report.
2. Before changing any installed environment, verify the proposed **new isolated Python 3.11** install profile against the v4.3 [conditional installation plan](runtime_recovery_v4_3/INSTALLATION_PLAN_NOT_APPROVED.md): official Windows CUDA PyTorch wheel, compatible Transformers 4.x/PEFT/bitsandbytes, exact wheel hashes, complete transitive binary-wheel lock, and sufficient disk space. Check the adapter producer configuration before finalizing the pins.
3. Obtain **separate explicit permission** for the specific environment creation, downloads, exact destination, package sources and disk allocation. Never overwrite a project venv or historical environment; reject source builds or unexpected wheel/version substitutions.
4. Following installation authorization, gather a fresh sanitized environment inventory. Separately authorize only read-only/non-model library import and CUDA DLL capability tests. If incompatible, stop with observed diagnostics and do not alter the frozen model experiment.
5. Seek genuine saved-run pairing evidence. If unavailable, make a versioned **development-only uncertain-lineage** artifact selection without claiming a verified original checkpoint pairing.
6. Only after runtime, checkpoint identities, and privacy controls are bound may a separately scoped **single forward-fit qualification** be proposed. That test would consume a specifically authorized model operation and cannot be treated as free or implied by a read-only check. If fit fails, stop; do not quietly change precision, device, token limits, batch configuration, or use CPU offload.
7. The full 96-generation/240-scoring-cell experiment remains separately gated, with the prior frozen design and no retries/refunds. Independent Arabic mathematical step/final judgments and bilingual fidelity assessment remain prerequisites for corresponding scientific claims.

## Explicit v4.4 status

- **Static environment inventory interpreted:** yes, using owner-supplied private v4.3 evidence.
- **Compatible GPU runtime verified:** no.
- **Exact historical dependency lock established:** no.
- **Matching saved adapter weights / reward-head copies observed:** yes, with different adapter bundle metadata.
- **Authentic adapter+head training-run linkage verified:** no.
- **CUDA NF4 model forward fit verified:** no.
- **Full experiment approval or model performance observations:** none.

**Decision: NO-GO.** This report is a qualification assessment, **not successful machine recovery or an executed experimental milestone**. Later work must collect actual evidence before changing that status.
