# Reproducibility guide

## Offline checks — start here

Use Python 3.11. These selected existing tests use the standard library and temporary fixtures; no model download, API key or GPU is required.

```bash
git clone https://github.com/the1ZAKK/arabic-english-llm-reasoning.git
cd arabic-english-llm-reasoning
python scripts/check_reproducibility.py
```

The runner explicitly selects six suites covering PRM800K ingestion, translation batches, materialization, authorized normalization, reviewed exports and source quarantine. It does not run every research test: some require PyTorch or other dependencies. GitHub Actions runs the same offline command on Python 3.11.

## Choose the appropriate execution layer

| Layer | Requirements | Scope |
| --- | --- | --- |
| Offline fixture checks | Python 3.11 standard library | Data conversion, review boundaries and quarantine behavior |
| Source ingestion | Existing ingestion scripts; optional packages in `research/prm_arabic_english/requirements-ingestion.txt` | Follow the source revision, split policy and upstream dataset terms in research documentation |
| API evaluation | Script-specific dependencies, service credentials and model access | External calls can incur costs; record model/version, prompt, settings and raw outputs |
| PRM inference or LoRA/QLoRA training | Script-specific PyTorch/Transformers/vLLM/PEFT stack, model weights and suitable hardware | Record package versions, GPU, precision, seeds, model revision and command |

Root `setup.py` registers a vLLM plugin. Installing it alone does **not** install the complete research environment. There is no single verified lockfile for all execution layers.

## Preserve research provenance

- Use the existing documented source revisions and held-out split rules.
- Keep rejected, quarantined, provisional and accepted records distinct.
- Never regenerate accepted corpus artifacts in place as a quick smoke test.
- Record the repository commit, input checksums, exact command, Python/package versions, model revision and output directory for each run.
- For API experiments, also record provider, model identifier, sampling settings, date, retries and errors without publishing credentials.
- Report pilot results with their existing sample sizes and limitations. Passing offline checks does not reproduce benchmark scores or certify a trained model.

Existing README results and research review records remain the authoritative experiment descriptions. See the files under `research/prm_arabic_english/` for individual workflows.

## Environment hygiene

Keep credentials in local environment configuration and do not commit `.env` files. Commit a sanitized example only when needed. Store checkpoints, caches and temporary runs outside tracked result directories.

