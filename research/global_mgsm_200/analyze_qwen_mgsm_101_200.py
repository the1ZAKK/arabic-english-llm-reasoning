import pandas as pd
import numpy as np
from scipy import stats


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "qwen_mgsm_101_200_reparsed.csv"

ADJUDICATED_FILE = "qwen_mgsm_101_200_adjudicated.csv"
REVIEW_FILE = "qwen_mgsm_101_200_review_decisions.csv"
PAIRED_FILE = "qwen_mgsm_101_200_paired_results.csv"
SUMMARY_FILE = "qwen_mgsm_101_200_statistical_summary.csv"

BOOTSTRAP_SAMPLES = 10000
RANDOM_SEED = 42


# ============================================================
# MANUAL ADJUDICATION
#
# 34 parser-flagged cases were manually inspected.
# All 34 were genuine incorrect responses.
#
# Four automatically-correct Arabic responses were also
# semantically inspected because Qwen can occasionally produce
# the correct number while solving an unrelated problem.
#
# 140, 147, 151 = false positives
# 191 = genuinely correct
# ============================================================

SEMANTIC_CHECK_DECISIONS = {
    (140, "arabic"): 0,
    (147, "arabic"): 0,
    (151, "arabic"): 0,
    (191, "arabic"): 1,
}

EXPECTED_PARSER_REVIEW_CASES = 34
EXPECTED_SEMANTIC_CHECK_CASES = 4


# ============================================================
# LOAD
# ============================================================

print("=" * 78)
print("QWEN MGSM 101-200 MANUAL ADJUDICATION AND STATISTICS")
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

    model_values = set(
        df["model"]
        .astype(str)
        .str.strip()
        .str.lower()
        .unique()
    )

    if model_values != {"qwen"}:

        raise RuntimeError(
            f"Expected only Qwen rows. Found: {model_values}"
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
# VERIFY UNIQUE PROBLEM/LANGUAGE PAIRS
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
        f"Found {duplicate_count} duplicate rows."
    )


# ============================================================
# VERIFY PARSER-REVIEW COUNT
# ============================================================

parser_review_mask = (
    df["needs_manual_review"]
    ==
    1
)


parser_review = df[
    parser_review_mask
].copy()


print(
    "\nParser-flagged manual-review cases:",
    len(parser_review)
)


if (
    len(parser_review)
    !=
    EXPECTED_PARSER_REVIEW_CASES
):

    raise RuntimeError(
        "Expected "
        f"{EXPECTED_PARSER_REVIEW_CASES} "
        "parser-review cases, found "
        f"{len(parser_review)}."
    )


# ============================================================
# VERIFY SEMANTIC-CHECK ROWS
# ============================================================

all_keys = set(
    zip(
        df["problem_id"],
        df["language"],
    )
)


semantic_keys = set(
    SEMANTIC_CHECK_DECISIONS.keys()
)


missing_semantic = (
    semantic_keys
    -
    all_keys
)


if missing_semantic:

    raise RuntimeError(
        "Semantic-check cases missing: "
        f"{missing_semantic}"
    )


if (
    len(semantic_keys)
    !=
    EXPECTED_SEMANTIC_CHECK_CASES
):

    raise RuntimeError(
        "Unexpected number of semantic-check decisions."
    )


# ============================================================
# PRESERVE REPARSED AUTOMATIC RESULTS
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
# APPLY 34 PARSER-REVIEW DECISIONS
#
# All 34 were inspected and judged incorrect.
# ============================================================

for index, row in df[
    parser_review_mask
].iterrows():

    df.at[
        index,
        "manual_is_correct"
    ] = 0


    df.at[
        index,
        "manual_reviewed"
    ] = 1


    df.at[
        index,
        "manual_status"
    ] = "incorrect"


    df.at[
        index,
        "manual_note"
    ] = (
        "Manual review confirmed a genuine model failure. "
        "The response did not correctly solve the supplied "
        "Arabic mathematical problem."
    )


# ============================================================
# APPLY ARABIC SEMANTIC-GROUNDING CHECKS
# ============================================================

for (
    problem_id,
    language
), decision in SEMANTIC_CHECK_DECISIONS.items():

    mask = (
        (df["problem_id"] == problem_id)
        &
        (df["language"] == language)
    )


    matches = df[
        mask
    ]


    if len(matches) != 1:

        raise RuntimeError(
            f"Expected exactly one row for "
            f"{problem_id}/{language}, found {len(matches)}."
        )


    index = matches.index[
        0
    ]


    df.at[
        index,
        "manual_is_correct"
    ] = decision


    df.at[
        index,
        "manual_reviewed"
    ] = 1


    if decision == 1:

        df.at[
            index,
            "manual_status"
        ] = "correct"


        df.at[
            index,
            "manual_note"
        ] = (
            "Semantic inspection confirmed that the response "
            "preserved the relevant quantities and mathematical "
            "operation of the supplied problem and reached the "
            "correct answer."
        )

    else:

        df.at[
            index,
            "manual_status"
        ] = "incorrect"


        df.at[
            index,
            "manual_note"
        ] = (
            "Semantic inspection found that the response solved "
            "a substantially different or unrelated task. "
            "The matching numerical gold answer was coincidental."
        )


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
# REPARSED AUTOMATIC ACCURACY
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
print("REPARSED AUTOMATIC ACCURACY")
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
    /
    100
)


english_accuracy = (
    english_correct
    /
    100
)


accuracy_gap = (
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
# BOOTSTRAP CONFIDENCE INTERVAL
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

    bootstrap[
        i
    ] = sample.mean()


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
# SAVE MANUAL REVIEW DECISIONS
# ============================================================

review_output = df[
    df[
        "manual_reviewed"
    ]
    ==
    1
].copy()


review_output.to_csv(
    REVIEW_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# SAVE ADJUDICATED RESULTS
# ============================================================

df.to_csv(
    ADJUDICATED_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# SAVE PAIRED RESULTS
# ============================================================

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
                "Qwen2.5-Math-1.5B-Instruct",

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

            "parser_review_cases":
                EXPECTED_PARSER_REVIEW_CASES,

            "semantic_check_cases":
                EXPECTED_SEMANTIC_CHECK_CASES,

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
# FILES CREATED
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