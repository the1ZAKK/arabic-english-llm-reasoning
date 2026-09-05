\# GemMaroc English–Darija Mathematical Reasoning Experiment



This experiment evaluates mathematical reasoning performance in English and Moroccan Darija using matched GSM8K-derived problems.



\## Model



GemMaroc/Qwen2.5-32B-Instruct-darija



The model was served on RunPod using vLLM through an OpenAI-compatible local endpoint.



\## Dataset



The Darija side was based on:



\- `abdeljalilELmajjodi/DqaDqa`



The English side was aligned with:



\- `openai/gsm8k`



DqaDqa contains culturally adapted Moroccan Darija versions of GSM8K-style problems. Therefore, the comparison is not always a literal translation comparison.



A deterministic 200-problem matched sample was used.



\## Quality Control



Problem pairs were manually checked for mathematical equivalence.



Primary analysis:



\- ALL\_200: all 200 sampled pairs



Strict sensitivity analysis excluded four problematic pairs:



\- 21

\- 26

\- 128

\- 185



Strict subset size:



\- N = 196



\## Generation



Each problem was evaluated once in English and once in Darija.



Generation was deterministic:



\- temperature = 0

\- one generation per language/problem pair

\- alternating language order

\- 400 generations total



The original generation script was run on RunPod and is not included in this repository.



\## Result Files



`gemmaroc\_en\_darija\_200\_results.csv`



Raw generation results before manual adjudication.



`gemmaroc\_en\_darija\_200\_adjudicated.csv`



Final results after conservative manual adjudication.



\## Automatic Scoring



English:



\- 183 / 200

\- 91.5%



Darija:



\- 170 / 200

\- 85.0%



English–Darija gap:



\- 6.5 percentage points



\## Final Conservative Adjudication



\### ALL\_200



English:



\- 191 / 200

\- 95.5%



Darija:



\- 177 / 200

\- 88.5%



Gap:



\- 7.0 percentage points



Paired outcomes:



\- Both correct: 174

\- Both wrong: 6

\- English-only correct: 17

\- Darija-only correct: 3

\- Discordant pairs: 20



Exact two-sided McNemar test:



\- p = 0.0025768



Paired bootstrap 95% confidence interval for the English–Darija gap:



\- approximately \[3.0, 11.5] percentage points



\### STRICT\_QC\_196



English:



\- 187 / 196

\- 95.4%



Darija:



\- 176 / 196

\- 89.8%



Gap:



\- 5.6 percentage points



Paired outcomes:



\- Both correct: 173

\- Both wrong: 6

\- English-only correct: 14

\- Darija-only correct: 3

\- Discordant pairs: 17



Exact two-sided McNemar test:



\- p = 0.0127258



Paired bootstrap 95% confidence interval:



\- approximately \[1.5, 9.7] percentage points



\## Adjudication Policy



Automatic failures were manually reviewed.



A response was counted as correct only when it clearly reached the gold answer or an equivalent representation.



Examples of accepted equivalent representations include:



\- `$3.50` when the stored gold answer is `350` cents

\- `0.24` when the stored gold answer is `24%`



Responses that were merely on the correct path but did not reach a sufficient final result before truncation were not credited.



\## Interpretation



GemMaroc performs strongly on Moroccan Darija mathematical reasoning, but English remains higher on these matched problems.



The disparity is substantially smaller than the large Arabic–English gaps observed in earlier smaller-model experiments in this project.



These results should not be interpreted as evidence of a universal Darija reasoning deficit. They are specific to this model, benchmark construction, prompting setup, and evaluation procedure.



\## Limitations



DqaDqa is culturally adapted rather than strictly translated, so some differences reflect context, units, currency, or wording as well as language.



The benchmark is GSM8K-derived, and the GemMaroc model may have encountered related mathematical data during training or evaluation.



Some generations reached the token limit, so manual adjudication was required for several cases.



The original RunPod generation script is not available in this repository, so exact generation reproduction is limited to the documented configuration and raw output files.

