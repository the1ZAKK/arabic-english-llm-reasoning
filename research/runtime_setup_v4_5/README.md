# Windows CUDA environment preparation v4.5

**Installation NOT APPROVED. Experiment remains NO-GO.** This kit prepares a new
CPython 3.11.9 x64 environment, preserving Python 3.13, both Git checkouts, all
model/checkpoint files and every research allowance. No model is downloaded or
loaded. Successful software CI does not demonstrate a GPU forward fit.

## Run now: one zero-download readiness launcher

Download `research/prm_arabic_english/prepare_arabicprm_cuda_windows_v4_5.cmd` from
the pinned verified research commit and double-click it. The complete small code
capsule and wheel lock are embedded, SHA256 verified before execution; it does not
download code or packages. It uses standard-library-only discovery and isolated
`-I -S -B` queries of an existing base interpreter. No environment is activated.
It must find **existing Windows CPython 3.11.9 x64**; it never installs Python.

The proposed absent destination is:
`%LOCALAPPDATA%\ArabicPRM\venvs\armath-cuda-v4-5`.
The separate absent wheel cache is under `%LOCALAPPDATA%\ArabicPRM\wheel-cache\v4-5`.
Both must share one volume, be outside Git and have no symlink/reparse traversal.
An existing destination/cache is a blocker, never an invitation to repair it.

Readiness creates only a new report directory under
`%LOCALAPPDATA%\ArabicPRM\runtime-setup-v4-5\reports\<unique-id>`:

- `share_status.json`: review then upload **only this sanitized file** to ChatGPT.
  It contains the exact plan hash when ready, available disk bytes and a safe
  blocker code when attention is required; it contains no private paths.
- `report_private.json`: exact local interpreter/bootstrap hashes, destination,
  complete package plan and any blockers. Keep this local.
- `installation_request_PENDING.json`, only when ready: **approved=false**, no
  identity or timestamp. This is a review request, not installation permission.

Repeated dry-runs create independent reports; they never update either checkout,
old environments, caches, model state, requests, ledgers or checkpoint contents.
No local runtime/hardware inspection is claimed by cloud testing.

## Pinned delivery identity

[Download the exact readiness CMD](https://raw.githubusercontent.com/the1ZAKK/arabic-english-llm-reasoning/5ee303a23cf264155f042a0e8f39c3eb9b953a22/research/prm_arabic_english/prepare_arabicprm_cuda_windows_v4_5.cmd)
(425,048 bytes). Save with the `.cmd` extension. Its complete-file SHA256 is:

`82e3f3669d83f01c958f7d85464f2d19875f12c362c482e98c406a8932be1af8`

The [source CI](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/45002207525)
covers 825 offline tests on each OS, native Windows CMD/hash/tamper/CI guards,
legacy protected-release checks and original ArMATH byte verification. Both jobs
must pass before final delivery. Source checks do not qualify laptop libraries.
Later documentation commits do not change this pinned command or its wheel lock.
The CMD exposes **dry-run only**; no arguments are forwarded into installation.

## Actual resolved package lock

Native Windows CPython 3.11.9 resolution/download/hash job:
[44999245610](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/44999245610),
source [1ddc085](https://github.com/the1ZAKK/arabic-english-llm-reasoning/commit/1ddc085297b9c03c7f4d2a8c8ca41f03b3833b91).
It installed/imported **none** of the resolved runtime packages.

Lock SHA256: `572cfb6922df24b9eefd9f3be477ba0966238f1d70bedd68dca4e43142e7e994`.

| Quantity | Measured or calculated bytes |
|---|---:|
| 30 actual binary wheels downloaded and SHA256 verified | 3,017,781,239 (2.81 GiB) |
| Sum of uncompressed ZIP member payloads | 6,962,369,294 (6.48 GiB) |
| Minimum free space, same-volume cache/environment/scratch | 12,664,505,093 (11.79 GiB) |

Space policy is compressed downloads + uncompressed archive payloads + the larger
of 2 GiB or 25% payload + 512 MiB bootstrap/log reserve. This is a conservative
installation plan, **not a measured installed footprint** or model-memory budget.
No model weights are included. Free space is rechecked before and after consent.

| Runtime package | Locked version | Actual wheel tag |
|---|---|---|
| accelerate | 1.11.0 | py3-none-any |
| bitsandbytes | 0.48.2 | py3-none-win_amd64 |
| huggingface-hub | 0.36.0 | py3-none-any |
| numpy | 2.2.6 | cp311-cp311-win_amd64 |
| packaging | 25.0 | py3-none-any |
| peft | 0.18.0 | py3-none-any |
| safetensors | 0.6.2 | cp38-abi3-win_amd64 |
| tokenizers | 0.22.1 | cp39-abi3-win_amd64 |
| torch | 2.8.0+cu126 | cp311-cp311-win_amd64 |
| transformers | 4.57.3 | py3-none-any |

The ten runtime pins are unchanged from v4.3. Pip 25.3 and setuptools 80.9.0 are
explicit installation-tool additions to replace ensurepip's bootstrap packages
inside the **new** venv only. The remaining 18 versions are a complete, actually
resolved, marker-aware transitive closure, now pinned in `requirements.lock`.
See `wheel_lock.json` for every exact official URL, wheel tag, Requires-Python,
Requires-Dist, SHA256, compressed size and archive payload size. This is a current
candidate lock, not a recovered historical training environment.

Torch is exactly the cp311/cp311/win_amd64 cu126 wheel selected from the official
PyTorch index, whose link points to `download-r2.pytorch.org`. All other artifacts
are official PyPI files at `files.pythonhosted.org`. No mixed extra-index, source
build, substitute version, unofficial bnb fork, compiler, CUDA toolkit, driver,
vLLM, TRL, torchvision, torchaudio, datasets or model installation is included.
`resolver_report.json`, `resolver.log`, `torch_index.html` and the resolution
receipt preserve actual CI evidence, not a synthetic reconstruction of a run.
`resolver_profile_input.json` retains the exact Windows CRLF-materialized profile
identity from that run (SHA checked); `profile.json` has identical JSON content.
Binary wheels were temporary CI inputs; they are not committed or represented as
a permanently stored wheel archive. Re-downloads must match every locked hash.

## Later installation: requires a separate decision

Review the actual laptop report, exact lock, sources, base interpreter identity,
destination and free-space plan first. This directive did **not** approve installing.
The prepared `runtime_setup_v4_5.py --mode install` path requires a separately
provided actual approval, bound to the exact deterministic private plan and scope
`installation`, and then an exact local affirmative prompt. The readiness CMD
passes no install arguments and cannot automatically activate that mode.
No approved file or invented approver/time is shipped.

After later authorization only: download these 30 wheels to the new cache, verify
all bytes, create a new venv using the hashed existing CPython bootstrap, install
from that cache with `--no-index --no-deps --require-hashes --only-binary=:all:`,
then check dependencies and exact package set. No dependency re-resolution occurs
on the laptop. Pip logs, install report, actual approval, an installed-file hash
manifest and installation receipt remain private. The sanitized terminal summary
records successful/cancelled/failed status and actual package-download attempts
and completions; it never retains a stale zero-download dry-run status. The full environment identity
includes installed file bytes; it is distinct from upstream wheel hashes.
Cancellation creates neither cache nor venv and makes zero downloads. Failed
installation preserves any partial **new** cache/env and a failure report; there
is no automatic cleanup, retry, reuse or modification of an existing environment.
A changed destination requires a new reviewed plan/approval, not a silent retry.
There are no PATH/default-Python/registry changes or scheduled tasks.

## Separate library qualification, no model test

A later `--mode qualify` requires the original successful installation receipt,
unchanged installed-file manifest, separate scope `non_model_imports_cuda_metadata`,
and another local confirmation. It imports only the locked libraries and exact
frozen legacy wrapper source capsule, checks actual versions, Torch CUDA build,
device properties/compute capability, Torch architectures, bnb CUDA DLL identity
and required Transformers/PEFT/hub/legacy signatures. It rechecks the hashed base
CPython bootstrap before and after probing, confirms the actual child Python
identity, and checks environment bytes again afterward. A base Python update
invalidates qualification even if all files inside the venv still match. Network/model-file access is blocked in the probe. No wrapper,
head, tokenizer or model is instantiated, and no tensor/kernel/forward/trace
scoring is requested. Native CUDA DLL imports are **not** a tested NF4 operation.
The result remains `model_fit_demonstrated=false`, with no experiment approval.
CI blocks both real install and qualification modes, including the direct probe.

Checkpoint metadata/lineage must be settled separately. See
[checkpoint qualification](CHECKPOINT_QUALIFICATION.md). Neither installation nor
library imports authorize model loading, fit probes, 96 generations, 240 scoring
cells, older pilot budgets, training or export.
