# v4.2 — controlled experiment readiness

18 November 2026. Offline engineering only; no model loads, inference, scoring,
model downloads, active approval or budget. The frozen v4.1 proposal remains
`da757e5b75c1c0ee9d7b1687ed26b8c50192cfc5cb56c89fe532e484316952cf`.
All original data, prior source/attempt/checkpoint/human records and main are unchanged.

## Versioned mathematical decision

[Reference evidence](armath_readiness_v4_2/reference_decisions.json) and
`armath_references_v4_2.py` independently derive the seven previously pending
answers from exact original Arabic questions before comparing the source equation.
They bind original question/equation/record hashes; no source is corrected.
These are AI technical checks, not developer-submitted or independent human judgments.

| Problem suffix | Question-derived exact result | Decision |
|---|---|---|
| fold0:0078 | 240 riyals total; 60 each only with equal sharing | Conditional; excluded because equal sharing is implicit |
| fold0:0832 | First book 20 riyals, second 12; sum32/difference8 | Technical development key |
| fold1:0152 | 640 cans/second ×60 =38400 cans/minute | Technical development key |
| fold2:0622 | Equal legs35; 35+35+40=110 and70>40 | Technical key; no invented length unit |
| fold2:0798 | 3−(6×400/1000)=3/5 litre | Technical key; leftover, not bowl capacity |
| fold2:0836 | 26−(2×10+5)=1 riyal short | Technical development key |
| fold4:0735 | Side78/4=19.5 mm; area1521/4 mm² | Technical key; squared units retained |

Together with five unchanged complete-question checks, there are **11 technical
reference keys, one conditional exclusion, zero independent human validations and
zero benchmark-eligible problems**. This supports a prospective development
numeric proxy, not a human-validated native benchmark. Resolve/screen the selected
references with qualified people before defensible human accuracy claims. No full
6,000-record review is imposed. Source-declared novel is not authenticated authorship;
twelve exposed cases/eight legacy components are not an independent held-out sample.

## Actual local runtime evidence

This cloud computer cannot read the owner's Windows filesystem, Ollama or GPU.
No fresh laptop model, checkpoint, library or hardware availability is claimed.
Use [the standalone read-only CMD](prm_arabic_english/inspect_armath_runtime_windows_v4_2.cmd)
or [the Python inspector](prm_arabic_english/armath_inspect_v4_2.py). The CMD embeds
and SHA256-checks its Python payload, selects an existing Python3.11+ (preferring
existing project .venv interpreters), and installs/downloads nothing. It does not
update Git, load model tensors, run generation/scoring or create consent/budgets.

The inspector only reads explicit/default local artifact/cache paths. It hashes
base/tokenizer/adapter/reward-head bytes and Ollama manifest/blob bytes, obtains
loopback version/tags/ps/show metadata, records installed packages and RAM, and
uses a separate installed-library process for Torch/CUDA/bitsandbytes capability
inspection without model loads/tensors/forwards. It reads nvidia-smi driver/VRAM
metadata. Only new private temporary report files are written. A custom cache can
be specified using --base / --adapter / --reward-head / --ollama-models-dir; missing
or ambiguous paths are reported, not downloaded or repaired. No legacy dirty
checkout, backup, private overlap worksheet or model/checkpoint is modified.

Double-click the CMD. It prints its private report directory. Review and share
**share_status.json only**; keep report_private.json private because it contains
local paths and full metadata. A successful prerequisite inventory still does not
prove a real NF4 forward fits GPU memory. Required generator digest remains
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
The actual PRM/tokenizer/head/adapter/runtime hashes remain unknown until real local
inspection. No values are invented in the cloud.

## Executor milestone

Guarded executor implementation and synthetic validation are the next active
engineering task. The proposed limits remain **96 one-shot Arabic generation
requests ×512 generated tokens, 240 one-shot matched NF4 scoring cells ×1024 input
tokens**. Old pilot20/diagnostic24 approvals cannot authorize this experiment.
No active approval will be created during development. Runtime fit, faithful
English mirrors, independent Arabic step/final judgments and separate explicit
execution authorization remain genuine dependencies.

Hardware references checked on 18 November 2026:
[bitsandbytes installation requirements](https://huggingface.co/docs/bitsandbytes/installation)
and [Ollama generation metadata](https://docs.ollama.com/api/generate).
Current bitsandbytes support is version/build dependent. A reported RTX2060/4GB
is not evidence of an installed compatible backend or enough free VRAM. The
retained full-logit wrapper's memory cost discussed in v4.1 remains relevant.
