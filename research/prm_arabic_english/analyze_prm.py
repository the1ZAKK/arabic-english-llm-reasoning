import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)

# ============================================================
# LOAD RESULTS
# ============================================================

FILE = "arabic_prm_results.csv"

df = pd.read_csv(FILE)

print("=" * 70)
print("ARABIC PRM — QUANTITATIVE EVALUATION")
print("=" * 70)

print(f"\nTotal evaluations: {len(df)}")
print(f"Problems: {df['problem_id'].nunique()}")

print("\nCategories:")
print(df["category"].value_counts())


# ============================================================
# CATEGORY STATISTICS
# ============================================================

print("\n" + "=" * 70)
print("CATEGORY STATISTICS")
print("=" * 70)

stats = df.groupby("category").agg(
    examples=("average_score", "count"),
    mean_score=("average_score", "mean"),
    std_score=("average_score", "std"),
    mean_minimum=("minimum_score", "mean"),
    mean_maximum=("maximum_score", "mean"),
)

print("\n")
print(stats.round(4))


# ============================================================
# CORRECT VS INCORRECT
# ============================================================

df["is_correct"] = (df["category"] == "correct").astype(int)

print("\n" + "=" * 70)
print("CORRECT vs INCORRECT")
print("=" * 70)

correct_scores = df[df["is_correct"] == 1]["average_score"]
incorrect_scores = df[df["is_correct"] == 0]["average_score"]

print(f"\nCorrect examples   : {len(correct_scores)}")
print(f"Incorrect examples : {len(incorrect_scores)}")

print(f"\nCorrect mean score   : {correct_scores.mean():.4f}")
print(f"Incorrect mean score : {incorrect_scores.mean():.4f}")

difference = correct_scores.mean() - incorrect_scores.mean()

print(f"Difference           : {difference:+.4f}")


# ============================================================
# BINARY CLASSIFICATION
# ============================================================

print("\n" + "=" * 70)
print("BINARY CLASSIFICATION")
print("=" * 70)

# Test multiple thresholds.
thresholds = np.arange(0.20, 0.81, 0.05)

print("\nThreshold | Accuracy | Precision | Recall | F1")
print("-" * 55)

best_threshold = None
best_f1 = -1

for threshold in thresholds:

    predicted = (df["average_score"] >= threshold).astype(int)

    accuracy = accuracy_score(df["is_correct"], predicted)
    precision = precision_score(
        df["is_correct"],
        predicted,
        zero_division=0
    )
    recall = recall_score(
        df["is_correct"],
        predicted,
        zero_division=0
    )
    f1 = f1_score(
        df["is_correct"],
        predicted,
        zero_division=0
    )

    print(
        f"{threshold:8.2f} | "
        f"{accuracy:8.4f} | "
        f"{precision:9.4f} | "
        f"{recall:6.4f} | "
        f"{f1:6.4f}"
    )

    if f1 > best_f1:
        best_f1 = f1
        best_threshold = threshold


print("\nBest threshold based on F1:")
print(f"Threshold = {best_threshold:.2f}")
print(f"F1        = {best_f1:.4f}")


# ============================================================
# FINAL CLASSIFICATION USING BEST THRESHOLD
# ============================================================

predicted = (
    df["average_score"] >= best_threshold
).astype(int)

accuracy = accuracy_score(df["is_correct"], predicted)
precision = precision_score(
    df["is_correct"],
    predicted,
    zero_division=0
)
recall = recall_score(
    df["is_correct"],
    predicted,
    zero_division=0
)
f1 = f1_score(
    df["is_correct"],
    predicted,
    zero_division=0
)

print("\n" + "=" * 70)
print("BEST THRESHOLD RESULTS")
print("=" * 70)

print(f"\nThreshold : {best_threshold:.2f}")
print(f"Accuracy  : {accuracy:.4f}")
print(f"Precision : {precision:.4f}")
print(f"Recall    : {recall:.4f}")
print(f"F1 Score  : {f1:.4f}")


# ============================================================
# ROC-AUC
# ============================================================

auc = roc_auc_score(
    df["is_correct"],
    df["average_score"]
)

print("\n" + "=" * 70)
print("ROC-AUC")
print("=" * 70)

print(f"\nROC-AUC: {auc:.4f}")


# ============================================================
# CONFUSION MATRIX
# ============================================================

cm = confusion_matrix(
    df["is_correct"],
    predicted
)

print("\n" + "=" * 70)
print("CONFUSION MATRIX")
print("=" * 70)

print("\nRows = Actual")
print("Columns = Predicted")
print("\n              Predicted")
print("              Wrong  Correct")
print(f"Actual Wrong   {cm[0,0]:5d}   {cm[0,1]:5d}")
print(f"Actual Correct {cm[1,0]:5d}   {cm[1,1]:5d}")


# ============================================================
# CLASSIFICATION REPORT
# ============================================================

print("\n" + "=" * 70)
print("CLASSIFICATION REPORT")
print("=" * 70)

print(
    classification_report(
        df["is_correct"],
        predicted,
        target_names=["Incorrect", "Correct"],
        digits=4,
        zero_division=0
    )
)


# ============================================================
# CATEGORY COMPARISON
# ============================================================

print("\n" + "=" * 70)
print("CATEGORY COMPARISON")
print("=" * 70)

category_order = [
    "correct",
    "arithmetic_error",
    "logic_error",
    "completely_wrong",
]

for category in category_order:

    subset = df[df["category"] == category]

    if len(subset) == 0:
        continue

    print(
        f"\n{category.upper()}"
    )

    print(
        f"  Mean   : {subset['average_score'].mean():.4f}"
    )

    print(
        f"  Median : {subset['average_score'].median():.4f}"
    )

    print(
        f"  Min    : {subset['average_score'].min():.4f}"
    )

    print(
        f"  Max    : {subset['average_score'].max():.4f}"
    )


# ============================================================
# PLOT 1 — SCORE DISTRIBUTION
# ============================================================

plt.figure(figsize=(10, 6))

for category in category_order:

    subset = df[df["category"] == category]

    if len(subset) == 0:
        continue

    plt.hist(
        subset["average_score"],
        bins=10,
        alpha=0.5,
        label=category
    )

plt.xlabel("Average PRM Score")
plt.ylabel("Number of Examples")
plt.title("Arabic PRM Score Distribution")
plt.legend()
plt.tight_layout()

plt.savefig(
    "prm_score_distribution.png",
    dpi=300
)

plt.show()


# ============================================================
# PLOT 2 — CATEGORY MEAN SCORES
# ============================================================

means = []

labels = []

for category in category_order:

    subset = df[df["category"] == category]

    if len(subset) == 0:
        continue

    labels.append(category)
    means.append(subset["average_score"].mean())

plt.figure(figsize=(10, 6))

plt.bar(labels, means)

plt.ylabel("Average PRM Score")
plt.xlabel("Category")
plt.title("Average PRM Score by Reasoning Category")

plt.xticks(rotation=20)

plt.tight_layout()

plt.savefig(
    "prm_category_scores.png",
    dpi=300
)

plt.show()


# ============================================================
# PLOT 3 — CORRECT VS INCORRECT
# ============================================================

plt.figure(figsize=(8, 6))

plt.boxplot(
    [
        correct_scores,
        incorrect_scores
    ],
    tick_labels=[
        "Correct",
        "Incorrect"
    ]
)

plt.ylabel("Average PRM Score")
plt.title("Correct vs Incorrect Arabic Reasoning")

plt.tight_layout()

plt.savefig(
    "prm_correct_vs_incorrect.png",
    dpi=300
)

plt.show()


# ============================================================
# SAVE EXTENDED CSV
# ============================================================

df["predicted_correct"] = predicted

df.to_csv(
    "arabic_prm_results_analyzed.csv",
    index=False
)

print("\n" + "=" * 70)
print("ANALYSIS COMPLETE")
print("=" * 70)

print("\nGenerated files:")

print("  arabic_prm_results_analyzed.csv")
print("  prm_score_distribution.png")
print("  prm_category_scores.png")
print("  prm_correct_vs_incorrect.png")

print("\n")