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

Final results:

| Language | Accuracy |
|---|---:|
| Arabic | 95.0% |
| English | 99.5% |

English-Arabic gap: **4.5 percentage points**

Under the strict-QC subset, the gap decreased to approximately **2.15 percentage points**.

This experiment shows that the very large language gaps observed in the smaller tested models are not stable across model families and capability levels.

Files:

`research/qwen35_27b/`

### 5. GemMaroc English-Darija Experiment

Model:

`GemMaroc/Qwen2.5-32B-Instruct-darija`

A deterministic sample of 200 matched English and Moroccan Darija GSM8K-derived mathematical problems was evaluated.

The Darija problems were drawn from DqaDqa and matched to their corresponding GSM8K problems. DqaDqa is culturally adapted rather than a literal translation of GSM8K, so paired English-Darija comparisons can reflect both language and localized wording/context differences.

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

The results show strong mathematical reasoning performance in Moroccan Darija while retaining a statistically detectable English advantage in this model and benchmark.

Files:

`research/gemmaroc_darija/`

### 6. GPT-OSS-120B English-Darija Experiment

Model:

`openai/gpt-oss-120b`

GPT-OSS-120B was evaluated via the Novita AI OpenAI-compatible API on the same 200 matched English-Darija problems used in the GemMaroc experiment.

Experimental setup:

- 200 matched problems
- 200 English generations
- 200 Moroccan Darija generations
- 400 total generations
- temperature = 0
- one generation per language per problem
- alternating English/Darija generation order
- identical prompt structure across languages
- conservative manual adjudication of automatic-scoring false negatives
- strict-QC subset excluding problems 21, 26, 128, and 185

Final adjudicated results:

| Subset | English | Darija | Gap | Exact McNemar p | Paired Bootstrap 95% CI |
|---|---:|---:|---:|---:|---:|
| ALL_200 | 190/200 (95.0%) | 181/200 (90.5%) | 4.50 pp | 0.0636 | [0.50, 9.00] pp |
| STRICT_QC_196 | 186/196 (94.9%) | 179/196 (91.3%) | 3.57 pp | 0.1435 | [-0.51, 7.65] pp |

The observed English-Darija gap was smaller than in the GemMaroc experiment. However, the exact paired McNemar test did not reach the conventional 0.05 significance threshold in either the full or strict-QC subset. The strict-QC bootstrap interval also included zero.

These results indicate strong Moroccan Darija mathematical reasoning performance for GPT-OSS-120B on this benchmark, with no clear statistically significant English advantage under the exact paired McNemar test.

Files:

`research/gemmaroc_darija/`

### 7. DeepSeek V3.2 English-Darija Experiment

Model:

`deepseek/deepseek-v3.2`

DeepSeek V3.2 was evaluated via the Novita AI OpenAI-compatible API on the same 200 matched English-Darija problems used for the GemMaroc and GPT-OSS-120B experiments.

Experimental setup:

- 200 matched problems
- 200 English generations
- 200 Moroccan Darija generations
- 400 total generations
- temperature = 0
- one generation per language per problem
- alternating English/Darija generation order
- identical prompt structure across languages
- conservative manual adjudication of automatic-scoring false negatives
- strict-QC subset excluding problems 21, 26, 128, and 185

Automatic scoring initially produced:

- English: 188/200 (94.0%)
- Darija: 179/200 (89.5%)

Manual review identified four false negatives caused by equivalent answer representations or automatic answer extraction:

- P25 English: `$3.50` equivalent to `350` cents
- P141 English: the response correctly derived `0.24 = 24%`, while automatic extraction captured `25` from the fraction `6/25`
- P141 Darija: `0.24` equivalent to `24%`
- P169 Darija: `22.5` hours equivalent to `1350` minutes

Final conservative adjudicated results:

| Subset | English | Darija | Gap | Exact McNemar p | Paired Bootstrap 95% CI |
|---|---:|---:|---:|---:|---:|
| ALL_200 | 190/200 (95.0%) | 181/200 (90.5%) | 4.50 pp | 0.1078 | [-0.50, 9.50] pp |
| STRICT_QC_196 | 186/196 (94.9%) | 180/196 (91.8%) | 3.06 pp | 0.2863 | [-1.53, 7.65] pp |

For ALL_200, the paired outcome structure was:

- both correct: 173
- both wrong: 2
- English-only correct: 17
- Darija-only correct: 8
- discordant pairs: 25

For STRICT_QC_196:

- both correct: 172
- both wrong: 2
- English-only correct: 14
- Darija-only correct: 8
- discordant pairs: 22

DeepSeek V3.2 therefore achieved strong performance in both languages. The observed English-Darija difference was 4.50 percentage points on the full sample and 3.06 points after strict QC.

Neither the ALL_200 nor STRICT_QC_196 difference reached the conventional 0.05 significance threshold under the exact paired McNemar test. The paired bootstrap 95% confidence intervals also included zero in both analyses.

DeepSeek V3.2 and GPT-OSS-120B obtained identical marginal ALL_200 accuracies (95.0% English and 90.5% Darija), but their paired error structures differed. Therefore, identical aggregate accuracies should not be interpreted as identical behavior.

Files:

`research/gemmaroc_darija/`

## English-Darija Cross-Model Comparison

The three models evaluated on the same 200 matched English-Darija benchmark can be summarized as follows.

### ALL_200

| Model | English | Darija | EN-DA Gap | Exact McNemar p | Paired Bootstrap 95% CI |
|---|---:|---:|---:|---:|---:|
| GemMaroc/Qwen2.5-32B | 95.5% | 88.5% | 7.00 pp | 0.0026 | [3.00, 11.50] pp |
| GPT-OSS-120B | 95.0% | 90.5% | 4.50 pp | 0.0636 | [0.50, 9.00] pp |
| DeepSeek V3.2 | 95.0% | 90.5% | 4.50 pp | 0.1078 | [-0.50, 9.50] pp |

### STRICT_QC_196

| Model | English | Darija | EN-DA Gap | Exact McNemar p | Paired Bootstrap 95% CI |
|---|---:|---:|---:|---:|---:|
| GemMaroc/Qwen2.5-32B | 95.4% | 89.8% | 5.61 pp | 0.0127 | [1.53, 9.69] pp |
| GPT-OSS-120B | 94.9% | 91.3% | 3.57 pp | 0.1435 | [-0.51, 7.65] pp |
| DeepSeek V3.2 | 94.9% | 91.8% | 3.06 pp | 0.2863 | [-1.53, 7.65] pp |

These results provide descriptive evidence that the English-Darija gap varies across model families. GemMaroc showed a statistically detectable English advantage on this benchmark, whereas GPT-OSS-120B and DeepSeek V3.2 did not show a clear difference under exact paired McNemar testing.

The smaller observed gaps for GPT-OSS-120B and DeepSeek V3.2 should not by themselves be interpreted as proof that either model is statistically more language-robust than GemMaroc. A direct paired comparison of model-specific language gaps would be required to support that stronger claim.

## Main Findings

Across the tested systems, English performance was consistently at least as high as Arabic or Darija performance on the matched mathematical reasoning tasks.

However, the **magnitude of the language-associated disparity was strongly model-dependent**.

The smaller Arabic-English generative models showed very large English advantages on Global-MGSM. In contrast, Qwen3.5-27B achieved near-ceiling performance in both English and MSA, reducing the observed English-Arabic gap to only a few percentage points.

The Moroccan Darija experiments similarly show that high mathematical reasoning accuracy is achievable in a lower-resource, non-standardized Arabic variety. GemMaroc, GPT-OSS-120B, and DeepSeek V3.2 all achieved high Darija accuracy, ranging from 88.5% to 90.5% on the full 200-problem sample after conservative adjudication.

Among the Darija experiments:

- GemMaroc achieved 95.5% English and 88.5% Darija accuracy, with a 7.0-point gap that was statistically significant under exact McNemar testing.
- GPT-OSS-120B achieved 95.0% English and 90.5% Darija accuracy, with a 4.5-point gap that did not reach the conventional significance threshold under exact McNemar testing.
- DeepSeek V3.2 achieved 95.0% English and 90.5% Darija accuracy, also with a 4.5-point gap, and its exact McNemar test likewise did not reach the conventional significance threshold.
- Under strict QC, DeepSeek V3.2's observed gap decreased to 3.06 percentage points and GPT-OSS-120B's to 3.57 percentage points.

The results therefore do **not** support a universal claim that language models cannot reason mathematically in Arabic or Moroccan Darija.

Instead, they suggest that multilingual mathematical reasoning robustness depends strongly on the model, training, language variety, evaluation setting, and benchmark.

The PRM experiment adds a separate finding: strong Arabic or Darija generation does not automatically imply language-robust reasoning evaluation. The tested process reward model showed substantially weaker correct-versus-incorrect discrimination in Arabic than in English.

This distinction between **reasoning generation** and **reasoning evaluation** is central to the project. A model may be capable of producing strong mathematical reasoning in Arabic or Darija while a separate evaluator or reward model remains less reliable when judging that reasoning.

## Methodological Notes and Limitations

The reported results should be interpreted within the tested models, datasets, prompts, and evaluation procedures.

Important limitations include:

- The Arabic and Darija results should not be generalized to all Arabic varieties, tasks, or language models.
- DqaDqa is culturally adapted rather than a literal translation of GSM8K. English-Darija paired differences can therefore include localized context, unit, currency, or wording changes in addition to language.
- GSM8K/MGSM-style problems may have appeared in model pretraining data. Potential benchmark contamination or differential exposure, particularly for English material, cannot be ruled out.
- Automatic numeric answer extraction can misclassify mathematically equivalent answers, motivating conservative manual adjudication of flagged responses.
- The strict-QC analyses exclude four predefined problematic English-Darija pairs: P21, P26, P128, and P185.
- Comparisons across model families are observational. Differences in architecture, scale, training data, instruction tuning, serving infrastructure, chat templates, and other model-specific factors prevent attributing improvements to model size or any single causal factor.
- Differences between two models' observed language gaps should not be treated as statistically established differences without a direct paired model-gap comparison.

## Repository Structure

```text
research/
├── prm_arabic_english/
├── reasoning_pilots/
├── global_mgsm_200/
├── qwen35_27b/
└── gemmaroc_darija/         # GemMaroc, GPT-OSS-120B, and DeepSeek V3.2 English-Darija experiments

docs/
└── Arabic_English_LLM_Reasoning_Final_Report.pdf

data/
model_utils/
vllm_add_dummy_model/
```