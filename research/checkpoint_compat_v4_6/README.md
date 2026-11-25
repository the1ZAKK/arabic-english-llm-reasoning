# v4.6 checkpoint metadata compatibility

This is an offline, model-free extension. It neither changes nor replaces the
frozen v4.2 executor, its 45-file release, the v4.5 installation lock, or either
historical checkpoint copy. Actual GPU model fit remains unverified.

## Run one read-only Windows check

Download `research/prm_arabic_english/inspect_arabicprm_checkpoints_windows_v4_6.cmd`
from the tested research commit. Compare its complete SHA256 with the adjacent
`.cmd.sha256`. Double-click normally; no Administrator privileges are needed.
The launcher also verifies the exact embedded Python ZIP application before
executing it with the existing Python's `-I -S -B` isolation flags.

Select the **existing v4.3 `report_private.json`** in the file picker. This is the
checkpoint inventory, not the v4.5 qualification result. Cancel if the correct
inventory is unavailable; do not invent a replacement or select a different
checkpoint manually. The inventory itself is never overwritten. Its byte hash
is checked before and after inspection.

All inventoried base, adapter and head candidates are retained. Their current
bytes must match the recorded artifact fingerprints. The tool reads `.bin` and
`.pt` ZIP directory information, `byteorder`, and bounded `data.pkl` metadata.
It does **not** execute the pickle, use an Unpickler, read tensor-storage members,
create tensors, convert files, import model libraries or contact Ollama.
Hashing the complete existing files can take several minutes.

New private/sanitized reports go under:

`%LOCALAPPDATA%\ArabicPRM\checkpoint-compat-v4-6\reports\<new-id>\`

Share only the **new `share_status.json`**. Keep `report_private.json`, the input
inventory, approvals and all checkpoint/run records local. Reports cannot be
written inside either checkout, a checkpoint, an inspected Python environment,
the input report directory, or an existing destination. Nothing is installed.

## Interpret the result

| Status | Meaning |
| --- | --- |
| `checkpoint_metadata_checked_no_model_fit` | Recorded bytes were reverified and the supported metadata was inspected. Selection, historical lineage, real loading and forward fit are still pending. |
| `checkpoint_metadata_needs_review` | At least one candidate failed a byte, layout or configuration check. Preserve it; inspect the private issue locally. |
| Inspection stopped | Input/schema/output-boundary checks failed. No checkpoint is repaired or overwritten. |

Every report retains `model_operations=0`, `active_budget_created=false`,
`automatic_checkpoint_selection=null`, `training_lineage_verified=false`,
`tensor_values_loaded=false`, and `experiment_decision=NO-GO`.
An unsupported active PEFT field prevents compatibility acceptance. Unknown null
fields remain in the original config and require explicit warning review; they
are not silently deleted or converted into a claim of successful adapter loading.

The public report reveals no checkpoint hashes, private paths, source dict keys,
raw errors or arbitrary config strings. The private report records exact byte
and metadata identities, every candidate and the Qwen2 body-key namespace.
An observed `wrapped_pretrained_model` namespace requires explicit loader review;
no prefix stripping or rewriting occurs here.

## Scope of the loading primitive

`verified_head_buffers` is a separate library function for a **future separately
authorized loader**. It verifies the whole-file hash and exact metadata before
reading only the small existing reward-head slices, then rechecks the file hash.
It returns bytes and descriptors, never tensors. The inspection CLI never calls
it. It has only been exercised on synthetic archives. No real checkpoint has
been converted or loaded, and the frozen executor still rejects `.bin`-only
base-head extraction. A later executor/probe integration needs its own tests,
release identity, actual local evidence and explicit authorization.

The symbolic metadata reader accepts only known storage descriptors, ordinary
state dictionaries, passive version metadata and `_rebuild_tensor`/`v2` metadata.
It never invokes those named functions. Missing heads, wrong dimensions,
unsupported dtype/stride, conflicting storage aliases, duplicate keys/members,
compressed/mixed/traversing archives, non-little-endian storage and unsupported
pickle operations are rejected. This is a narrow compatibility reader, not a
general pickle loader or a certification of arbitrary PyTorch archives.

## Reproduce without any model operation

```text
python scripts/build_checkpoint_compat_windows_v4_6.py
python -m unittest discover -s research/prm_arabic_english -p test_checkpoint_compat_v4_6.py
python scripts/check_reproducibility.py
```

The builder reuses the existing Windows launcher shell, and packages the exact
frozen v4.3 stdlib inspector plus this extension and the pinned PEFT schema. CI
uses only fabricated checkpoint data, including native Windows CMD hash/tamper,
isolated ZIP execution, sanitized report and no-selection/no-operation checks.

## Primary implementation evidence

- [PyTorch 2.8 serialization format](https://github.com/pytorch/pytorch/blob/v2.8.0/docs/source/notes/serialization.rst)
  describes the ZIP `data.pkl`, storage and byte-order layout. Metadata inspection
  is distinct from `torch.load` and does not establish model compatibility.
- PEFT 0.18.0 tag resolves to commit
  `77daa8d3b7decf2b40238ab47e2c1bd0f26c7749`.
  [LoraConfig](https://github.com/huggingface/peft/blob/77daa8d3b7decf2b40238ab47e2c1bd0f26c7749/src/peft/tuners/lora/config.py)
  and [base config](https://github.com/huggingface/peft/blob/77daa8d3b7decf2b40238ab47e2c1bd0f26c7749/src/peft/config.py)
  were parsed statically. `peft_018_schema.json` retains the exact source SHA256s
  and annotated fields; no target library was imported to build that evidence.
- The native PEFT loader has a warning path for unknown fields. This tool
  reports that condition for explicit review; it does not automatically upgrade
  packages, filter metadata or declare an inference-compatible adapter.
