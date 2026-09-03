import pandas as pd
import numpy as np
from scipy import stats


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "gemma_mgsm_101_200_results.csv"

ADJUDICATED_FILE = "gemma_mgsm_101_200_adjudicated.csv"
REVIEW_FILE = "gemma_mgsm_101_200_review_decisions.csv"
PAIRED_FILE = "gemma_mgsm_101_200_paired_results.csv"
SUMMARY_FILE = "gemma_mgsm_101_200_statistical_summary.csv"

BOOTSTRAP_SAMPLES = 10000
RANDOM_SEED = 42


# ============================================================
# MANUAL ADJUDICATION
# ============================================================

MANUALLY_CORRECT = {

    (113, "english"),

    (119, "english"),

    (120, "english"),

    (126, "english"),

    (136, "english"),

    (146, "english"),

    (150, "english"),

    (156, "english"),

    (169, "english"),

    (172, "english"),

    (184, "english"),

    (185, "english"),

    (186, "english"),

    (189, "english"),
}


# ============================================================
# LOAD
# ============================================================

print("=" * 78)
print("GEMMA MGSM 101-200 MANUAL ADJUDICATION AND STATISTICS")
print("=" * 78)


df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig",
)


print(
    "\nRows loaded:",
    len(df)
)


if len(df) != 200:

    raise RuntimeError(
        f"Expected 200 rows, found {len(df)}."
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

    print(
        df["model"].value_counts()
    )

    models = set(
        df["model"]
        .astype(str)
        .str.lower()
        .unique()
    )

    if models != {"gemma"}:

        raise RuntimeError(
            f"Expected only Gemma rows; found {models}."
        )


# ============================================================
# VERIFY STRUCTURE
# ============================================================

if df["problem_id"].min() != 101:

    raise RuntimeError(
        "Expected minimum problem ID 101."
    )


if df["problem_id"].max() != 200:

    raise RuntimeError(
        "Expected maximum problem ID 200."
    )


arabic_count = int(
    (
        df["language"]
        ==
        "arabic"
    ).sum()
)


english_count = int(
    (
        df["language"]
        ==
        "english"
    ).sum()
)


print(
    "\nArabic rows :",
    arabic_count
)

print(
    "English rows:",
    english_count
)


if arabic_count != 100:

    raise RuntimeError(
        "Expected 100 Arabic rows."
    )


if english_count != 100:

    raise RuntimeError(
        "Expected 100 English rows."
    )


# ============================================================
# VERIFY UNIQUE PAIRS
# ============================================================

duplicate_count = int(
    df.duplicated(
        subset=[
            "problem_id",
            "language",
        ]
    ).sum()
)


if duplicate_count:

    raise RuntimeError(
        f"Found {duplicate_count} duplicate problem/language rows."
    )


# ============================================================
# VERIFY REVIEW CASES
# ============================================================

review_mask = (
    df["needs_manual_review"]
    ==
    1
)


review_df = df[
    review_mask
].copy()


print(
    "\nFlagged manual-review cases:",
    len(review_df)
)


if len(review_df) != 55:

    raise RuntimeError(
        f"Expected 55 review cases, found {len(review_df)}."
    )


review_keys = set(
    zip(
        review_df["problem_id"],
        review_df["language"],
    )
)


missing = (
    MANUALLY_CORRECT
    -
    review_keys
)


if missing:

    raise RuntimeError(
        "Manually correct cases missing "
        f"from review set: {missing}"
    )


# ============================================================
# PRESERVE AUTOMATIC SCORING
# ============================================================

df[
    "automatic_is_correct"
] = df[
    "is_correct"
]


df[
    "manual_is_correct"
] = df[
    "automatic_is_correct"
]


df[
    "manual_reviewed"
] = 0


df[
    "manual_status"
] = ""


df[
    "manual_note"
] = ""


# ============================================================
# APPLY MANUAL REVIEW
# ============================================================

for index, row in df[
    review_mask
].iterrows():

    key = (
        int(
            row["problem_id"]
        ),
        row["language"],
    )


    automatic = int(
        row[
            "automatic_is_correct"
        ]
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
                "clearly reached the correct solution before "
                "later truncation, formatting failure, or "
                "generation degeneration."
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


        df.at[
            index,
            "manual_note"
        ] = (
            "Manual review found that the response did not "
            "clearly solve the supplied problem and reach "
            "the gold answer as its solution."
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
# CHANGED SCORES
# ============================================================

changed = df[
    df[
        "automatic_is_correct"
    ]
    !=
    df[
        "manual_is_correct"
    ]
].copy()


print("\n" + "=" * 78)
print("AUTOMATIC SCORES CHANGED BY MANUAL REVIEW")
print("=" * 78)


print(
    "\nNumber of changed cases:",
    len(changed)
)


if len(changed):

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
# FINAL ADJUDICATED ACCURACY
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


gap = (
    english_accuracy
    -
    arabic_accuracy
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
    f"{gap:+.4f}"
)


print(
    f"Percentage-point gap: "
    f"{gap * 100:+.1f}"
)


# ============================================================
# BUILD PAIRED RESULTS
# ============================================================

arabic = (

    df[
        df["language"]
        ==
        "arabic"
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
        df["language"]
        ==
        "english"
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
    validate="one_to_one",
)


paired = paired.sort_values(
    "problem_id"
)


if len(paired) != 100:

    raise RuntimeError(
        f"Expected 100 paired problems, found {len(paired)}."
    )


# ============================================================
# PAIRED OUTCOMES
# ============================================================

both_correct = int(

    (
        (
            paired[
                "arabic_correct"
            ] == 1
        )
        &
        (
            paired[
                "english_correct"
            ] == 1
        )
    ).sum()

)


both_wrong = int(

    (
        (
            paired[
                "arabic_correct"
            ] == 0
        )
        &
        (
            paired[
                "english_correct"
            ] == 0
        )
    ).sum()

)


english_only = int(

    (
        (
            paired[
                "arabic_correct"
            ] == 0
        )
        &
        (
            paired[
                "english_correct"
            ] == 1
        )
    ).sum()

)


arabic_only = int(

    (
        (
            paired[
                "arabic_correct"
            ] == 1
        )
        &
        (
            paired[
                "english_correct"
            ] == 0
        )
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
# EXACT MCNEMAR
# ============================================================

discordant = (
    english_only
    +
    arabic_only
)


if discordant:

    mcnemar_p = stats.binomtest(
        min(
            english_only,
            arabic_only,
        ),
        n=discordant,
        p=0.5,
        alternative="two-sided",
    ).pvalue

else:

    mcnemar_p = 1.0


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
    f"{mcnemar_p:.16g}"
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
# BOOTSTRAP CI
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


bootstrap = np.empty(
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
    df["manual_reviewed"]
    ==
    1
][
    [
        "problem_id",
        "source_index",
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
# SAVE FULL DATA
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

            "problem_range":
                "101-200",

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
                observed_gap,

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
                55,

            "manual_correct_cases":
                len(
                    MANUALLY_CORRECT
                ),

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
# FILES
# ============================================================

print("\n" + "=" * 78)
print("FILES CREATED")
print("=" * 78)


print(
    "\n",
    ADJUDICATED_FILE
)

print(
    " ",
    REVIEW_FILE
)

print(
    " ",
    PAIRED_FILE
)

print(
    " ",
    SUMMARY_FILE
)