import pandas as pd
import numpy as np
from scipy import stats


# ============================================================
# CONFIGURATION
# ============================================================

ARABIC_FILE = "arabic_prm_results.csv"
ENGLISH_FILE = "english_prm_results.csv"

OUTPUT_FILE = "discrimination_analysis_results.csv"


# ============================================================
# HEADER
# ============================================================

print("=" * 70)
print("ARABIC vs ENGLISH PRM DISCRIMINATION ANALYSIS")
print("=" * 70)


# ============================================================
# LOAD DATA
# ============================================================

print("\nLoading result files...")

arabic = pd.read_csv(ARABIC_FILE)
english = pd.read_csv(ENGLISH_FILE)

print(f"Arabic evaluations : {len(arabic)}")
print(f"English evaluations: {len(english)}")


# ============================================================
# CHECK REQUIRED COLUMNS
# ============================================================

required_columns = [
    "problem_id",
    "category",
    "average_score"
]

for column in required_columns:

    if column not in arabic.columns:
        raise ValueError(
            f"Arabic CSV is missing column: {column}"
        )

    if column not in english.columns:
        raise ValueError(
            f"English CSV is missing column: {column}"
        )


print("\nCSV structure verified.")


# ============================================================
# NORMALIZE
# ============================================================

arabic["category"] = (
    arabic["category"]
    .astype(str)
    .str.strip()
    .str.lower()
)

english["category"] = (
    english["category"]
    .astype(str)
    .str.strip()
    .str.lower()
)

arabic["average_score"] = pd.to_numeric(
    arabic["average_score"],
    errors="coerce"
)

english["average_score"] = pd.to_numeric(
    english["average_score"],
    errors="coerce"
)


# ============================================================
# DEFINE CORRECT / INCORRECT
# ============================================================

incorrect_categories = [
    "arithmetic_error",
    "logic_error",
    "completely_wrong"
]


# ============================================================
# CALCULATE PER-PROBLEM DISCRIMINATION
# ============================================================

print("\n" + "=" * 70)
print("CALCULATING PER-PROBLEM DISCRIMINATION")
print("=" * 70)


def calculate_problem_gaps(df):

    correct = df[
        df["category"] == "correct"
    ][
        ["problem_id", "average_score"]
    ].copy()

    incorrect = df[
        df["category"].isin(incorrect_categories)
    ][
        ["problem_id", "average_score"]
    ].copy()

    # Average all incorrect response types
    incorrect_mean = (
        incorrect
        .groupby("problem_id")["average_score"]
        .mean()
        .reset_index()
    )

    incorrect_mean.rename(
        columns={
            "average_score": "incorrect_mean"
        },
        inplace=True
    )

    correct.rename(
        columns={
            "average_score": "correct_score"
        },
        inplace=True
    )

    merged = pd.merge(
        correct,
        incorrect_mean,
        on="problem_id",
        how="inner"
    )

    merged["discrimination_gap"] = (
        merged["correct_score"]
        - merged["incorrect_mean"]
    )

    return merged


arabic_gaps = calculate_problem_gaps(arabic)
english_gaps = calculate_problem_gaps(english)


print(
    f"\nArabic paired problems : {len(arabic_gaps)}"
)

print(
    f"English paired problems: {len(english_gaps)}"
)


# ============================================================
# MERGE ARABIC + ENGLISH
# ============================================================

paired = pd.merge(
    arabic_gaps,
    english_gaps,
    on="problem_id",
    suffixes=("_arabic", "_english")
)


print(
    f"Problems available for language comparison: "
    f"{len(paired)}"
)


if len(paired) < 2:

    raise ValueError(
        "Not enough paired problems for statistical testing."
    )


# ============================================================
# DISPLAY PER-PROBLEM GAPS
# ============================================================

print("\n" + "=" * 70)
print("PER-PROBLEM DISCRIMINATION GAPS")
print("=" * 70)

for _, row in paired.iterrows():

    print(
        f"Problem {row['problem_id']}: "
        f"Arabic={row['discrimination_gap_arabic']:+.4f} | "
        f"English={row['discrimination_gap_english']:+.4f}"
    )


# ============================================================
# OVERALL DISCRIMINATION
# ============================================================

arabic_gap = paired[
    "discrimination_gap_arabic"
].to_numpy()

english_gap = paired[
    "discrimination_gap_english"
].to_numpy()


print("\n" + "=" * 70)
print("OVERALL DISCRIMINATION")
print("=" * 70)

print(
    f"\nArabic mean gap : "
    f"{arabic_gap.mean():+.4f}"
)

print(
    f"English mean gap: "
    f"{english_gap.mean():+.4f}"
)


language_difference = (
    english_gap.mean()
    - arabic_gap.mean()
)


print(
    f"English - Arabic: "
    f"{language_difference:+.4f}"
)


# ============================================================
# PAIRED DIFFERENCES
# ============================================================

differences = (
    english_gap
    - arabic_gap
)


print("\n" + "=" * 70)
print("PAIRED LANGUAGE DIFFERENCE")
print("=" * 70)

print(
    f"\nMean difference: "
    f"{differences.mean():+.4f}"
)

print(
    f"Std difference : "
    f"{differences.std(ddof=1):.4f}"
)


# ============================================================
# 95% CONFIDENCE INTERVAL
# ============================================================

n = len(differences)

mean_diff = differences.mean()

std_diff = differences.std(ddof=1)

se_diff = std_diff / np.sqrt(n)

t_critical = stats.t.ppf(
    0.975,
    df=n - 1
)

ci_low = (
    mean_diff
    - t_critical * se_diff
)

ci_high = (
    mean_diff
    + t_critical * se_diff
)


print(
    f"\n95% CI: "
    f"[{ci_low:.4f}, {ci_high:.4f}]"
)


# ============================================================
# PAIRED T-TEST
# ============================================================

t_stat, t_p = stats.ttest_rel(
    english_gap,
    arabic_gap
)


print("\n" + "=" * 70)
print("PAIRED T-TEST")
print("=" * 70)

print(
    f"\nt = {t_stat:.4f}"
)

print(
    f"p = {t_p:.10f}"
)


# ============================================================
# WILCOXON SIGNED-RANK TEST
# ============================================================

try:

    w_stat, w_p = stats.wilcoxon(
        english_gap,
        arabic_gap
    )

except ValueError:

    w_stat = np.nan
    w_p = np.nan


print("\n" + "=" * 70)
print("WILCOXON SIGNED-RANK TEST")
print("=" * 70)

print(
    f"\nW = {w_stat:.4f}"
)

print(
    f"p = {w_p:.10f}"
)


# ============================================================
# COHEN'S DZ
# ============================================================

if std_diff > 0:

    cohens_dz = (
        mean_diff
        / std_diff
    )

else:

    cohens_dz = np.nan


print("\n" + "=" * 70)
print("EFFECT SIZE")
print("=" * 70)

print(
    f"\nCohen's dz = {cohens_dz:.4f}"
)


# ============================================================
# INTERPRET EFFECT SIZE
# ============================================================

abs_d = abs(cohens_dz)

if abs_d < 0.2:

    effect_label = "negligible"

elif abs_d < 0.5:

    effect_label = "small"

elif abs_d < 0.8:

    effect_label = "medium"

else:

    effect_label = "large"


print(
    f"Effect interpretation: {effect_label}"
)


# ============================================================
# CLASSIFICATION ANALYSIS
# ============================================================

print("\n" + "=" * 70)
print("CORRECT vs INCORRECT CLASSIFICATION")
print("=" * 70)


def classification_metrics(df):

    scores = []
    labels = []

    for _, row in df.iterrows():

        if row["category"] == "correct":

            labels.append(1)
            scores.append(row["average_score"])

        elif row["category"] in incorrect_categories:

            labels.append(0)
            scores.append(row["average_score"])

    scores = np.array(scores)
    labels = np.array(labels)

    thresholds = np.unique(scores)

    best_accuracy = -1
    best_threshold = None

    best_precision = 0
    best_recall = 0
    best_f1 = 0

    for threshold in thresholds:

        predictions = (
            scores >= threshold
        ).astype(int)

        tp = np.sum(
            (predictions == 1)
            & (labels == 1)
        )

        tn = np.sum(
            (predictions == 0)
            & (labels == 0)
        )

        fp = np.sum(
            (predictions == 1)
            & (labels == 0)
        )

        fn = np.sum(
            (predictions == 0)
            & (labels == 1)
        )

        accuracy = (
            (tp + tn)
            / len(labels)
        )

        precision = (
            tp / (tp + fp)
            if (tp + fp) > 0
            else 0
        )

        recall = (
            tp / (tp + fn)
            if (tp + fn) > 0
            else 0
        )

        f1 = (
            2 * precision * recall
            / (precision + recall)
            if (precision + recall) > 0
            else 0
        )

        if accuracy > best_accuracy:

            best_accuracy = accuracy
            best_threshold = threshold
            best_precision = precision
            best_recall = recall
            best_f1 = f1

    # ROC-AUC
    try:

        from sklearn.metrics import roc_auc_score

        auc = roc_auc_score(
            labels,
            scores
        )

    except Exception:

        auc = np.nan

    return {
        "accuracy": best_accuracy,
        "threshold": best_threshold,
        "precision": best_precision,
        "recall": best_recall,
        "f1": best_f1,
        "auc": auc
    }


arabic_metrics = classification_metrics(
    arabic
)

english_metrics = classification_metrics(
    english
)


print("\nArabic:")

print(
    f"  Accuracy : "
    f"{arabic_metrics['accuracy']:.4f}"
)

print(
    f"  Precision: "
    f"{arabic_metrics['precision']:.4f}"
)

print(
    f"  Recall   : "
    f"{arabic_metrics['recall']:.4f}"
)

print(
    f"  F1       : "
    f"{arabic_metrics['f1']:.4f}"
)

print(
    f"  ROC-AUC  : "
    f"{arabic_metrics['auc']:.4f}"
)

print(
    f"  Threshold: "
    f"{arabic_metrics['threshold']:.4f}"
)


print("\nEnglish:")

print(
    f"  Accuracy : "
    f"{english_metrics['accuracy']:.4f}"
)

print(
    f"  Precision: "
    f"{english_metrics['precision']:.4f}"
)

print(
    f"  Recall   : "
    f"{english_metrics['recall']:.4f}"
)

print(
    f"  F1       : "
    f"{english_metrics['f1']:.4f}"
)

print(
    f"  ROC-AUC  : "
    f"{english_metrics['auc']:.4f}"
)

print(
    f"  Threshold: "
    f"{english_metrics['threshold']:.4f}"
)


# ============================================================
# SAVE RESULTS
# ============================================================

results = {

    "arabic_discrimination_gap":
        arabic_gap.mean(),

    "english_discrimination_gap":
        english_gap.mean(),

    "english_minus_arabic_gap":
        language_difference,

    "mean_difference":
        mean_diff,

    "ci_low":
        ci_low,

    "ci_high":
        ci_high,

    "paired_t":
        t_stat,

    "paired_t_p":
        t_p,

    "wilcoxon_w":
        w_stat,

    "wilcoxon_p":
        w_p,

    "cohens_dz":
        cohens_dz,

    "arabic_accuracy":
        arabic_metrics["accuracy"],

    "english_accuracy":
        english_metrics["accuracy"],

    "arabic_precision":
        arabic_metrics["precision"],

    "english_precision":
        english_metrics["precision"],

    "arabic_recall":
        arabic_metrics["recall"],

    "english_recall":
        english_metrics["recall"],

    "arabic_f1":
        arabic_metrics["f1"],

    "english_f1":
        english_metrics["f1"],

    "arabic_auc":
        arabic_metrics["auc"],

    "english_auc":
        english_metrics["auc"]

}


results_df = pd.DataFrame(
    [results]
)

results_df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# SAVE PER-PROBLEM DATA
# ============================================================

paired_output = (
    "per_problem_discrimination.csv"
)

paired.to_csv(
    paired_output,
    index=False
)


# ============================================================
# FINAL INTERPRETATION
# ============================================================

print("\n" + "=" * 70)
print("FINAL INTERPRETATION")
print("=" * 70)

if t_p < 0.05:

    print(
        "\nThe difference in discrimination gaps "
        "between English and Arabic is statistically "
        "significant (p < 0.05)."
    )

else:

    print(
        "\nThe difference in discrimination gaps "
        "is NOT statistically significant (p >= 0.05)."
    )


if language_difference > 0:

    print(
        "\nEnglish has a larger discrimination gap "
        "than Arabic."
    )

else:

    print(
        "\nArabic has a larger discrimination gap "
        "than English."
    )


print(
    f"\nArabic gap : {arabic_gap.mean():.4f}"
)

print(
    f"English gap: {english_gap.mean():.4f}"
)

print(
    f"Difference : {language_difference:+.4f}"
)

print(
    f"\nCohen's dz: {cohens_dz:.4f}"
)

print(
    "\nIMPORTANT:"
)

print(
    "This analysis evaluates the language sensitivity "
    "of the PRM's reasoning-score discrimination."
)

print(
    "It does NOT by itself prove that all LLMs "
    "reason worse in Arabic than English."
)

print(
    "\nResults saved to:"
)

print(
    f"  {OUTPUT_FILE}"
)

print(
    f"  {paired_output}"
)

print("\n" + "=" * 70)
print("ANALYSIS COMPLETE")
print("=" * 70)