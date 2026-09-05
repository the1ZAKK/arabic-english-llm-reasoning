import re
from decimal import Decimal, InvalidOperation

import pandas as pd


INPUT_FILE = "qwen_mgsm_100_results.csv"

OUTPUT_FILE = "qwen_mgsm_100_reparsed.csv"

REVIEW_FILE = "qwen_mgsm_100_manual_review.txt"


# ============================================================
# DIGIT NORMALIZATION
# ============================================================

DIGIT_TRANSLATION = str.maketrans({
    "٠": "0",
    "١": "1",
    "٢": "2",
    "٣": "3",
    "٤": "4",
    "٥": "5",
    "٦": "6",
    "٧": "7",
    "٨": "8",
    "٩": "9",

    "۰": "0",
    "۱": "1",
    "۲": "2",
    "۳": "3",
    "۴": "4",
    "۵": "5",
    "۶": "6",
    "۷": "7",
    "۸": "8",
    "۹": "9",
})


def normalize_digits(text):

    return str(text).translate(
        DIGIT_TRANSLATION
    )


# ============================================================
# NUMBER NORMALIZATION
# ============================================================

def normalize_number(value):

    if value is None:
        return None

    value = normalize_digits(
        value
    )

    value = value.strip()

    value = value.replace(",", "")
    value = value.replace("٬", "")
    value = value.replace("٫", ".")
    value = value.replace("$", "")
    value = value.replace("%", "")

    try:

        number = Decimal(value)

        if number == number.to_integral():

            return str(
                int(number)
            )

        return format(
            number.normalize(),
            "f",
        )

    except InvalidOperation:

        return value


NUMBER = (
    r"[-+]?"
    r"(?:\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.\d+)?"
)


# ============================================================
# EXTRACTOR
# ============================================================

def extract_qwen_answer(response):

    text = normalize_digits(
        response
    )

    candidates = []


    # --------------------------------------------------------
    # 1. \boxed{number}
    # Qwen Math commonly uses this.
    # --------------------------------------------------------

    for match in re.finditer(
        rf"\\boxed\s*\{{\s*({NUMBER})\s*\}}",
        text,
        flags=re.IGNORECASE,
    ):

        candidates.append({
            "position": match.start(),
            "value": normalize_number(
                match.group(1)
            ),
            "type": "boxed",
        })


    # --------------------------------------------------------
    # 2. English final-answer phrases
    # --------------------------------------------------------

    english_patterns = [

        rf"FINAL\s+ANSWER\s*:\s*(?:THE\s+FINAL\s+ANSWER\s+IS\s*)?"
        rf"(?:\$|\\?\$)?\s*({NUMBER})",

        rf"Final\s+Answer\s*:\s*(?:The\s+final\s+answer\s+is\s*)?"
        rf"(?:\$|\\?\$)?\s*({NUMBER})",

        rf"The\s+final\s+answer\s+is\s*"
        rf"(?:\$|\\?\$)?\s*({NUMBER})",

        rf"Therefore[,:\s]+(?:the\s+answer\s+is\s*)?"
        rf"(?:\$|\\?\$)?\s*({NUMBER})",
    ]


    for pattern in english_patterns:

        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):

            candidates.append({
                "position": match.start(),
                "value": normalize_number(
                    match.group(1)
                ),
                "type": "english_final_phrase",
            })


    # --------------------------------------------------------
    # 3. Arabic answer phrases
    # --------------------------------------------------------

    arabic_patterns = [

        rf"الإجابة\s+النهائية\s*[:：]?\s*"
        rf"({NUMBER})",

        rf"الجواب\s+النهائي\s*[:：]?\s*"
        rf"({NUMBER})",

        rf"الإجابة\s+هي\s*[:：]?\s*"
        rf"({NUMBER})",

        rf"الجواب\s+هو\s*[:：]?\s*"
        rf"({NUMBER})",

        rf"إذن[,،:\s]+(?:الإجابة\s+هي\s*)?"
        rf"({NUMBER})",
    ]


    for pattern in arabic_patterns:

        for match in re.finditer(
            pattern,
            text,
        ):

            candidates.append({
                "position": match.start(),
                "value": normalize_number(
                    match.group(1)
                ),
                "type": "arabic_final_phrase",
            })


    # --------------------------------------------------------
    # REMOVE DUPLICATES AT SAME VALUE/POSITION
    # --------------------------------------------------------

    unique = []

    seen = set()


    for item in sorted(
        candidates,
        key=lambda x: x["position"],
    ):

        key = (
            item["position"],
            item["value"],
        )

        if key not in seen:

            unique.append(
                item
            )

            seen.add(
                key
            )


    candidates = unique


    # --------------------------------------------------------
    # EXPLICIT ANSWERS FOUND
    # --------------------------------------------------------

    if candidates:

        values = [
            item["value"]
            for item in candidates
        ]

        unique_values = set(
            values
        )


        # If all explicit answers agree, accept.
        if len(unique_values) == 1:

            return {
                "answer":
                    values[0],

                "method":
                    candidates[0]["type"],

                "needs_manual_review":
                    0,

                "review_reason":
                    "",

                "all_candidates":
                    "|".join(values),
            }


        # Conflicting explicit answers.
        #
        # Use the FIRST explicit answer for provisional
        # scoring because later repetition/degeneration
        # caused false negatives in previous experiments.
        #
        # But ALWAYS flag this case for human review.

        return {
            "answer":
                candidates[0]["value"],

            "method":
                candidates[0]["type"],

            "needs_manual_review":
                1,

            "review_reason":
                "conflicting_explicit_answers",

            "all_candidates":
                "|".join(values),
        }


    # --------------------------------------------------------
    # 4. Last-number fallback
    # --------------------------------------------------------

    numbers = re.findall(
        NUMBER,
        text,
    )


    if numbers:

        value = normalize_number(
            numbers[-1]
        )

        return {
            "answer":
                value,

            "method":
                "last_number_fallback",

            "needs_manual_review":
                1,

            "review_reason":
                "fallback_extraction",

            "all_candidates":
                "",
        }


    # --------------------------------------------------------
    # NOTHING NUMERIC
    # --------------------------------------------------------

    return {
        "answer":
            None,

        "method":
            "no_number",

        "needs_manual_review":
            1,

        "review_reason":
            "no_numeric_answer",

        "all_candidates":
            "",
    }


# ============================================================
# NUMERIC COMPARISON
# ============================================================

def numeric_equal(predicted, gold):

    if predicted is None:
        return False

    p = normalize_number(
        predicted
    )

    g = normalize_number(
        gold
    )

    try:

        return (
            Decimal(p)
            ==
            Decimal(g)
        )

    except Exception:

        return p == g


# ============================================================
# LOAD
# ============================================================

print("=" * 78)
print("RE-PARSING QWEN MGSM-100 RESULTS")
print("=" * 78)


df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig",
)


print(
    "\nRows:",
    len(df)
)


if len(df) != 200:

    raise RuntimeError(
        f"Expected 200 rows, found {len(df)}."
    )


if "model" in df.columns:

    print("\nModel values:")

    print(
        df["model"].value_counts()
    )


# ============================================================
# PRESERVE OLD RESULTS
# ============================================================

df[
    "old_extracted_answer"
] = df[
    "extracted_answer"
]


df[
    "old_is_correct"
] = df[
    "is_correct"
]


df[
    "old_extraction_method"
] = df[
    "extraction_method"
]


df[
    "old_needs_manual_review"
] = df[
    "needs_manual_review"
]


# ============================================================
# RE-PARSE EVERY RESPONSE
# ============================================================

new_answers = []

new_methods = []

new_correct = []

new_review = []

new_review_reason = []

all_candidates = []


for _, row in df.iterrows():

    parsed = extract_qwen_answer(
        row["generated_response"]
    )


    prediction = parsed[
        "answer"
    ]


    correct = numeric_equal(
        prediction,
        row["gold_answer"],
    )


    new_answers.append(
        prediction
    )

    new_methods.append(
        parsed["method"]
    )

    new_correct.append(
        int(correct)
    )

    new_review.append(
        parsed[
            "needs_manual_review"
        ]
    )

    new_review_reason.append(
        parsed[
            "review_reason"
        ]
    )

    all_candidates.append(
        parsed[
            "all_candidates"
        ]
    )


df[
    "extracted_answer"
] = new_answers


df[
    "extraction_method"
] = new_methods


df[
    "is_correct"
] = new_correct


df[
    "needs_manual_review"
] = new_review


df[
    "review_reason"
] = new_review_reason


df[
    "all_explicit_answers"
] = all_candidates


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 78)
print("REVISED AUTOMATIC RESULTS")
print("=" * 78)


for language in [
    "arabic",
    "english",
]:

    rows = df[
        df["language"] == language
    ]

    correct = int(
        rows["is_correct"].sum()
    )

    total = len(
        rows
    )

    print(
        f"\n{language.upper()}"
    )

    print(
        f"Correct: {correct}/{total}"
    )

    print(
        f"Accuracy: {correct / total:.4f}"
    )


# ============================================================
# CHANGES
# ============================================================

old_correct = pd.to_numeric(
    df["old_is_correct"],
    errors="coerce",
).fillna(0).astype(int)


changed = df[
    old_correct
    !=
    df["is_correct"]
]


print("\n" + "=" * 78)
print("SCORING CHANGES")
print("=" * 78)


print(
    "\nCases whose automatic score changed:",
    len(changed)
)


if len(changed):

    print(

        changed[
            [
                "problem_id",
                "language",
                "gold_answer",
                "old_extracted_answer",
                "extracted_answer",
                "old_is_correct",
                "is_correct",
            ]
        ].to_string(
            index=False
        )

    )


# ============================================================
# REVIEW COUNT
# ============================================================

review = df[
    df["needs_manual_review"] == 1
].copy()


print("\n" + "=" * 78)
print("NEW MANUAL REVIEW SUMMARY")
print("=" * 78)


print(
    "\nCases requiring manual review:",
    len(review)
)


if len(review):

    for _, row in review.iterrows():

        print(
            f"Problem "
            f"{int(row['problem_id']):3d} | "
            f"{row['language']:7s} | "
            f"gold={row['gold_answer']} | "
            f"pred={row['extracted_answer']} | "
            f"{row['review_reason']}"
        )


# ============================================================
# SAVE REPARSED CSV
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# SAVE ONLY CASES THAT STILL REQUIRE HUMAN REVIEW
# ============================================================

with open(
    REVIEW_FILE,
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
            f"REPARSED ANSWER: "
            f"{row['extracted_answer']}\n"
        )

        f.write(
            f"AUTOMATIC CORRECT: "
            f"{row['is_correct']}\n"
        )

        f.write(
            f"METHOD: "
            f"{row['extraction_method']}\n"
        )

        f.write(
            f"REASON: "
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


print("\n" + "=" * 78)
print("FILES CREATED")
print("=" * 78)


print(
    "\n",
    OUTPUT_FILE
)

print(
    " ",
    REVIEW_FILE
)