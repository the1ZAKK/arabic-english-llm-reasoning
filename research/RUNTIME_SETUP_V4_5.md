# v4.5 — isolated Windows CUDA setup readiness

22 November 2026. **Preparation complete in code; installation pending separate
approval. Experiment remains NO-GO.** No laptop installation, target-library
import, model operation, training, allowance or checkpoint selection occurred.

[Use the one-file readiness launcher and review instructions](runtime_setup_v4_5/README.md).
It defaults to zero downloads/installations and produces a sanitized status plus
private deterministic installation plan. The future installer and separate
non-model qualification commands are guarded independently, not automatically run.

## Resolved evidence and compatibility limits

[Native Windows resolution 44999245610](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/44999245610)
actually downloaded and hashed all **30** binary library artifacts under CPython
**3.11.9 x64**, using official PyPI plus the exact official Torch cu126 wheel.
No resolved runtime package was installed or imported. The full marker/extra-aware
dependency closure, compatible wheel tags and Requires-Python bounds passed.
Lock SHA256: `572cfb6922df24b9eefd9f3be477ba0966238f1d70bedd68dca4e43142e7e994`.
Retained raw resolution report/index/receipt hashes and exact artifact URLs make
this a resolved binary lock, not just a list of proposed direct pins.

The ten v4.3 runtime versions remain unchanged. Two separately disclosed installer
tools, pip 25.3 and setuptools 80.9.0, have hashed PyPI wheels and replace bootstrap
versions only in the new venv. The 18 transitive pins are current resolution
choices, not evidence of the original training stack. New versions, source builds,
wrong hashes, unknown dependencies and altered runtime/destination plans stop.

Downloads total **3,017,781,239 bytes**; archive payloads total **6,962,369,294**.
The same-volume installation/cache/scratch minimum is **12,664,505,093 bytes free**
(11.79 GiB), replacing v4.3's unmeasured 20 GiB planning reserve for this lock.
This is not a measured installed footprint or a model VRAM estimate.

Static wheel inspection verified the cu126 Torch build metadata, bnb cuda126 DLL,
Qwen2/AutoModelForCausalLM/BitsAndBytesConfig, PEFT loading/state APIs and legacy
hub exception exports. The wrapper's actual imports also require Accelerate
PartialState, Transformers PreTrainedModel/deepspeed integration, safetensors and
NumPy; the later gated probe checks these without instantiating any model/head.
Wheel resolution/static source presence is **not** actual import, DLL, CUDA kernel,
producer-metadata or model compatibility. The documented bnb
[0.48.2 Windows table](https://huggingface.co/docs/bitsandbytes/v0.48.2/installation)
and [official Torch 2.8 cu126 channel](https://pytorch.org/get-started/previous-versions/#v280)
support investigating this profile; laptop behavior remains unobserved.

The owner-reported RTX 2060 Max-Q 6 GiB, driver 592.82 and 16 GiB RAM were not
remeasured here. The frozen scoring wrapper still retains hidden states and
upcasts full-vocabulary logits: ~0.58 GiB FP32 logits alone at 1,024 tokens, with
possible source/upcast overlap ~0.87 GiB. Existing v4.3 memory analysis is retained;
installation disk space does not establish NF4 fit. No token/offload/precision
fallback or second resident model is introduced into the frozen design.

## Checkpoint decision

[Authentic evidence review and explicit development-only procedure](runtime_setup_v4_5/CHECKPOINT_QUALIFICATION.md).
The retained three-epoch history and successive save/reload conventions do not
bind both saved tensor hashes. Identical adapter weight copies with different
metadata and identical head copies remain preserved, unselected and unverified
as an original run/epoch pair. No private checkpoint identity is published.

## Decision and next evidence

The package lock is resolved and hash-verified. Laptop readiness, actual
installation, native library/CUDA metadata checks, checkpoint selection/lineage
and NF4 forward fit are separate outstanding gates. Run the dry-run CMD now and
review/upload only `share_status.json`. Any later installation approval must bind
the exact lock, official sources, measured space requirement, actual base
interpreter/bootstrap and new outside-checkout destination from the private plan.
A local affirmative prompt is still required after that separate approval.

After successful authorized installation, non-model import/CUDA metadata
qualification needs separate approval. Model loading/forward fit and the frozen
96-generation/240-score experiment require later independent authorization and
runtime binding; neither old pilot20 nor diagnostic24 is reusable. No model
weights, original ArMATH data, frozen proposals/releases, retries, human QC, prior
approvals, checkpoints or main were changed. CI verifies software behavior only.

Terminal install reporting retains attempted/completed package-download counts,
per-wheel private events, failures and cancellation. It does not present an old
dry-run summary after later authorized installation. The 824-test full offline
suite passed locally; 29 v4.5 synthetic/package checks also passed after the
reporting/logging fix. [Windows/Linux source CI](https://github.com/the1ZAKK/arabic-english-llm-reasoning/actions/runs/45000468124) checks the exact
implementation commit dbd9566e0528eb31d60789782917e4ca5ebced40. Both OS jobs
must succeed before delivery; their actual results are visible in that run, and
the documentation delivery commit has its own associated CI.

The exact v4.5 setup-bundle canonical SHA256 used in private installation plans
is `426920ebad47755128b5fe65e594c601b18a418191fa2913a9d55994e76a5464`. The prepared readiness CMD SHA256 is
`89373c050cee27ee15e710c7c7027fdb9bdcde66bba20edf12962a8dfa5ef22e`.
The original v4.2 release remains
`0a3cb623a1bdebe54b5c514480bf182d22238ce9ab4a4292ddd9a03aa1bc4924`
(45 dependencies); the historical 42-fingerprint release remains
`4ab6aca826555d7e0583840a0edcefd3606d796adc9727870ab0340f6facbb85`.
All three identities were recomputed offline, with no model-library imports.
