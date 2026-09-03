import pandas as pd


INPUT_FILE = "gemma_mgsm_101_200_results.csv"

CSV_OUTPUT = "gemma_mgsm_101_200_manual_review.csv"

TXT_OUTPUT = "gemma_mgsm_101_200_manual_review.txt"


# ============================================================
# LOAD
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig",
)


print("=" * 80)
print("PREPARING GEMMA MGSM 101-200 MANUAL REVIEW")
print("=" * 80)


print("\nRows loaded:", len(df))


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


df["needs_manual_review"] = pd.to_numeric(
    df["needs_manual_review"],
    errors="coerce",
).fillna(0).astype(int)


df["is_correct"] = pd.to_numeric(
    df["is_correct"],
    errors="coerce",
).fillna(0).astype(int)


# ============================================================
# VALIDATE PROBLEM RANGE
# ============================================================

if df["problem_id"].min() != 101:

    raise RuntimeError(
        "Expected minimum problem ID 101."
    )


if df["problem_id"].max() != 200:

    raise RuntimeError(
        "Expected maximum problem ID 200."
    )


if set(df["language"]) != {
    "arabic",
    "english",
}:

    raise RuntimeError(
        f"Unexpected languages: {set(df['language'])}"
    )


if (
    (df["language"] == "arabic").sum()
    != 100
):

    raise RuntimeError(
        "Expected 100 Arabic rows."
    )


if (
    (df["language"] == "english").sum()
    != 100
):

    raise RuntimeError(
        "Expected 100 English rows."
    )


# ============================================================
# SELECT REVIEW CASES
# ============================================================

review = df[
    df["needs_manual_review"] == 1
].copy()


review = review.sort_values(
    [
        "problem_id",
        "language",
    ]
)


print(
    "\nCases requiring manual review:",
    len(review)
)


if len(review) != 55:

    raise RuntimeError(
        f"Expected 55 review cases, found {len(review)}."
    )


# ============================================================
# ADD MANUAL FIELDS
# ============================================================

review[
    "manual_is_correct"
] = ""


review[
    "manual_answer"
] = ""


review[
    "manual_error_type"
] = ""


review[
    "manual_note"
] = ""


# ============================================================
# SAVE REVIEW CSV
# ============================================================

columns = [
    "problem_id",
    "source_index",
    "language",
    "gold_answer",
    "extracted_answer",
    "is_correct",
    "extraction_method",
    "review_reason",
    "all_explicit_answers",
    "question",
    "generated_response",
    "manual_is_correct",
    "manual_answer",
    "manual_error_type",
    "manual_note",
]


review[
    columns
].to_csv(
    CSV_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# SAVE HUMAN-READABLE TEXT FILE
# ============================================================

with open(
    TXT_OUTPUT,
    "w",
    encoding="utf-8",
) as f:

    for _, row in review.iterrows():

        f.write(
            "=" * 90
            + "\n"
        )

        f.write(
            f"PROBLEM {int(row['problem_id'])} "
            f"| {str(row['language']).upper()}\n"
        )

        f.write(
            "=" * 90
            + "\n\n"
        )

        f.write(
            f"GOLD ANSWER: "
            f"{row['gold_answer']}\n"
        )

        f.write(
            f"EXTRACTED ANSWER: "
            f"{row['extracted_answer']}\n"
        )

        f.write(
            f"AUTOMATIC CORRECT: "
            f"{row['is_correct']}\n"
        )

        f.write(
            f"EXTRACTION METHOD: "
            f"{row['extraction_method']}\n"
        )

        f.write(
            f"REVIEW REASON: "
            f"{row['review_reason']}\n"
        )

        f.write(
            f"ALL EXPLICIT ANSWERS: "
            f"{row['all_explicit_answers']}\n\n"
        )

        f.write(
            "QUESTION:\n"
        )

        f.write(
            str(row["question"])
            + "\n\n"
        )

        f.write(
            "MODEL RESPONSE:\n"
        )

        f.write(
            str(row["generated_response"])
            + "\n\n"
        )

        f.write(
            "MANUAL DECISION:\n"
        )

        f.write(
            "Correct? [0/1]: \n"
        )

        f.write(
            "Final answer: \n"
        )

        f.write(
            "Error type: \n"
        )

        f.write(
            "Notes: \n\n"
        )


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 80)
print("REVIEW BREAKDOWN")
print("=" * 80)


print(
    "\nBy language:"
)

print(
    review[
        "language"
    ].value_counts()
)


print(
    "\nAutomatically correct but flagged:"
)


flagged_correct = review[
    review["is_correct"] == 1
][
    [
        "problem_id",
        "language",
        "gold_answer",
        "extracted_answer",
        "review_reason",
    ]
]


if len(flagged_correct):

    print(
        flagged_correct.to_string(
            index=False
        )
    )

else:

    print(
        "None"
    )


print("\n" + "=" * 80)
print("FILES CREATED")
print("=" * 80)


print(
    "\n",
    CSV_OUTPUT
)

print(
    " ",
    TXT_OUTPUT
)