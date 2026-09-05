import pandas as pd
import numpy as np
from scipy import stats


# ============================================================
# FILES
# ============================================================

GEMMA_FILE = "gemma_mgsm_100_adjudicated.csv"
QWEN_FILE = "qwen_mgsm_100_adjudicated.csv"

SUMMARY_OUTPUT = "mgsm_100_cross_model_summary.csv"
PROBLEM_OUTPUT = "mgsm_100_cross_model_problem_analysis.csv"

BOOTSTRAP_SAMPLES = 20000
PERMUTATION_SAMPLES = 20000
SEED = 42


# ============================================================
# LOAD
# ============================================================

print("=" * 80)
print("CROSS-MODEL ARABIC-ENGLISH MGSM-100 ANALYSIS")
print("=" * 80)


gemma = pd.read_csv(
    GEMMA_FILE,
    encoding="utf-8-sig",
)

qwen = pd.read_csv(
    QWEN_FILE,
    encoding="utf-8-sig",
)


# ============================================================
# NORMALIZE
# ============================================================

def prepare(df, model_name):

    df = df.copy()

    df["problem_id"] = pd.to_numeric(
        df["problem_id"],
        errors="raise",
    ).astype(int)

    df["language"] = (
        df["language"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["manual_is_correct"] = pd.to_numeric(
        df["manual_is_correct"],
        errors="raise",
    ).astype(int)

    if len(df) != 200:
        raise RuntimeError(
            f"{model_name}: expected 200 rows, found {len(df)}"
        )

    if (
        (df["language"] == "arabic").sum()
        != 100
    ):
        raise RuntimeError(
            f"{model_name}: expected 100 Arabic rows."
        )

    if (
        (df["language"] == "english").sum()
        != 100
    ):
        raise RuntimeError(
            f"{model_name}: expected 100 English rows."
        )

    return df


gemma = prepare(
    gemma,
    "Gemma",
)

qwen = prepare(
    qwen,
    "Qwen",
)


# ============================================================
# BUILD ONE ROW PER PROBLEM
# ============================================================

def build_pairs(df, prefix):

    ar = (
        df[
            df["language"] == "arabic"
        ][
            [
                "problem_id",
                "manual_is_correct",
            ]
        ]
        .rename(
            columns={
                "manual_is_correct":
                    f"{prefix}_arabic"
            }
        )
    )

    en = (
        df[
            df["language"] == "english"
        ][
            [
                "problem_id",
                "manual_is_correct",
            ]
        ]
        .rename(
            columns={
                "manual_is_correct":
                    f"{prefix}_english"
            }
        )
    )

    paired = pd.merge(
        ar,
        en,
        on="problem_id",
        validate="one_to_one",
    )

    paired[
        f"{prefix}_language_gap"
    ] = (
        paired[
            f"{prefix}_english"
        ]
        -
        paired[
            f"{prefix}_arabic"
        ]
    )

    return paired


gemma_pairs = build_pairs(
    gemma,
    "gemma",
)

qwen_pairs = build_pairs(
    qwen,
    "qwen",
)


combined = pd.merge(
    gemma_pairs,
    qwen_pairs,
    on="problem_id",
    validate="one_to_one",
)


if len(combined) != 100:
    raise RuntimeError(
        f"Expected 100 matched problems, found {len(combined)}."
    )


# ============================================================
# MODEL SUMMARY FUNCTION
# ============================================================

def model_summary(
    df,
    prefix,
    model_name,
):

    arabic = int(
        df[
            f"{prefix}_arabic"
        ].sum()
    )

    english = int(
        df[
            f"{prefix}_english"
        ].sum()
    )

    arabic_accuracy = arabic / 100
    english_accuracy = english / 100

    gap = (
        english_accuracy
        -
        arabic_accuracy
    )

    both_correct = int(
        (
            (df[f"{prefix}_arabic"] == 1)
            &
            (df[f"{prefix}_english"] == 1)
        ).sum()
    )

    both_wrong = int(
        (
            (df[f"{prefix}_arabic"] == 0)
            &
            (df[f"{prefix}_english"] == 0)
        ).sum()
    )

    english_only = int(
        (
            (df[f"{prefix}_arabic"] == 0)
            &
            (df[f"{prefix}_english"] == 1)
        ).sum()
    )

    arabic_only = int(
        (
            (df[f"{prefix}_arabic"] == 1)
            &
            (df[f"{prefix}_english"] == 0)
        ).sum()
    )

    discordant = (
        english_only
        +
        arabic_only
    )

    if discordant:

        p = stats.binomtest(
            min(
                english_only,
                arabic_only,
            ),
            discordant,
            p=0.5,
            alternative="two-sided",
        ).pvalue

    else:
        p = 1.0

    return {
        "model":
            model_name,

        "arabic_correct":
            arabic,

        "arabic_accuracy":
            arabic_accuracy,

        "english_correct":
            english,

        "english_accuracy":
            english_accuracy,

        "english_minus_arabic":
            gap,

        "both_correct":
            both_correct,

        "both_wrong":
            both_wrong,

        "english_only":
            english_only,

        "arabic_only":
            arabic_only,

        "mcnemar_exact_p":
            p,
    }


gemma_summary = model_summary(
    combined,
    "gemma",
    "Gemma-3-1B-IT",
)

qwen_summary = model_summary(
    combined,
    "qwen",
    "Qwen2.5-Math-1.5B-Instruct",
)


# ============================================================
# PRINT MAIN RESULTS
# ============================================================

print("\n" + "=" * 80)
print("MODEL RESULTS")
print("=" * 80)


for result in [
    gemma_summary,
    qwen_summary,
]:

    print(
        f"\n{result['model']}"
    )

    print(
        f"Arabic : "
        f"{result['arabic_correct']}/100 "
        f"= {result['arabic_accuracy']:.2%}"
    )

    print(
        f"English: "
        f"{result['english_correct']}/100 "
        f"= {result['english_accuracy']:.2%}"
    )

    print(
        f"Gap: "
        f"{result['english_minus_arabic']:+.2%}"
    )

    print(
        f"McNemar p: "
        f"{result['mcnemar_exact_p']:.16g}"
    )


# ============================================================
# DIFFERENCE IN LANGUAGE GAPS
#
# For each problem:
#
# model gap =
# English correctness - Arabic correctness
#
# Then compare Qwen's language gap against Gemma's
# on exactly the same problems.
# ============================================================

combined[
    "qwen_minus_gemma_gap"
] = (
    combined[
        "qwen_language_gap"
    ]
    -
    combined[
        "gemma_language_gap"
    ]
)


gap_difference = float(
    combined[
        "qwen_minus_gemma_gap"
    ].mean()
)


print("\n" + "=" * 80)
print("MODEL DIFFERENCE IN LANGUAGE GAP")
print("=" * 80)


print(
    "\nGemma English-Arabic gap:",
    f"{gemma_summary['english_minus_arabic']:.4f}",
)


print(
    "Qwen English-Arabic gap :",
    f"{qwen_summary['english_minus_arabic']:.4f}",
)


print(
    "\nQwen gap - Gemma gap:",
    f"{gap_difference:+.4f}",
)


# ============================================================
# PAIRED BOOTSTRAP CI FOR DIFFERENCE IN GAPS
# ============================================================

rng = np.random.default_rng(
    SEED
)


gap_diffs = combined[
    "qwen_minus_gemma_gap"
].to_numpy(
    dtype=float
)


bootstrap = np.empty(
    BOOTSTRAP_SAMPLES
)


for i in range(
    BOOTSTRAP_SAMPLES
):

    sample = rng.choice(
        gap_diffs,
        size=len(gap_diffs),
        replace=True,
    )

    bootstrap[i] = (
        sample.mean()
    )


ci_low = float(
    np.percentile(
        bootstrap,
        2.5,
    )
)


ci_high = float(
    np.percentile(
        bootstrap,
        97.5,
    )
)


print(
    "\nPaired bootstrap 95% CI:"
)

print(
    f"[{ci_low:.4f}, {ci_high:.4f}]"
)


# ============================================================
# PAIRED RANDOMIZATION TEST
#
# Null:
# The magnitude of the language gap does not differ
# systematically between Qwen and Gemma.
#
# Under the null we randomly flip the sign of each
# per-problem model difference.
# ============================================================

observed = abs(
    gap_difference
)


permutation_values = np.empty(
    PERMUTATION_SAMPLES
)


for i in range(
    PERMUTATION_SAMPLES
):

    signs = rng.choice(
        [-1, 1],
        size=len(gap_diffs),
    )

    permutation_values[i] = abs(
        np.mean(
            gap_diffs * signs
        )
    )


permutation_p = (
    np.sum(
        permutation_values
        >= observed
    )
    + 1
) / (
    PERMUTATION_SAMPLES
    + 1
)


print(
    "\nPaired randomization p-value:",
    f"{permutation_p:.8f}",
)


# ============================================================
# SUCCESS PATTERNS ACROSS MODELS
# ============================================================

print("\n" + "=" * 80)
print("ARABIC CROSS-MODEL SUCCESS")
print("=" * 80)


both_arabic_correct = int(
    (
        (combined["gemma_arabic"] == 1)
        &
        (combined["qwen_arabic"] == 1)
    ).sum()
)


gemma_only_arabic = int(
    (
        (combined["gemma_arabic"] == 1)
        &
        (combined["qwen_arabic"] == 0)
    ).sum()
)


qwen_only_arabic = int(
    (
        (combined["gemma_arabic"] == 0)
        &
        (combined["qwen_arabic"] == 1)
    ).sum()
)


neither_arabic = int(
    (
        (combined["gemma_arabic"] == 0)
        &
        (combined["qwen_arabic"] == 0)
    ).sum()
)


print(
    "\nBoth models correct in Arabic:",
    both_arabic_correct
)

print(
    "Gemma only correct in Arabic:",
    gemma_only_arabic
)

print(
    "Qwen only correct in Arabic:",
    qwen_only_arabic
)

print(
    "Neither correct in Arabic:",
    neither_arabic
)


# ============================================================
# ENGLISH CROSS-MODEL SUCCESS
# ============================================================

print("\n" + "=" * 80)
print("ENGLISH CROSS-MODEL SUCCESS")
print("=" * 80)


both_english_correct = int(
    (
        (combined["gemma_english"] == 1)
        &
        (combined["qwen_english"] == 1)
    ).sum()
)


gemma_only_english = int(
    (
        (combined["gemma_english"] == 1)
        &
        (combined["qwen_english"] == 0)
    ).sum()
)


qwen_only_english = int(
    (
        (combined["gemma_english"] == 0)
        &
        (combined["qwen_english"] == 1)
    ).sum()
)


neither_english = int(
    (
        (combined["gemma_english"] == 0)
        &
        (combined["qwen_english"] == 0)
    ).sum()
)


print(
    "\nBoth models correct in English:",
    both_english_correct
)

print(
    "Gemma only correct in English:",
    gemma_only_english
)

print(
    "Qwen only correct in English:",
    qwen_only_english
)

print(
    "Neither correct in English:",
    neither_english
)


# ============================================================
# SAVE SUMMARY
# ============================================================

summary = pd.DataFrame(
    [
        gemma_summary,
        qwen_summary,
    ]
)


summary[
    "cross_model_gap_difference"
] = np.nan

summary[
    "cross_model_gap_ci_low"
] = np.nan

summary[
    "cross_model_gap_ci_high"
] = np.nan

summary[
    "cross_model_gap_randomization_p"
] = np.nan


summary.loc[
    summary["model"]
    ==
    "Qwen2.5-Math-1.5B-Instruct",
    "cross_model_gap_difference",
] = gap_difference


summary.loc[
    summary["model"]
    ==
    "Qwen2.5-Math-1.5B-Instruct",
    "cross_model_gap_ci_low",
] = ci_low


summary.loc[
    summary["model"]
    ==
    "Qwen2.5-Math-1.5B-Instruct",
    "cross_model_gap_ci_high",
] = ci_high


summary.loc[
    summary["model"]
    ==
    "Qwen2.5-Math-1.5B-Instruct",
    "cross_model_gap_randomization_p",
] = permutation_p


summary.to_csv(
    SUMMARY_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)


combined.to_csv(
    PROBLEM_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)


print("\n" + "=" * 80)
print("FILES CREATED")
print("=" * 80)


print(
    "\n",
    SUMMARY_OUTPUT
)

print(
    " ",
    PROBLEM_OUTPUT
)