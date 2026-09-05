import pandas as pd
import numpy as np
from scipy import stats


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "gemma_mgsm_100_results.csv"

ADJUDICATED_FILE = "gemma_mgsm_100_adjudicated.csv"
REVIEW_FILE = "gemma_mgsm_100_review_decisions.csv"
PAIRED_FILE = "gemma_mgsm_100_paired_results.csv"
SUMMARY_FILE = "gemma_mgsm_100_statistical_summary.csv"

BOOTSTRAP_SAMPLES = 10000
RANDOM_SEED = 42


# ============================================================
# MANUAL ADJUDICATION
#
# These are the 11 review cases confirmed correct after
# inspecting the full generated response.
#
# Every other case marked needs_manual_review=1 is manually
# adjudicated as incorrect.
# ============================================================

MANUALLY_CORRECT = {

    (2, "english"),

    (10, "english"),

    (22, "english"),

    (49, "english"),

    (61, "english"),

    (70, "arabic"),

    (72, "english"),

    (79, "english"),

    (80, "english"),

    (81, "english"),

    (97, "english"),
}


# ============================================================
# LOAD
# ============================================================

print("=" * 78)
print("GEMMA MGSM-100 MANUAL ADJUDICATION AND STATISTICAL ANALYSIS")
print("=" * 78)


df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig",
)


print("\nRows loaded:", len(df))


if len(df) != 200:

    raise RuntimeError(
        f"Expected 200 evaluations, found {len(df)}."
    )


# ============================================================
# NORMALIZE
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


df["needs_manual_review"] = pd.to_numeric(
    df["needs_manual_review"],
    errors="coerce",
).fillna(0).astype(int)


# ============================================================
# VERIFY MODEL
# ============================================================

if "model" in df.columns:

    print("\nModel values:")
    print(df["model"].value_counts())

    model_values = set(
        df["model"]
        .astype(str)
        .str.lower()
        .unique()
    )

    if model_values != {"gemma"}:

        raise RuntimeError(
            "This file does not appear to contain only Gemma "
            f"results. Found: {model_values}"
        )


# ============================================================
# VERIFY STRUCTURE
# ============================================================

arabic_count = (
    df["language"]
    .eq("arabic")
    .sum()
)

english_count = (
    df["language"]
    .eq("english")
    .sum()
)


print("\nArabic rows :", arabic_count)
print("English rows:", english_count)


if arabic_count != 100:
    raise RuntimeError(
        "Expected exactly 100 Arabic rows."
    )


if english_count != 100:
    raise RuntimeError(
        "Expected exactly 100 English rows."
    )


# ============================================================
# CHECK REVIEW CASES
# ============================================================

review_mask = (
    df["needs_manual_review"] == 1
)

review_df = df[
    review_mask
].copy()


print(
    "\nFlagged manual-review cases:",
    len(review_df)
)


if len(review_df) != 54:

    raise RuntimeError(
        f"Expected 54 review cases, found {len(review_df)}. "
        "Stop so manual decisions are not applied to the wrong run."
    )


review_keys = set(
    zip(
        review_df["problem_id"],
        review_df["language"],
    )
)


missing_correct_keys = (
    MANUALLY_CORRECT
    - review_keys
)


if missing_correct_keys:

    raise RuntimeError(
        "Some manually adjudicated cases are missing "
        f"from this run: {missing_correct_keys}"
    )


# ============================================================
# PRESERVE AUTOMATIC SCORING
# ============================================================

df["automatic_is_correct"] = (
    df["is_correct"]
)


df["manual_is_correct"] = (
    df["automatic_is_correct"]
)


df["manual_reviewed"] = 0

df["manual_status"] = ""

df["manual_note"] = ""


# ============================================================
# APPLY ALL 54 MANUAL DECISIONS
# ============================================================

for index, row in df[
    review_mask
].iterrows():

    key = (
        int(row["problem_id"]),
        row["language"],
    )


    automatic = int(
        row["automatic_is_correct"]
    )


    if key in MANUALLY_CORRECT:

        manual = 1

        df.at[
            index,
            "manual_status"
        ] = "correct"

        if automatic == 0:

            df.at[
                index,
                "manual_note"
            ] = (
                "Manual review confirmed that the model "
                "reached the correct gold answer; automatic "
                "answer extraction/formatting caused a false negative."
            )

        else:

            df.at[
                index,
                "manual_note"
            ] = (
                "Manual review confirmed the automatically "
                "scored correct response."
            )


    else:

        manual = 0

        df.at[
            index,
            "manual_status"
        ] = "incorrect"

        if automatic == 1:

            df.at[
                index,
                "manual_note"
            ] = (
                "Manual review found that the response did "
                "not actually solve the problem correctly. "
                "The automatic fallback produced a false positive."
            )

        else:

            df.at[
                index,
                "manual_note"
            ] = (
                "Manual review confirmed a genuine model "
                "failure, incomplete solution, or incorrect answer."
            )


    df.at[
        index,
        "manual_is_correct"
    ] = manual


    df.at[
        index,
        "manual_reviewed"
    ] = 1


# ============================================================
# SHOW CHANGES CAUSED BY ADJUDICATION
# ============================================================

changed = df[
    df["automatic_is_correct"]
    != df["manual_is_correct"]
].copy()


print("\n" + "=" * 78)
print("AUTOMATIC SCORES CHANGED BY MANUAL REVIEW")
print("=" * 78)


print(
    "\nNumber of changed cases:",
    len(changed)
)


if len(changed) > 0:

    print(
        changed[
            [
                "problem_id",
                "language",
                "gold_answer",
                "extracted_answer",
                "automatic_is_correct",
                "manual_is_correct",
            ]
        ].to_string(
            index=False
        )
    )


# ============================================================
# AUTOMATIC ACCURACY
# ============================================================

automatic_arabic = int(

    df.loc[
        df["language"] == "arabic",
        "automatic_is_correct",
    ].sum()

)


automatic_english = int(

    df.loc[
        df["language"] == "english",
        "automatic_is_correct",
    ].sum()

)


print("\n" + "=" * 78)
print("AUTOMATIC ACCURACY")
print("=" * 78)


print(
    f"\nArabic : "
    f"{automatic_arabic}/100 "
    f"= {automatic_arabic / 100:.4f}"
)


print(
    f"English: "
    f"{automatic_english}/100 "
    f"= {automatic_english / 100:.4f}"
)


# ============================================================
# ADJUDICATED ACCURACY
# ============================================================

arabic_correct = int(

    df.loc[
        df["language"] == "arabic",
        "manual_is_correct",
    ].sum()

)


english_correct = int(

    df.loc[
        df["language"] == "english",
        "manual_is_correct",
    ].sum()

)


arabic_accuracy = (
    arabic_correct
    / 100
)


english_accuracy = (
    english_correct
    / 100
)


accuracy_gap = (
    english_accuracy
    - arabic_accuracy
)


print("\n" + "=" * 78)
print("FINAL ADJUDICATED ACCURACY")
print("=" * 78)


print(
    f"\nArabic : "
    f"{arabic_correct}/100 "
    f"= {arabic_accuracy:.4f}"
)


print(
    f"English: "
    f"{english_correct}/100 "
    f"= {english_accuracy:.4f}"
)


print(
    f"\nEnglish - Arabic gap: "
    f"{accuracy_gap:+.4f}"
)


print(
    f"Percentage-point gap: "
    f"{accuracy_gap * 100:+.1f}"
)


# ============================================================
# BUILD MATCHED PAIRS
# ============================================================

arabic = (

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


english = (

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
    arabic,
    english,
    on="problem_id",
    how="inner",
)


paired = paired.sort_values(
    "problem_id"
)


if len(paired) != 100:

    raise RuntimeError(
        f"Expected 100 paired problems, "
        f"found {len(paired)}."
    )


# ============================================================
# PAIRED OUTCOMES
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


print("\n" + "=" * 78)
print("PAIRED OUTCOMES")
print("=" * 78)


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

discordant = (
    english_only
    + arabic_only
)


if discordant == 0:

    mcnemar_p = 1.0

else:

    mcnemar_p = stats.binomtest(

        min(
            english_only,
            arabic_only,
        ),

        n=discordant,

        p=0.5,

        alternative="two-sided",

    ).pvalue


print("\n" + "=" * 78)
print("EXACT MCNEMAR TEST")
print("=" * 78)


print(
    "\nDiscordant pairs:",
    discordant
)

print(
    "English-only successes:",
    english_only
)

print(
    "Arabic-only successes :",
    arabic_only
)

print(
    f"\nExact two-sided p-value: "
    f"{mcnemar_p:.12f}"
)


# ============================================================
# PAIRED DIFFERENCE
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


observed_gap = float(

    paired[
        "english_minus_arabic"
    ].mean()

)


# ============================================================
# BOOTSTRAP 95% CI
# ============================================================

rng = np.random.default_rng(
    RANDOM_SEED
)


differences = (

    paired[
        "english_minus_arabic"
    ].to_numpy(
        dtype=float
    )

)


bootstrap_means = np.empty(
    BOOTSTRAP_SAMPLES
)


for i in range(
    BOOTSTRAP_SAMPLES
):

    sample = rng.choice(
        differences,
        size=len(differences),
        replace=True,
    )

    bootstrap_means[i] = (
        sample.mean()
    )


ci_low = float(
    np.percentile(
        bootstrap_means,
        2.5,
    )
)


ci_high = float(
    np.percentile(
        bootstrap_means,
        97.5,
    )
)


print("\n" + "=" * 78)
print("BOOTSTRAP 95% CONFIDENCE INTERVAL")
print("=" * 78)


print(
    f"\nObserved English-Arabic gap: "
    f"{observed_gap:+.4f}"
)


print(
    f"95% bootstrap CI: "
    f"[{ci_low:.4f}, {ci_high:.4f}]"
)


# ============================================================
# SAVE REVIEW DECISIONS
# ============================================================

review_output = df[
    df["manual_reviewed"] == 1
][
    [
        "problem_id",
        "language",
        "gold_answer",
        "extracted_answer",
        "automatic_is_correct",
        "manual_is_correct",
        "manual_status",
        "manual_note",
        "question",
        "generated_response",
    ]
]


review_output.to_csv(
    REVIEW_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# SAVE FULL ADJUDICATED DATA
# ============================================================

df.to_csv(
    ADJUDICATED_FILE,
    index=False,
    encoding="utf-8-sig",
)


paired.to_csv(
    PAIRED_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# SAVE SUMMARY
# ============================================================

summary = pd.DataFrame(
    [
        {
            "model":
                "Gemma-3-1B-IT",

            "n_pairs":
                100,

            "arabic_correct":
                arabic_correct,

            "arabic_accuracy":
                arabic_accuracy,

            "english_correct":
                english_correct,

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

            "discordant_pairs":
                discordant,

            "mcnemar_exact_p":
                mcnemar_p,

            "bootstrap_ci_low":
                ci_low,

            "bootstrap_ci_high":
                ci_high,

            "manual_review_cases":
                54,

            "changed_by_adjudication":
                len(changed),
        }
    ]
)


summary.to_csv(
    SUMMARY_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# INTERPRETATION
# ============================================================

print("\n" + "=" * 78)
print("INTERPRETATION")
print("=" * 78)


if mcnemar_p < 0.05:

    print(
        "\nThe paired Arabic-English accuracy "
        "difference is statistically significant "
        "at alpha = 0.05."
    )

else:

    print(
        "\nThe paired Arabic-English accuracy "
        "difference does not reach p < 0.05."
    )


if english_accuracy > arabic_accuracy:

    print(
        "\nGemma achieved higher English than "
        "Arabic accuracy on the matched "
        "100-problem MGSM benchmark."
    )


print("\n" + "=" * 78)
print("FILES CREATED")
print("=" * 78)


print("\n", ADJUDICATED_FILE)
print(" ", REVIEW_FILE)
print(" ", PAIRED_FILE)
print(" ", SUMMARY_FILE)