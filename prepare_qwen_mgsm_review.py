import pandas as pd
from pathlib import Path


INPUT_FILE = "gemma_mgsm_100_results.csv"

CSV_OUTPUT = "gemma_mgsm_100_manual_review.csv"
TEXT_OUTPUT = "gemma_mgsm_100_manual_review.txt"


print("=" * 76)
print("PREPARING GEMMA MGSM MANUAL REVIEW")
print("=" * 76)


df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig",
)


# ------------------------------------------------------------
# Normalize
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# Select review cases
# ------------------------------------------------------------

review = df[
    df["needs_manual_review"] == 1
].copy()


print(
    "\nCases requiring review:",
    len(review)
)


# ------------------------------------------------------------
# Add adjudication columns
# ------------------------------------------------------------

review["manual_is_correct"] = ""
review["manual_answer"] = ""
review["manual_error_type"] = ""
review["manual_note"] = ""


# ------------------------------------------------------------
# Useful order
# ------------------------------------------------------------

review = review.sort_values(
    ["problem_id", "language"]
)


# ------------------------------------------------------------
# Save editable CSV
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# Create human-readable text file
# ------------------------------------------------------------

with open(
    TEXT_OUTPUT,
    "w",
    encoding="utf-8",
) as f:

    for _, row in review.iterrows():

        f.write(
            "=" * 90
            + "\n"
        )

        f.write(
            f"PROBLEM {row['problem_id']} "
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


print("\nCreated:")
print(" ", CSV_OUTPUT)
print(" ", TEXT_OUTPUT)

print(
    "\nDo not calculate final statistics "
    "until these cases are adjudicated."
)