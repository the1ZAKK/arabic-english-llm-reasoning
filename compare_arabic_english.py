import pandas as pd
import numpy as np
from scipy import stats


# ============================================================
# CONFIGURATION
# ============================================================

ARABIC_FILE = "arabic_prm_results.csv"
ENGLISH_FILE = "english_prm_results.csv"

OUTPUT_FILE = "arabic_english_comparison.csv"


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 70)
print("ARABIC vs ENGLISH PRM COMPARISON")
print("=" * 70)

print("\nLoading results...")

arabic = pd.read_csv(ARABIC_FILE)
english = pd.read_csv(ENGLISH_FILE)

print("Arabic rows :", len(arabic))
print("English rows:", len(english))


# ============================================================
# DISPLAY COLUMNS
# ============================================================

print("\nArabic columns:")
print(list(arabic.columns))

print("\nEnglish columns:")
print(list(english.columns))


# ============================================================
# FIND REQUIRED COLUMNS
# ============================================================

def find_column(df, candidates):
    for candidate in candidates:
        if candidate in df.columns:
            return candidate

    # Case-insensitive search
    lower_map = {c.lower(): c for c in df.columns}

    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]

    return None


id_ar = find_column(
    arabic,
    ["id", "problem_id", "problem", "example_id"]
)

id_en = find_column(
    english,
    ["id", "problem_id", "problem", "example_id"]
)

category_ar = find_column(
    arabic,
    ["category", "type", "label"]
)

category_en = find_column(
    english,
    ["category", "type", "label"]
)

score_ar = find_column(
    arabic,
    ["average_score", "avg_score", "score", "mean_score", "average"]
)

score_en = find_column(
    english,
    ["average_score", "avg_score", "score", "mean_score", "average"]
)


print("\nDetected columns:")
print("Arabic ID      :", id_ar)
print("English ID     :", id_en)
print("Arabic category:", category_ar)
print("English category:", category_en)
print("Arabic score   :", score_ar)
print("English score  :", score_en)


if score_ar is None or score_en is None:
    raise ValueError(
        "\nCould not identify score columns.\n"
        "Please show the first 10 lines of both CSV files."
    )

if category_ar is None or category_en is None:
    raise ValueError(
        "\nCould not identify category columns.\n"
        "Please show the first 10 lines of both CSV files."
    )


# ============================================================
# NORMALIZE DATA
# ============================================================

arabic[score_ar] = pd.to_numeric(
    arabic[score_ar],
    errors="coerce"
)

english[score_en] = pd.to_numeric(
    english[score_en],
    errors="coerce"
)

arabic[category_ar] = arabic[category_ar].astype(str).str.strip().str.lower()
english[category_en] = english[category_en].astype(str).str.strip().str.lower()


# ============================================================
# CATEGORY SUMMARY
# ============================================================

categories = [
    "correct",
    "arithmetic_error",
    "logic_error",
    "completely_wrong"
]


print("\n" + "=" * 70)
print("CATEGORY MEANS")
print("=" * 70)

summary_rows = []

for category in categories:

    ar_values = arabic.loc[
        arabic[category_ar] == category,
        score_ar
    ].dropna()

    en_values = english.loc[
        english[category_en] == category,
        score_en
    ].dropna()

    print(f"\n{category}")

    print(f"  Arabic N : {len(ar_values)}")
    print(f"  English N: {len(en_values)}")

    if len(ar_values) > 0:
        print(f"  Arabic mean : {ar_values.mean():.4f}")
        print(f"  Arabic std  : {ar_values.std(ddof=1):.4f}")

    if len(en_values) > 0:
        print(f"  English mean: {en_values.mean():.4f}")
        print(f"  English std : {en_values.std(ddof=1):.4f}")

    if len(ar_values) > 0 and len(en_values) > 0:

        difference = en_values.mean() - ar_values.mean()

        print(f"  English - Arabic: {difference:+.4f}")

        # Welch t-test
        t_stat, p_value = stats.ttest_ind(
            en_values,
            ar_values,
            equal_var=False
        )

        # Mann-Whitney U
        u_stat, mw_p = stats.mannwhitneyu(
            en_values,
            ar_values,
            alternative="two-sided"
        )

        print(f"  Welch t-test : t={t_stat:.4f}, p={p_value:.6f}")
        print(f"  Mann-Whitney : U={u_stat:.4f}, p={mw_p:.6f}")

        summary_rows.append({
            "category": category,
            "arabic_n": len(ar_values),
            "english_n": len(en_values),
            "arabic_mean": ar_values.mean(),
            "english_mean": en_values.mean(),
            "english_minus_arabic": difference,
            "welch_t": t_stat,
            "welch_p": p_value,
            "mann_whitney_u": u_stat,
            "mann_whitney_p": mw_p
        })


# ============================================================
# PAIRED ANALYSIS
# ============================================================

print("\n" + "=" * 70)
print("PAIRED ARABIC vs ENGLISH ANALYSIS")
print("=" * 70)

paired_rows = []

if id_ar is not None and id_en is not None:

    for category in categories:

        ar_cat = arabic[
            arabic[category_ar] == category
        ][[id_ar, score_ar]].copy()

        en_cat = english[
            english[category_en] == category
        ][[id_en, score_en]].copy()

        ar_cat.columns = ["problem_id", "arabic_score"]
        en_cat.columns = ["problem_id", "english_score"]

        # Convert problem IDs if possible
        ar_cat["problem_id"] = ar_cat["problem_id"].astype(str)
        en_cat["problem_id"] = en_cat["problem_id"].astype(str)

        merged = pd.merge(
            ar_cat,
            en_cat,
            on="problem_id",
            how="inner"
        ).dropna()

        if len(merged) < 2:
            print(f"\n{category}: insufficient paired observations")
            continue

        ar_scores = merged["arabic_score"].to_numpy()
        en_scores = merged["english_score"].to_numpy()

        differences = en_scores - ar_scores

        mean_difference = differences.mean()

        # Paired t-test
        t_stat, p_value = stats.ttest_rel(
            en_scores,
            ar_scores
        )

        # Wilcoxon
        try:
            w_stat, w_p = stats.wilcoxon(
                en_scores,
                ar_scores
            )
        except ValueError:
            w_stat, w_p = np.nan, np.nan

        # Cohen's dz
        diff_std = differences.std(ddof=1)

        if diff_std > 0:
            cohens_dz = mean_difference / diff_std
        else:
            cohens_dz = np.nan

        # 95% CI
        se = diff_std / np.sqrt(len(differences))

        if len(differences) > 1:
            t_critical = stats.t.ppf(
                0.975,
                df=len(differences) - 1
            )

            ci_low = mean_difference - t_critical * se
            ci_high = mean_difference + t_critical * se
        else:
            ci_low = np.nan
            ci_high = np.nan

        print(f"\n{category}")

        print(f"  Paired N              : {len(merged)}")
        print(f"  Arabic mean           : {ar_scores.mean():.4f}")
        print(f"  English mean          : {en_scores.mean():.4f}")
        print(f"  English - Arabic      : {mean_difference:+.4f}")

        print(
            f"  95% CI                : "
            f"[{ci_low:.4f}, {ci_high:.4f}]"
        )

        print(
            f"  Paired t-test         : "
            f"t={t_stat:.4f}, p={p_value:.6f}"
        )

        print(
            f"  Wilcoxon signed-rank  : "
            f"W={w_stat:.4f}, p={w_p:.6f}"
        )

        print(
            f"  Cohen's dz            : "
            f"{cohens_dz:.4f}"
        )

        paired_rows.append({
            "category": category,
            "paired_n": len(merged),
            "arabic_mean": ar_scores.mean(),
            "english_mean": en_scores.mean(),
            "english_minus_arabic": mean_difference,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "paired_t": t_stat,
            "paired_t_p": p_value,
            "wilcoxon_w": w_stat,
            "wilcoxon_p": w_p,
            "cohens_dz": cohens_dz
        })


# ============================================================
# OVERALL CORRECT vs INCORRECT
# ============================================================

print("\n" + "=" * 70)
print("OVERALL CORRECT vs INCORRECT")
print("=" * 70)


def get_category_values(df, category_col, score_col, category_list):

    mask = df[category_col].isin(category_list)

    return df.loc[mask, score_col].dropna()


ar_correct = get_category_values(
    arabic,
    category_ar,
    score_ar,
    ["correct"]
)

ar_incorrect = get_category_values(
    arabic,
    category_ar,
    score_ar,
    [
        "arithmetic_error",
        "logic_error",
        "completely_wrong"
    ]
)

en_correct = get_category_values(
    english,
    category_en,
    score_en,
    ["correct"]
)

en_incorrect = get_category_values(
    english,
    category_en,
    score_en,
    [
        "arithmetic_error",
        "logic_error",
        "completely_wrong"
    ]
)


print("\nArabic:")
print(f"  Correct mean   : {ar_correct.mean():.4f}")
print(f"  Incorrect mean : {ar_incorrect.mean():.4f}")
print(f"  Difference     : {ar_correct.mean() - ar_incorrect.mean():+.4f}")

print("\nEnglish:")
print(f"  Correct mean   : {en_correct.mean():.4f}")
print(f"  Incorrect mean : {en_incorrect.mean():.4f}")
print(f"  Difference     : {en_correct.mean() - en_incorrect.mean():+.4f}")


# ============================================================
# DISCRIMINATION GAP
# ============================================================

arabic_gap = ar_correct.mean() - ar_incorrect.mean()
english_gap = en_correct.mean() - en_incorrect.mean()

gap_difference = english_gap - arabic_gap

print("\n" + "=" * 70)
print("PRM DISCRIMINATION GAP")
print("=" * 70)

print(f"\nArabic discrimination gap : {arabic_gap:+.4f}")
print(f"English discrimination gap: {english_gap:+.4f}")
print(f"English - Arabic gap       : {gap_difference:+.4f}")


# ============================================================
# SAVE CATEGORY RESULTS
# ============================================================

if summary_rows:

    summary_df = pd.DataFrame(summary_rows)

    summary_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\nCategory comparison saved to:")
    print(OUTPUT_FILE)


# ============================================================
# SAVE PAIRED RESULTS
# ============================================================

if paired_rows:

    paired_output = "arabic_english_paired_comparison.csv"

    paired_df = pd.DataFrame(paired_rows)

    paired_df.to_csv(
        paired_output,
        index=False
    )

    print("Paired comparison saved to:")
    print(paired_output)


# ============================================================
# FINAL INTERPRETATION
# ============================================================

print("\n" + "=" * 70)
print("INTERPRETATION")
print("=" * 70)

print("""
The key quantity is the Correct-vs-Incorrect discrimination gap.

A larger gap means that the PRM is better at distinguishing
correct reasoning from incorrect reasoning.

We therefore compare:

    English gap
    Arabic gap

If the English gap is substantially larger than the Arabic gap,
this provides evidence that the PRM has weaker discrimination
performance on Arabic than on English.

However, this alone does NOT prove that all LLMs are worse
at Arabic reasoning. It specifically tests whether this PRM's
evaluation behavior differs between Arabic and English.

The strongest evidence will come from the paired statistical
tests and confidence intervals above.
""")

print("=" * 70)
print("COMPARISON COMPLETE")
print("=" * 70)