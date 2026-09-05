# Arabic-English and Moroccan Darija Mathematical Reasoning in LLMs

This repository contains experiments investigating language-associated differences in mathematical reasoning and process-reward evaluation across English, Modern Standard Arabic (MSA), and Moroccan Darija.

The project studies whether mathematically equivalent problems receive comparable reasoning performance across languages, how these differences vary across model families and model capabilities, and whether process reward models (PRMs) evaluate Arabic reasoning as reliably as English reasoning.

## Research Questions

The project investigates four main questions:

1. Do process reward models distinguish correct and incorrect mathematical reasoning equally well in Arabic and English?
2. Do generative language models achieve comparable mathematical reasoning accuracy on matched Arabic-English problems?
3. Does the size of the language-associated performance gap change across model families and stronger models?
4. How robust is mathematical reasoning in Moroccan Darija, a lower-resource and non-standardized Arabic variety?

## Experiments

### 1. Arabic-English Process Reward Evaluation

Model:

`Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B`

A controlled 20-problem experiment compared PRM scores for correct and deliberately incorrect reasoning responses in Arabic and English.

The tested PRM showed substantially stronger discrimination between correct and incorrect reasoning in English than in Arabic.

Files:

`research/prm_arabic_english/`

### 2. Generative Reasoning Pilots

Two smaller generative models were evaluated on matched Arabic-English arithmetic problems:

- Qwen2.5-Math-1.5B-Instruct
- Gemma-3-1B-it

Both models achieved higher English accuracy in the tested setup, although the magnitude of the difference varied considerably by model.

Files:

`research/reasoning_pilots/`

### 3. Global-MGSM 200-Pair Study

A larger paired experiment used 200 matched English-Arabic mathematical problems from Global-MGSM.

Results:

| Model | Arabic | English | EN-AR Gap |
|---|---:|---:|---:|
| Gemma-3-1B-it | 22.0% | 60.5% | 38.5 pp |
| Qwen2.5-Math-1.5B-Instruct | 1.5% | 89.5% | 88.0 pp |

Strict quality-control sensitivity analyses produced similar conclusions.

Files:

`research/global_mgsm_200/`

### 4. Qwen3.5-27B Global-MGSM Experiment

A stronger Qwen3.5-27B model was evaluated on the same 200-pair English-Arabic benchmark.

Final adjudicated results:

| Language | Accuracy |
|---|---:|
| Arabic | 95.0% |
| English | 99.5% |

English-Arabic gap: **4.5 percentage points**

Under the strict-QC subset, the gap decreased to approximately **2.15 percentage points**.

This experiment demonstrates that the very large language gaps observed in smaller models are not stable across model families and capability levels.

Files:

`research/qwen35_27b/`

### 5. GemMaroc English-Darija Experiment

Model:

`GemMaroc/Qwen2.5-32B-Instruct-darija`

A deterministic sample of 200 matched English and Moroccan Darija GSM8K-derived mathematical problems was evaluated.

Final conservative adjudication:

| Analysis | English | Darija | Gap |
|---|---:|---:|---:|
| ALL_200 | 95.5% | 88.5% | 7.0 pp |
| STRICT_QC_196 | 95.4% | 89.8% | 5.6 pp |

For ALL_200:

- Exact McNemar p = 0.0025768
- Paired bootstrap 95% CI for the gap = [3.0, 11.5] percentage points

For STRICT_QC_196:

- Exact McNemar p = 0.0127258
- Paired bootstrap 95% CI = [1.53, 9.69] percentage points

The results show strong mathematical reasoning performance in Moroccan Darija while retaining a modest English advantage in this model and benchmark.

Files:

`research/gemmaroc_darija/`

## Main Findings

Across the tested systems, English performance was consistently at least as high as Arabic or Darija performance on matched mathematical reasoning tasks.

However, the **magnitude of the disparity is strongly model-dependent**.

Smaller models showed large English-Arabic differences, while Qwen3.5-27B achieved near-ceiling performance in both English and MSA. GemMaroc also achieved strong performance in Moroccan Darija, with a substantially smaller residual gap than the smaller-model Arabic experiments.

The results therefore do **not** support a universal claim that language models cannot reason mathematically in Arabic.

Instead, they suggest that multilingual mathematical reasoning robustness depends strongly on the model, training, language variety, evaluation setting, and benchmark.

The PRM experiment additionally indicates that strong Arabic generation does not automatically imply language-robust reasoning evaluation: process reward models themselves may exhibit language-dependent discrimination.

## Repository Structure

```text
research/
├── prm_arabic_english/
├── reasoning_pilots/
├── global_mgsm_200/
├── qwen35_27b/
└── gemmaroc_darija/

docs/
└── Arabic_English_LLM_Reasoning_Final_Report.pdf

data/
model_utils/
vllm_add_dummy_model/