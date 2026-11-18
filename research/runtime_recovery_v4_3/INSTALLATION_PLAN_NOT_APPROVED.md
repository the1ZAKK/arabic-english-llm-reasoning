# Conditional new-environment proposal — NOT APPROVED

**Do not install from this document in v4.3.** First inspect every relevant existing
environment with the new tool. An absent package in the v4.2 launcher-selected
interpreter does not establish a need for installation. Prefer investigating a
complete existing environment without mutating its packages or historical venv.

The repository has no retained historical PRM dependency lock. Root `setup.py`
registers a vLLM plugin; it does not specify this PRM environment. Ingestion's
datasets dependency is unrelated. The upstream README
server example uses vLLM0.6.4.post1; that is not this laptop runtime or a saved lock. The following is a proposed legacy-API candidate,
not the recovered historical stack, an ABI-tested installation, or an approved lock.
If recovered adapter metadata identifies a different PEFT producer or configuration,
review that before finalizing versions. Do not silently downgrade an existing env.

| Direct package | Proposed pin | Reason / authoritative source |
|---|---|---|
| Python | existing 3.11.x x64 | Matches retained project/CI convention; investigate 3.11.9 first |
| torch | 2.8.0+cu126 | Official [Windows CUDA 12.6 wheel channel](https://pytorch.org/get-started/previous-versions/#v280); explicit CUDA build, not CPU-only |
| transformers | 4.57.3 | Retain 4.x Qwen2 and legacy wrapper APIs, `dtype`/`torch_dtype`; [tagged dependency table](https://github.com/huggingface/transformers/blob/v4.57.3/src/transformers/dependency_versions_table.py) requires Torch >=2.2, hub>=0.34,<1, tokenizers>=0.22,<=0.23 |
| peft | 0.18.0 | Local LoRA CAUSAL_LM/state APIs; [tagged metadata](https://github.com/huggingface/peft/blob/v0.18.0/setup.py) allows Python>=3.10, Torch >=1.13, accelerate>=0.21, hub>=0.25 |
| bitsandbytes | 0.48.2 | [Versioned Windows build table](https://huggingface.co/docs/bitsandbytes/v0.48.2/installation) includes CUDA 12.6 and sm75; [metadata](https://github.com/bitsandbytes-foundation/bitsandbytes/blob/0.48.2/pyproject.toml) requires Torch >=2.3,<3 |
| accelerate | 1.11.0 | Required `PartialState` and device-map support; [tagged metadata](https://github.com/huggingface/accelerate/blob/v1.11.0/setup.py) requires Torch >=2, Python>=3.10 |
| huggingface-hub | 0.36.0 | Within Transformers' 0.34–<1 bound; retain legacy hub exception imports |
| tokenizers | 0.22.1 | Within the tagged Transformers range; local fast-tokenizer offsets |
| safetensors | 0.6.2 | Meets >=0.4.3 declared floor; actual future loader uses safe_open |
| numpy | 2.2.6 | Explicit direct import in unchanged io_utils; Python 3.11 wheel candidate |
| packaging | 25.0 | Satisfies declared >=20/20.9 bounds |

These direct pins satisfy the inspected declared bounds. That is **not** empirical
proof of imports, driver linkage, model loading, exact producer compatibility or
reproducible scores. No versions are selected simply because they are newest.
No vLLM, TRL, DeepSpeed, flash-attn, torchvision, torchaudio or datasets installation
is needed for the v4.2 scoring path. Do not install Linux-only extras, preview wheels,
unofficial bitsandbytes forks, a CUDA toolkit/compiler or a driver automatically.

## Proposed procedure after separate installation authorization

1. Choose an existing verified x64 Python 3.11 base; reserve a **new**, absent path
   such as LOCALAPPDATA/ArabicPRM/venvs/armath-nf4-v4-3. Never reuse either checkout's
   `.venv`, activate it globally, or change PATH/Python defaults. If the target exists,
   stop; do not replace it.
2. Before downloading or installing, approve the exact profile, official source
   indexes, disk allowance and no-model/no-fit scope. Retain the current inventory.
   Read-only metadata alone does not authenticate native wheel contents.
3. After that approval, resolve **all transitive** Windows CPython 3.11 x64 binary
   wheels from PyPI, with Torch obtained separately from the official cu126 index.
   Avoid mixing an extra index with a default index. Produce a complete resolver
   report and SHA256 wheel lock, including auxiliary dependencies, before installation.
   Reject source builds, missing wheels or changed pins. This milestone has neither
   downloaded those wheels nor produced that complete binary lock; do not call the
   direct-pin table a fully resolved requirements lock.
4. Create/install only in the new environment from the inspected wheel set; retain
   wheel hashes and install report, then check dependencies. No model weights are
   downloaded, no checkpoint is copied or changed. The later installer should be
   a separately tested, hash-pinned one-click tool with explicit confirmation.
5. Static metadata verification remains distinct from later authorized library/DLL
   imports, device/kernel capability checks and a **separately authorized** model-fit
   probe. Never run training/evaluation scripts as installation tests. Bind an actual
   compatible runtime to a later tested experiment release before model execution.

Allow **20 GiB free on the chosen installation volume** as a conservative planning
reserve for a CUDA Torch environment, binary wheel cache and installation scratch.
This is not a measured download/installed size. The complete future wheel lock must
replace it with actual sizes plus temporary-space headroom. Existing weights are
reused read-only, not budgeted as another download. The inspector reports TEMP-volume
free space; do not assume it is the proposed environment's volume.

Windows/CUDA/DLL compatibility remains a real qualification step: the reported
driver 592.82 and Turing GPU do not prove the cu126 runtime or bnb DLL can load.
Missing runtime DLLs or a CPU-only Torch build must be diagnosed without changing
the old environment. Do not use `BNB_CUDA_VERSION`, CPU offload, BF16, reduced token
limits or a new model as an automatic workaround to the frozen experiment.
