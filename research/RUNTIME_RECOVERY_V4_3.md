# v4.3 — laptop runtime recovery evidence

18 November 2026, Asia/Shanghai. Diagnosis and preparation only. No installation,
package/weight download, third-party import probe, model load, forward, generation,
scoring, training or active allowance. The final local suite passed 795 tests, including 30 recovery checks. Inspect this
source commit's own Windows/Linux CI and native CMD hash guards. Code/CI on the research branch does not
qualify the owner's laptop. [Run the one-file inspector](runtime_recovery_v4_3/README.md).

## Actual evidence and historical requirements

The owner supplied a v4.2 inspector summary: Python 3.11.9, RTX 2060 Max-Q with
**6144 MiB (6 GiB)**, approximately 16 GB RAM, driver 592.82, exact expected Qwen
digest and present Skywork/tokenizer bundles. This supersedes the earlier 4GB
hardware assumption for current planning; it is not a new cloud measurement.
Adapter/head locations are ambiguous, and packages were missing from only the
selected interpreter. The full private report, alternative environments and
actual checkpoint bytes have not been supplied to this cloud session.

[Historical source evidence](runtime_recovery_v4_3/historical_source_evidence.json)
pins the baseline sources without modifying them. `train_arabicprm_pilot.py` used
Qwen2.5-1.5B, NF4/double quantization/FP16, rank 8 q_proj/v_proj LoRA, alpha 16,
dropout 0.05, seed 42 and a separately trainable value head. Each improved save wrote
adapter, head, tokenizer and history **in successive operations**, not an atomic
hash-bound pair. The public reload result records metrics, not checkpoint hashes
or dependency versions. Co-location and metric agreement only corroborate context.
No retained historical dependency lock or checkpoint pair hash manifest was found
in the inspected reproducible repository evidence. Private records may still exist.

The scoring path actually imports Torch, NumPy, Transformers, Accelerate,
huggingface_hub, safetensors and PEFT; bitsandbytes supplies the NF4 backend and
tokenizers supplies fast offsets. Root setup.py only registers a vLLM plugin. The upstream README pins vLLM
0.6.4.post1 for its separate multi-GPU server example, not the laptop PRM stack.
The old training/evaluation files perform model operations at import time: **do
not import or run them for discovery**. Versioned inspection is standard library
only and preserves the existing v4.2 loader, newline input policy and reward head.

## What the new tool resolves, and what it cannot

- Inspect discovered Python executables with `-I -S -B`; query distribution metadata
  from explicit site paths without activation, `.pth`, sitecustomize or package
  imports. Per-user metadata is a separate nonactivated scope: isolated -I hid it
  in the earlier inspection; its existence and relevance are still unknown. Include named project venvs, registered Python, launcher/PATH, Conda and
  common user environments. Read torch/version.py through AST, not execution.
- Hash all scoped checkpoint candidates. Distinguish full adapter bundles, identical
  config/weight material, separate head bytes, and unrelated copies. Keep every
  candidate and failed inspection visible. Never choose newest or `best` by name.
- Read safetensors headers and JSON records only. Hash opaque `.pt` data and list
  ZIP directories without opening members or unpickling. Header metadata does not
  load tensors; an opaque head's tensor shape remains unverified.
- Compare previous v4.2 inventory hashes, existing manifest hash mentions and same-run
  path conventions. All are identified by evidence type; none authenticates a saved
  training epoch. No retrospective lineage statement or human attestation is created.
- Rehash discovered Skywork/tokenizer bundles against the **owner-reported** hashes;
  retain metadata-derived memory components. A matching local fingerprint is not
  proof of vendor origin or adapter/base training lineage.

After the actual shareable report, inspect which E/A/H IDs resolve the ambiguity.
If no authentic hash-bound save record exists, the precise missing evidence is an
original run/epoch log or manifest linking both actual adapter and head hashes.
If unavailable, the student must identify the original run/history privately and
keep the missing cryptographic lineage explicit; do not manufacture historical
evidence. Equal copies do not require recovery/merging/deletion. An explicit path
choice can be made later without claiming newly proved training provenance.

## 6 GiB NF4 feasibility, not a fit result

The versioned [bnb Windows table](https://huggingface.co/docs/bitsandbytes/v0.48.2/installation)
includes sm75/Turing and CUDA 12.6 builds; the RTX20 family is a plausible NF4 target.
Use FP16 compute, not an assumed BF16 path. Actual Torch/bnb binary loading, CUDA
capability and free VRAM still require separately authorized local qualification.

At batch 1 and the frozen 1,024-token ceiling, the unchanged wrapper retains all
hidden states and upcasts full 151,936-vocabulary logits to FP32:

| Component | Arithmetic estimate, not measured allocation |
|---|---|
| FP16 logits | 311,164,928 bytes (~0.290 GiB) |
| FP32 logits | 622,329,856 bytes (~0.580 GiB) |
| Possible simultaneous source/upcast logits | 933,494,784 bytes (~0.869 GiB) |
| 29 FP16 hidden states, width 1536 | 91,226,112 bytes (~0.085 GiB) |
| Ideal 1.5B all-4-bit weights | ~0.70 GiB; insufficient as total memory estimate |

Embeddings/output/head/norms are not all quantized. The tool derives separate
quantizable linear and remaining FP16 parameter lower bounds from actual tensor
headers, without loading tensors. Add double-quantization scales, LoRA state,
attention/MLP temporaries, model-loading peaks, CUDA/allocator overhead, display
usage and other processes. Roughly 3–5 GiB is a planning envelope for one resident
1.5B NF4 scoring model, **not a demonstrated peak or guarantee**. Do not sum only
the 4-bit payload and claim fit. Host 16 GB is also a shared/loading resource.

Six GiB makes the planned sequential batch 1 NF4 run more plausible than the old
4GB assumption. Ollama must release its existing resident model before PRM scoring;
no unload-generation request or hidden warm-up is authorized. Preserve one PRM
condition at a time and the original 96/240 limits. Actual forward fit remains null.

## Next decision and safety checklist

1. Run the new read-only CMD and review/upload only share_status.json. Preserve
   report_private.json and all original files. Discovery is bounded, never proof
   that every Python installation on all drives was inspected.
2. Review complete existing environment metadata before deciding any install is
   necessary. Multiple distribution versions, unknown custom paths or missing DLL
   evidence remain blockers. Do not change PATH or either original venv.
3. Resolve explicit artifact locations and assess authentic pairing/base lineage.
   Do not load a `.pt` file merely to settle a filename ambiguity.
4. Only if needed, review [the proposed isolated-environment plan](runtime_recovery_v4_3/INSTALLATION_PLAN_NOT_APPROVED.md).
   Direct pins have source/API justification, not an executed binary lock or import
   qualification. Any download/install requires separate documented consent.
5. A later import/capability check, model-fit probe and experiment execution remain
   distinct authorization scopes. The v4.1 proposal, v4.2 release, old allowances,
   historical attempts, human records, original ArMATH folds and main remain intact.

Synthetic tests cover metadata isolation, duplicate/missing distributions, copy
equivalence, changed weights, opaque heads, invalid metadata, private-path removal,
preservation, memory arithmetic, no execution modes and launcher hashes. Native
Windows CI must verify the exact CMD and reject tampering. Passing these checks
does not establish package imports, checkpoint lineage, a human label or GPU fit.
