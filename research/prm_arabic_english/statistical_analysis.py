import pandas as pd
import numpy as np
from scipy import stats

INPUT = "arabic_prm_results.csv"
OUTPUT = "arabic_prm_statistical_analysis.csv"

df = pd.read_csv(INPUT)

# Ensure the expected columns exist
required = {"problem_id", "category", "average_score"}
missing = required - set(df.columns)
if missing:
    raise ValueError(f"Missing required columns: {missing}")

# Normalize category names
df["category"] = df["category"].astype(str).str.strip().str.lower()

categories = ["correct", "arithmetic_error", "logic_error", "completely_wrong"]

print("=" * 72)
print("ARABIC PRM — STATISTICAL SIGNIFICANCE ANALYSIS")
print("=" * 72)
print(f"Total evaluations: {len(df)}")
print(f"Problems: {df['problem_id'].nunique()}")

# ------------------------------------------------------------
# Descriptive statistics
# ------------------------------------------------------------
print("\n" + "=" * 72)
print("DESCRIPTIVE STATISTICS")
print("=" * 72)

desc_rows = []
for cat in categories:
    x = df.loc[df["category"] == cat, "average_score"].dropna()
    desc_rows.append({
        "category": cat,
        "n": len(x),
        "mean": x.mean(),
        "std": x.std(ddof=1),
        "median": x.median(),
        "min": x.min(),
        "max": x.max(),
    })

desc = pd.DataFrame(desc_rows)
print(desc.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
def cohens_dz(a, b):
    """Paired Cohen's dz = mean(difference) / SD(difference)."""
    d = np.asarray(a) - np.asarray(b)
    sd = d.std(ddof=1)
    return np.nan if sd == 0 else d.mean() / sd

def ci_mean_difference(a, b, confidence=0.95):
    """95% CI for paired mean difference a-b."""
    d = np.asarray(a) - np.asarray(b)
    n = len(d)
    mean_d = d.mean()
    se = stats.sem(d)
    tcrit = stats.t.ppf((1 + confidence) / 2, n - 1)
    return mean_d - tcrit * se, mean_d + tcrit * se

# ------------------------------------------------------------
# Paired comparisons
# Each problem_id has a correct answer and an error variant.
# Pairing by problem_id is therefore more appropriate than
# treating all observations as independent.
# ------------------------------------------------------------
print("\n" + "=" * 72)
print("PAIRED STATISTICAL TESTS")
print("=" * 72)

results = []

for incorrect_cat in categories[1:]:
    pair = df[df["category"].isin(["correct", incorrect_cat])].pivot(
        index="problem_id",
        columns="category",
        values="average_score"
    ).dropna()

    correct = pair["correct"].to_numpy()
    incorrect = pair[incorrect_cat].to_numpy()
    diff = correct - incorrect

    # Paired t-test
    t_stat, t_p = stats.ttest_rel(correct, incorrect)

    # Wilcoxon signed-rank test
    try:
        w_stat, w_p = stats.wilcoxon(correct, incorrect, alternative="two-sided")
    except ValueError:
        w_stat, w_p = np.nan, np.nan

    d_z = cohens_dz(correct, incorrect)
    ci_low, ci_high = ci_mean_difference(correct, incorrect)

    results.append({
        "comparison": f"correct_vs_{incorrect_cat}",
        "n_pairs": len(pair),
        "correct_mean": correct.mean(),
        "incorrect_mean": incorrect.mean(),
        "mean_difference": diff.mean(),
        "ci95_low": ci_low,
        "ci95_high": ci_high,
        "paired_t": t_stat,
        "paired_t_p": t_p,
        "wilcoxon_W": w_stat,
        "wilcoxon_p": w_p,
        "cohens_dz": d_z,
    })

    print(f"\nCorrect vs {incorrect_cat}")
    print(f"  N pairs              : {len(pair)}")
    print(f"  Correct mean         : {correct.mean():.4f}")
    print(f"  Incorrect mean       : {incorrect.mean():.4f}")
    print(f"  Mean difference      : {diff.mean():+.4f}")
    print(f"  95% CI               : [{ci_low:.4f}, {ci_high:.4f}]")
    print(f"  Paired t-test        : t={t_stat:.4f}, p={t_p:.6f}")
    print(f"  Wilcoxon signed-rank : W={w_stat:.4f}, p={w_p:.6f}")
    print(f"  Cohen's dz           : {d_z:.4f}")

# ------------------------------------------------------------
# Overall correct vs all incorrect observations
# This reproduces the main binary comparison, but the paired
# category tests above should be preferred for inference.
# ------------------------------------------------------------
correct_all = df.loc[df["category"] == "correct", "average_score"].to_numpy()
incorrect_all = df.loc[df["category"] != "correct", "average_score"].to_numpy()

t_ind, p_ind = stats.ttest_ind(correct_all, incorrect_all, equal_var=False)

# Welch Cohen's d
n1, n2 = len(correct_all), len(incorrect_all)
s1, s2 = correct_all.std(ddof=1), incorrect_all.std(ddof=1)
pooled_sd = np.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
d_ind = (correct_all.mean() - incorrect_all.mean()) / pooled_sd

print("\n" + "=" * 72)
print("OVERALL CORRECT VS INCORRECT")
print("=" * 72)
print(f"Correct N            : {n1}")
print(f"Incorrect N          : {n2}")
print(f"Correct mean         : {correct_all.mean():.4f}")
print(f"Incorrect mean       : {incorrect_all.mean():.4f}")
print(f"Mean difference      : {correct_all.mean() - incorrect_all.mean():+.4f}")
print(f"Welch t-test         : t={t_ind:.4f}, p={p_ind:.6f}")
print(f"Cohen's d            : {d_ind:.4f}")

# ------------------------------------------------------------
# One-way ANOVA + Kruskal-Wallis across the four categories
# ------------------------------------------------------------
groups = [
    df.loc[df["category"] == cat, "average_score"].dropna().to_numpy()
    for cat in categories
]

f_stat, anova_p = stats.f_oneway(*groups)
h_stat, kw_p = stats.kruskal(*groups)

print("\n" + "=" * 72)
print("FOUR-CATEGORY GLOBAL TEST")
print("=" * 72)
print(f"One-way ANOVA      : F={f_stat:.4f}, p={anova_p:.6f}")
print(f"Kruskal-Wallis     : H={h_stat:.4f}, p={kw_p:.6f}")

# ------------------------------------------------------------
# Multiple-comparison correction for the 3 paired tests
# Bonferroni correction
# ------------------------------------------------------------
res = pd.DataFrame(results)
res["paired_t_p_bonferroni"] = np.minimum(res["paired_t_p"] * 3, 1.0)
res["wilcoxon_p_bonferroni"] = np.minimum(res["wilcoxon_p"] * 3, 1.0)

print("\n" + "=" * 72)
print("MULTIPLE-COMPARISON CORRECTION")
print("=" * 72)
print(
    res[
        [
            "comparison",
            "paired_t_p",
            "paired_t_p_bonferroni",
            "wilcoxon_p",
            "wilcoxon_p_bonferroni",
            "cohens_dz",
        ]
    ].to_string(index=False, float_format=lambda x: f"{x:.6f}")
)

# ------------------------------------------------------------
# Save results
# ------------------------------------------------------------
res.to_csv(OUTPUT, index=False)

print("\n" + "=" * 72)
print("STATISTICAL ANALYSIS COMPLETE")
print("=" * 72)
print(f"Results saved to: {OUTPUT}")
