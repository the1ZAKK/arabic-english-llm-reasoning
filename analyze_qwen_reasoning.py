import pandas as pd
import numpy as np
from scipy import stats


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "qwen_reasoning_results.csv"

ADJUDICATED_OUTPUT = "qwen_reasoning_adjudicated.csv"

SUMMARY_OUTPUT = "qwen_reasoning_statistical_summary.csv"

PAIR_OUTPUT = "qwen_reasoning_paired_results.csv"

RANDOM_SEED = 42

BOOTSTRAP_SAMPLES = 10000


# ============================================================
# MANUAL ADJUDICATION
# ============================================================

# Format:
#
# ("language", problem_id): {
#     "is_correct": 0 or 1,
#     "error_type": "...",
#     "note": "..."
# }
#
# IMPORTANT:
# Only override cases that have actually been manually inspected.
#
# Problem 11 Arabic:
# The response contains the correct calculation 9 + 4 = 13.
# The automatic extractor incorrectly selected a later number (16).
#
# Therefore this is an ANSWER EXTRACTION ERROR, not a reasoning error.

MANUAL_OVERRIDES = {

    ("arabic", 11): {
        "is_correct": 1,
        "error_type": "answer_extraction_error",
        "note": (
            "Manual review: model explicitly computed "
            "9 + 4 = 13 correctly, but automatic fallback "
            "extracted a later number (16)."
        ),
    },

}


# ============================================================
# OPTIONAL ERROR LABELS FOR INSPECTED ARABIC FAILURES
# ============================================================

# These labels do NOT change correctness.
# They simply help describe the type of Arabic failure observed.
#
# You can edit these labels later after further manual review.

ARABIC_ERROR_TYPES = {

    1: "language_generation_failure",

    2: "problem_misunderstanding",

    3: "problem_misunderstanding",

    4: "language_generation_failure",

    6: "problem_misunderstanding",

    7: "problem_misunderstanding",

    8: "reasoning_error",

    10: "no_valid_answer",

    # Problem 11 is corrected above.

    12: "language_generation_failure",

    13: "language_generation_failure",

    14: "problem_misunderstanding",

    15: "problem_misunderstanding",

}


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 72)
print("QWEN ARABIC vs ENGLISH REASONING ANALYSIS")
print("=" * 72)


print("\nLoading:")
print(INPUT_FILE)


df = pd.read_csv(
    INPUT_FILE
)


print(
    "\nRows loaded:",
    len(df)
)


# ============================================================
# VALIDATE REQUIRED COLUMNS
# ============================================================

required_columns = [

    "problem_id",

    "language",

    "expected_answer",

    "extracted_answer",

    "is_correct",

    "generated_response",

    "status",

]


missing_columns = [

    column

    for column in required_columns

    if column not in df.columns

]


if missing_columns:

    raise RuntimeError(
        f"Missing required columns: "
        f"{missing_columns}"
    )


# ============================================================
# NORMALIZE TYPES
# ============================================================

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


df["is_correct"] = pd.to_numeric(
    df["is_correct"],
    errors="coerce",
).fillna(0).astype(int)


# ============================================================
# CHECK DATASET SIZE
# ============================================================

print("\nValidating experiment structure...")


arabic_rows = df[
    df["language"] == "arabic"
]


english_rows = df[
    df["language"] == "english"
]


print(
    "Arabic rows :",
    len(arabic_rows)
)

print(
    "English rows:",
    len(english_rows)
)


if len(arabic_rows) != 20:

    raise RuntimeError(
        "Expected exactly 20 Arabic rows."
    )


if len(english_rows) != 20:

    raise RuntimeError(
        "Expected exactly 20 English rows."
    )


if len(df) != 40:

    raise RuntimeError(
        "Expected exactly 40 total evaluations."
    )


print(
    "Dataset validation successful."
)


# ============================================================
# PRESERVE AUTOMATIC RESULTS
# ============================================================

df["automatic_is_correct"] = (
    df["is_correct"]
)


df["manual_is_correct"] = (
    df["automatic_is_correct"]
)


df["error_type"] = np.where(
    df["automatic_is_correct"] == 1,
    "correct",
    "unreviewed_failure",
)


df["manual_note"] = ""


# ============================================================
# ADD ERROR LABELS
# ============================================================

for problem_id, error_type in ARABIC_ERROR_TYPES.items():

    mask = (

        (df["language"] == "arabic")

        &

        (df["problem_id"] == problem_id)

        &

        (df["automatic_is_correct"] == 0)

    )


    df.loc[
        mask,
        "error_type"
    ] = error_type


# ============================================================
# APPLY MANUAL OVERRIDES
# ============================================================

print("\n" + "=" * 72)
print("APPLYING MANUAL ADJUDICATION")
print("=" * 72)


for (
    language,
    problem_id
), override in MANUAL_OVERRIDES.items():


    mask = (

        (df["language"] == language)

        &

        (df["problem_id"] == problem_id)

    )


    matching = df[
        mask
    ]


    if len(matching) != 1:

        raise RuntimeError(
            f"Expected exactly one row for "
            f"{language} Problem {problem_id}, "
            f"found {len(matching)}."
        )


    old_value = int(
        matching[
            "automatic_is_correct"
        ].iloc[0]
    )


    new_value = int(
        override[
            "is_correct"
        ]
    )


    df.loc[
        mask,
        "manual_is_correct"
    ] = new_value


    df.loc[
        mask,
        "error_type"
    ] = override[
        "error_type"
    ]


    df.loc[
        mask,
        "manual_note"
    ] = override[
        "note"
    ]


    print(
        f"\n{language.upper()} "
        f"Problem {problem_id}"
    )

    print(
        f"Automatic correctness: "
        f"{old_value}"
    )

    print(
        f"Manual correctness   : "
        f"{new_value}"
    )

    print(
        "Classification       :",
        override["error_type"]
    )


# ============================================================
# CORRECT AUTOMATIC-VS-MANUAL SUMMARY
# ============================================================

print("\n" + "=" * 72)
print("AUTOMATIC vs MANUAL SCORING")
print("=" * 72)


automatic_arabic = int(

    df.loc[
        df["language"] == "arabic",
        "automatic_is_correct"
    ].sum()

)


manual_arabic = int(

    df.loc[
        df["language"] == "arabic",
        "manual_is_correct"
    ].sum()

)


automatic_english = int(

    df.loc[
        df["language"] == "english",
        "automatic_is_correct"
    ].sum()

)


manual_english = int(

    df.loc[
        df["language"] == "english",
        "manual_is_correct"
    ].sum()

)


print(
    f"\nArabic automatic: "
    f"{automatic_arabic}/20"
)

print(
    f"Arabic adjudicated: "
    f"{manual_arabic}/20"
)

print(
    f"\nEnglish automatic: "
    f"{automatic_english}/20"
)

print(
    f"English adjudicated: "
    f"{manual_english}/20"
)


# ============================================================
# LANGUAGE ACCURACY
# ============================================================

arabic_accuracy = (
    manual_arabic
    / 20
)


english_accuracy = (
    manual_english
    / 20
)


accuracy_gap = (
    english_accuracy
    - arabic_accuracy
)


print("\n" + "=" * 72)
print("ADJUDICATED LANGUAGE ACCURACY")
print("=" * 72)


print(
    f"\nArabic accuracy : "
    f"{manual_arabic}/20 "
    f"= {arabic_accuracy:.4f}"
)


print(
    f"English accuracy: "
    f"{manual_english}/20 "
    f"= {english_accuracy:.4f}"
)


print(
    f"\nEnglish - Arabic accuracy gap: "
    f"{accuracy_gap:+.4f}"
)


print(
    f"Percentage-point difference: "
    f"{accuracy_gap * 100:+.1f} points"
)


# ============================================================
# CREATE PAIRED DATA
# ============================================================

arabic_pair = (

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
                "arabic_correct"
        }
    )

)


english_pair = (

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
                "english_correct"
        }
    )

)


paired = pd.merge(
    arabic_pair,
    english_pair,
    on="problem_id",
    how="inner",
)


if len(paired) != 20:

    raise RuntimeError(
        f"Expected 20 paired problems, "
        f"found {len(paired)}."
    )


# ============================================================
# PAIRED OUTCOME COUNTS
# ============================================================

both_correct = int(

    (
        (paired["arabic_correct"] == 1)
        &
        (paired["english_correct"] == 1)
    ).sum()

)


both_wrong = int(

    (
        (paired["arabic_correct"] == 0)
        &
        (paired["english_correct"] == 0)
    ).sum()

)


english_only = int(

    (
        (paired["arabic_correct"] == 0)
        &
        (paired["english_correct"] == 1)
    ).sum()

)


arabic_only = int(

    (
        (paired["arabic_correct"] == 1)
        &
        (paired["english_correct"] == 0)
    ).sum()

)


print("\n" + "=" * 72)
print("PAIRED OUTCOMES")
print("=" * 72)


print(
    "\nBoth correct:",
    both_correct
)

print(
    "Both wrong:",
    both_wrong
)

print(
    "English correct / Arabic wrong:",
    english_only
)

print(
    "Arabic correct / English wrong:",
    arabic_only
)


# ============================================================
# EXACT MCNEMAR TEST
# ============================================================

print("\n" + "=" * 72)
print("EXACT MCNEMAR TEST")
print("=" * 72)


discordant = (
    english_only
    + arabic_only
)


if discordant == 0:

    mcnemar_p = 1.0

else:

    # Under H0, either direction among discordant pairs
    # is equally likely with probability 0.5.

    mcnemar_result = stats.binomtest(

        min(
            english_only,
            arabic_only
        ),

        n=discordant,

        p=0.5,

        alternative="two-sided",

    )


    mcnemar_p = (
        mcnemar_result.pvalue
    )


print(
    f"\nDiscordant pairs: "
    f"{discordant}"
)


print(
    f"English-only successes: "
    f"{english_only}"
)


print(
    f"Arabic-only successes : "
    f"{arabic_only}"
)


print(
    f"\nExact two-sided p-value: "
    f"{mcnemar_p:.10f}"
)


# ============================================================
# PAIRED DIFFERENCES
# ============================================================

paired[
    "english_minus_arabic"
] = (

    paired[
        "english_correct"
    ]

    -

    paired[
        "arabic_correct"
    ]

)


observed_difference = (

    paired[
        "english_minus_arabic"
    ].mean()

)


# ============================================================
# BOOTSTRAP CONFIDENCE INTERVAL
# ============================================================

print("\n" + "=" * 72)
print("BOOTSTRAP 95% CONFIDENCE INTERVAL")
print("=" * 72)


rng = np.random.default_rng(
    RANDOM_SEED
)


pair_differences = (

    paired[
        "english_minus_arabic"
    ]
    .to_numpy(
        dtype=float
    )

)


bootstrap_means = np.empty(
    BOOTSTRAP_SAMPLES
)


n = len(
    pair_differences
)


for i in range(
    BOOTSTRAP_SAMPLES
):


    sample = rng.choice(

        pair_differences,

        size=n,

        replace=True,

    )


    bootstrap_means[i] = (
        sample.mean()
    )


ci_low = float(
    np.percentile(
        bootstrap_means,
        2.5
    )
)


ci_high = float(
    np.percentile(
        bootstrap_means,
        97.5
    )
)


print(
    f"\nObserved accuracy difference: "
    f"{observed_difference:+.4f}"
)


print(
    f"95% bootstrap CI: "
    f"[{ci_low:.4f}, {ci_high:.4f}]"
)


# ============================================================
# PER-PROBLEM RESULTS
# ============================================================

print("\n" + "=" * 72)
print("FINAL PAIRED PROBLEM RESULTS")
print("=" * 72)


for _, row in paired.iterrows():


    print(

        f"Problem "
        f"{int(row['problem_id']):2d}: "

        f"Arabic="
        f"{int(row['arabic_correct'])} | "

        f"English="
        f"{int(row['english_correct'])}"

    )


# ============================================================
# ARABIC ERROR ANALYSIS
# ============================================================

print("\n" + "=" * 72)
print("ARABIC ERROR ANALYSIS")
print("=" * 72)


arabic_failures = df[

    (df["language"] == "arabic")

    &

    (df["manual_is_correct"] == 0)

].copy()


error_counts = (

    arabic_failures[
        "error_type"
    ]
    .value_counts()
)


print(
    f"\nRemaining Arabic failures: "
    f"{len(arabic_failures)}"
)


for error_type, count in error_counts.items():

    print(
        f"{error_type:30s}: "
        f"{count}"
    )


# ============================================================
# SHOW FAILURE IDS
# ============================================================

print("\nArabic failure details:")


for _, row in arabic_failures.iterrows():


    print(

        f"Problem "
        f"{int(row['problem_id']):2d}: "

        f"{row['error_type']}"

    )


# ============================================================
# SAVE ADJUDICATED DATA
# ============================================================

df.to_csv(
    ADJUDICATED_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)


paired.to_csv(
    PAIR_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# SAVE STATISTICAL SUMMARY
# ============================================================

summary = pd.DataFrame(
    [
        {

            "arabic_correct":
                manual_arabic,

            "arabic_total":
                20,

            "arabic_accuracy":
                arabic_accuracy,

            "english_correct":
                manual_english,

            "english_total":
                20,

            "english_accuracy":
                english_accuracy,

            "english_minus_arabic":
                accuracy_gap,

            "both_correct":
                both_correct,

            "both_wrong":
                both_wrong,

            "english_only_correct":
                english_only,

            "arabic_only_correct":
                arabic_only,

            "mcnemar_exact_p":
                mcnemar_p,

            "bootstrap_ci_low":
                ci_low,

            "bootstrap_ci_high":
                ci_high,

        }
    ]
)


summary.to_csv(
    SUMMARY_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# FINAL INTERPRETATION
# ============================================================

print("\n" + "=" * 72)
print("STATISTICAL INTERPRETATION")
print("=" * 72)


if mcnemar_p < 0.05:

    print(
        "\nThe Arabic-English difference in "
        "paired reasoning accuracy is statistically "
        "significant at alpha = 0.05."
    )

else:

    print(
        "\nThe Arabic-English difference in "
        "paired reasoning accuracy is NOT statistically "
        "significant at alpha = 0.05."
    )


if accuracy_gap > 0:

    print(
        "\nEnglish reasoning accuracy was higher "
        "than Arabic reasoning accuracy on this "
        "matched benchmark."
    )


print(
    f"\nArabic accuracy : "
    f"{arabic_accuracy:.4f}"
)


print(
    f"English accuracy: "
    f"{english_accuracy:.4f}"
)


print(
    f"Gap             : "
    f"{accuracy_gap:+.4f}"
)


print(
    f"McNemar p       : "
    f"{mcnemar_p:.10f}"
)


print(
    f"95% CI          : "
    f"[{ci_low:.4f}, {ci_high:.4f}]"
)


print(
    "\nIMPORTANT:"
)

print(
    "This result supports a language-dependent "
    "performance difference for the specific Qwen "
    "model and matched 20-problem benchmark tested."
)

print(
    "It should not be generalized to all LLMs, "
    "all Arabic reasoning tasks, or Arabic reasoning "
    "in general without testing more models and "
    "larger datasets."
)


# ============================================================
# FINISH
# ============================================================

print("\n" + "=" * 72)
print("ANALYSIS COMPLETE")
print("=" * 72)


print(
    "\nGenerated files:"
)

print(
    " ",
    ADJUDICATED_OUTPUT
)

print(
    " ",
    PAIR_OUTPUT
)

print(
    " ",
    SUMMARY_OUTPUT
)