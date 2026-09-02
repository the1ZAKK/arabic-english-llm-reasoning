import pandas as pd
import numpy as np
from scipy import stats

INPUT_FILE = "gemma3_reasoning_results.csv"
OUTPUT_FILE = "gemma3_reasoning_adjudicated.csv"
PAIRED_FILE = "gemma3_paired_results.csv"
SUMMARY_FILE = "gemma3_statistical_summary.csv"

# ------------------------------------------------------------
# Load
# ------------------------------------------------------------

df = pd.read_csv(INPUT_FILE)

df["problem_id"] = df["problem_id"].astype(int)
df["language"] = df["language"].str.lower()
df["automatic_is_correct"] = df["is_correct"].astype(int)
df["manual_is_correct"] = df["automatic_is_correct"]

df["manual_note"] = ""

# ------------------------------------------------------------
# MANUAL ADJUDICATION
# ------------------------------------------------------------

# English Problem 5:
# Correct reasoning and repeated answer 30.
# Extractor selected a final truncated "3".

mask = (
    (df["language"] == "english")
    & (df["problem_id"] == 5)
)

df.loc[mask, "manual_is_correct"] = 1
df.loc[mask, "manual_note"] = (
    "Correct solution: model computed 5*6=30 and repeatedly "
    "gave FINAL ANSWER: 30. Extractor captured a later truncated 3."
)

# Arabic Problem 14:
# Correct reasoning: 60 / 2 = 30 km/h.
# Extractor captured malformed repeated digits after the answer.

mask = (
    (df["language"] == "arabic")
    & (df["problem_id"] == 14)
)

df.loc[mask, "manual_is_correct"] = 1
df.loc[mask, "manual_note"] = (
    "Correct solution: model explicitly derived 60/2=30 and "
    "stated speed = 30 km/h. Later token degeneration caused "
    "the extractor to capture repeated digits."
)

# ------------------------------------------------------------
# Accuracy
# ------------------------------------------------------------

arabic = df[df["language"] == "arabic"]
english = df[df["language"] == "english"]

ar_correct = int(arabic["manual_is_correct"].sum())
en_correct = int(english["manual_is_correct"].sum())

ar_accuracy = ar_correct / 20
en_accuracy = en_correct / 20

gap = en_accuracy - ar_accuracy

print("=" * 72)
print("GEMMA 3 ADJUDICATED RESULTS")
print("=" * 72)

print(f"\nArabic : {ar_correct}/20 = {ar_accuracy:.4f}")
print(f"English: {en_correct}/20 = {en_accuracy:.4f}")
print(f"Gap    : {gap:+.4f} ({gap*100:+.1f} percentage points)")

# ------------------------------------------------------------
# Create paired dataset
# ------------------------------------------------------------

ar = (
    arabic[["problem_id", "manual_is_correct"]]
    .rename(columns={"manual_is_correct": "arabic_correct"})
)

en = (
    english[["problem_id", "manual_is_correct"]]
    .rename(columns={"manual_is_correct": "english_correct"})
)

paired = pd.merge(ar, en, on="problem_id").sort_values("problem_id")

both_correct = int(
    ((paired.arabic_correct == 1) &
     (paired.english_correct == 1)).sum()
)

both_wrong = int(
    ((paired.arabic_correct == 0) &
     (paired.english_correct == 0)).sum()
)

english_only = int(
    ((paired.arabic_correct == 0) &
     (paired.english_correct == 1)).sum()
)

arabic_only = int(
    ((paired.arabic_correct == 1) &
     (paired.english_correct == 0)).sum()
)

print("\n" + "=" * 72)
print("PAIRED OUTCOMES")
print("=" * 72)

print("\nBoth correct:", both_correct)
print("Both wrong:", both_wrong)
print("English correct / Arabic wrong:", english_only)
print("Arabic correct / English wrong:", arabic_only)

# ------------------------------------------------------------
# Exact McNemar
# ------------------------------------------------------------

discordant = english_only + arabic_only

if discordant == 0:
    p_value = 1.0
else:
    p_value = stats.binomtest(
        min(english_only, arabic_only),
        n=discordant,
        p=0.5,
        alternative="two-sided",
    ).pvalue

print("\n" + "=" * 72)
print("EXACT MCNEMAR TEST")
print("=" * 72)

print("\nDiscordant pairs:", discordant)
print(f"Exact two-sided p-value: {p_value:.10f}")

# ------------------------------------------------------------
# Bootstrap paired accuracy-gap CI
# ------------------------------------------------------------

paired["difference"] = (
    paired["english_correct"]
    - paired["arabic_correct"]
)

differences = paired["difference"].to_numpy()

rng = np.random.default_rng(42)

bootstrap = []

for _ in range(10000):
    sample = rng.choice(
        differences,
        size=len(differences),
        replace=True
    )
    bootstrap.append(sample.mean())

ci_low, ci_high = np.percentile(
    bootstrap,
    [2.5, 97.5]
)

print("\n" + "=" * 72)
print("BOOTSTRAP 95% CONFIDENCE INTERVAL")
print("=" * 72)

print(f"\nObserved gap: {gap:+.4f}")
print(f"95% bootstrap CI: [{ci_low:.4f}, {ci_high:.4f}]")

# ------------------------------------------------------------
# Show actual remaining failures
# ------------------------------------------------------------

print("\n" + "=" * 72)
print("ADJUDICATED ARABIC FAILURES")
print("=" * 72)

failures = arabic[
    arabic["manual_is_correct"] == 0
]

for _, row in failures.iterrows():
    print(
        f"Problem {int(row['problem_id']):2d}: "
        f"expected={row['expected_answer']} | "
        f"extracted={row['extracted_answer']}"
    )

# ------------------------------------------------------------
# Save
# ------------------------------------------------------------

df.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig"
)

paired.to_csv(
    PAIRED_FILE,
    index=False,
    encoding="utf-8-sig"
)

summary = pd.DataFrame([{
    "model": "Gemma-3-1B-IT",
    "arabic_correct": ar_correct,
    "arabic_total": 20,
    "arabic_accuracy": ar_accuracy,
    "english_correct": en_correct,
    "english_total": 20,
    "english_accuracy": en_accuracy,
    "english_minus_arabic": gap,
    "both_correct": both_correct,
    "both_wrong": both_wrong,
    "english_only_correct": english_only,
    "arabic_only_correct": arabic_only,
    "mcnemar_exact_p": p_value,
    "bootstrap_ci_low": ci_low,
    "bootstrap_ci_high": ci_high,
}])

summary.to_csv(
    SUMMARY_FILE,
    index=False,
    encoding="utf-8-sig"
)

print("\n" + "=" * 72)
print("INTERPRETATION")
print("=" * 72)

if p_value < 0.05:
    print("\nPaired Arabic-English difference is statistically significant.")
else:
    print(
        "\nPaired difference does not reach p < 0.05 "
        "on this 20-problem sample."
    )

print(
    "\nA positive English-Arabic gap nevertheless indicates "
    "higher English accuracy on this benchmark."
)

print("\nSaved:")
print(" ", OUTPUT_FILE)
print(" ", PAIRED_FILE)
print(" ", SUMMARY_FILE)