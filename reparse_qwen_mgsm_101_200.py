import re
from decimal import Decimal, InvalidOperation

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "qwen_mgsm_101_200_results.csv"

OUTPUT_FILE = "qwen_mgsm_101_200_reparsed.csv"

REVIEW_FILE = "qwen_mgsm_101_200_manual_review.txt"

FIRST_PROBLEM_ID = 101
LAST_PROBLEM_ID = 200

EXPECTED_PROBLEMS = 100
EXPECTED_ROWS = 200


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

    value = value.replace(
        ",",
        ""
    )

    value = value.replace(
        "٬",
        ""
    )

    value = value.replace(
        "٫",
        "."
    )

    value = value.replace(
        "$",
        ""
    )

    value = value.replace(
        "%",
        ""
    )

    value = value.strip()


    try:

        number = Decimal(
            value
        )

        if (
            number
            ==
            number.to_integral()
        ):

            return str(
                int(number)
            )

        return format(
            number.normalize(),
            "f",
        )

    except InvalidOperation:

        return value


# ============================================================
# NUMBER PATTERN
# ============================================================

NUMBER = (
    r"[-+]?"
    r"(?:\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.\d+)?"
)


# ============================================================
# QWEN-SPECIFIC ANSWER EXTRACTOR
# ============================================================

def extract_qwen_answer(response):

    text = normalize_digits(
        response
    )

    candidates = []


    # --------------------------------------------------------
    # 1. \boxed{number}
    #
    # Qwen Math's chat template commonly asks for answers
    # inside \boxed{} even when our user prompt requests
    # FINAL ANSWER.
    # --------------------------------------------------------

    for match in re.finditer(
        rf"\\boxed\s*\{{\s*({NUMBER})\s*\}}",
        text,
        flags=re.IGNORECASE,
    ):

        candidates.append({
            "position":
                match.start(),

            "value":
                normalize_number(
                    match.group(1)
                ),

            "type":
                "boxed",
        })


    # --------------------------------------------------------
    # 2. English final-answer phrases
    # --------------------------------------------------------

    english_patterns = [

        (
            rf"FINAL\s+ANSWER\s*:\s*"
            rf"(?:THE\s+FINAL\s+ANSWER\s+IS\s*)?"
            rf"(?:\$|\\?\$)?\s*({NUMBER})"
        ),

        (
            rf"Final\s+Answer\s*:\s*"
            rf"(?:The\s+final\s+answer\s+is\s*)?"
            rf"(?:\$|\\?\$)?\s*({NUMBER})"
        ),

        (
            rf"The\s+final\s+answer\s+is\s*"
            rf"(?:\$|\\?\$)?\s*({NUMBER})"
        ),

        (
            rf"Therefore[,:\s]+"
            rf"(?:the\s+answer\s+is\s*)?"
            rf"(?:\$|\\?\$)?\s*({NUMBER})"
        ),
    ]


    for pattern in english_patterns:

        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):

            candidates.append({
                "position":
                    match.start(),

                "value":
                    normalize_number(
                        match.group(1)
                    ),

                "type":
                    "english_final_phrase",
            })


    # --------------------------------------------------------
    # 3. Arabic final-answer phrases
    # --------------------------------------------------------

    arabic_patterns = [

        (
            rf"الإجابة\s+النهائية\s*"
            rf"[:：]?\s*({NUMBER})"
        ),

        (
            rf"الجواب\s+النهائي\s*"
            rf"[:：]?\s*({NUMBER})"
        ),

        (
            rf"الإجابة\s+هي\s*"
            rf"[:：]?\s*({NUMBER})"
        ),

        (
            rf"الجواب\s+هو\s*"
            rf"[:：]?\s*({NUMBER})"
        ),

        (
            rf"إذن[,،:\s]+"
            rf"(?:الإجابة\s+هي\s*)?"
            rf"({NUMBER})"
        ),
    ]


    for pattern in arabic_patterns:

        for match in re.finditer(
            pattern,
            text,
        ):

            candidates.append({
                "position":
                    match.start(),

                "value":
                    normalize_number(
                        match.group(1)
                    ),

                "type":
                    "arabic_final_phrase",
            })


    # --------------------------------------------------------
    # REMOVE EXACT DUPLICATES
    #
    # The same text span can occasionally match more than one
    # pattern.
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


        # ----------------------------------------------------
        # All explicit answers agree.
        # ----------------------------------------------------

        if len(
            unique_values
        ) == 1:

            return {
                "answer":
                    values[0],

                "method":
                    candidates[0][
                        "type"
                    ],

                "needs_manual_review":
                    0,

                "review_reason":
                    "",

                "all_candidates":
                    "|".join(
                        values
                    ),
            }


        # ----------------------------------------------------
        # Conflicting explicit answers.
        #
        # Use the FIRST explicit answer provisionally.
        #
        # In earlier experiments, later token degeneration and
        # answer repetition sometimes produced bogus later
        # answers after a valid solution.
        #
        # Always flag these cases for manual inspection.
        # ----------------------------------------------------

        return {
            "answer":
                candidates[0][
                    "value"
                ],

            "method":
                candidates[0][
                    "type"
                ],

            "needs_manual_review":
                1,

            "review_reason":
                "conflicting_explicit_answers",

            "all_candidates":
                "|".join(
                    values
                ),
        }


    # --------------------------------------------------------
    # 4. LAST-NUMBER FALLBACK
    #
    # Always requires manual review.
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
    # 5. NO NUMERIC ANSWER
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

def numeric_equal(
    predicted,
    gold,
):

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

        return (
            p
            ==
            g
        )


# ============================================================
# LOAD
# ============================================================

print("=" * 78)

print(
    "RE-PARSING QWEN MGSM "
    "PROBLEMS 101-200"
)

print("=" * 78)


df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig",
)


print(
    "\nRows:",
    len(df)
)


# ============================================================
# BASIC ROW VALIDATION
# ============================================================

if len(df) != EXPECTED_ROWS:

    raise RuntimeError(
        f"Expected {EXPECTED_ROWS} rows, "
        f"found {len(df)}."
    )


# ============================================================
# NORMALIZE STRUCTURAL FIELDS
# ============================================================

df[
    "problem_id"
] = pd.to_numeric(
    df["problem_id"],
    errors="raise",
).astype(int)


df[
    "language"
] = (
    df[
        "language"
    ]
    .astype(str)
    .str.strip()
    .str.lower()
)


# ============================================================
# VERIFY QWEN MODEL
# ============================================================

if "model" in df.columns:

    print(
        "\nModel values:"
    )

    print(
        df[
            "model"
        ].value_counts()
    )


    model_values = set(
        df[
            "model"
        ]
        .astype(str)
        .str.strip()
        .str.lower()
        .unique()
    )


    if model_values != {
        "qwen"
    }:

        raise RuntimeError(
            "Expected only Qwen rows. "
            f"Found: {model_values}"
        )


# ============================================================
# VERIFY PROBLEM RANGE
# ============================================================

minimum_id = int(
    df[
        "problem_id"
    ].min()
)


maximum_id = int(
    df[
        "problem_id"
    ].max()
)


print(
    "\nMinimum problem ID:",
    minimum_id
)

print(
    "Maximum problem ID:",
    maximum_id
)


if minimum_id != FIRST_PROBLEM_ID:

    raise RuntimeError(
        f"Expected minimum problem ID "
        f"{FIRST_PROBLEM_ID}."
    )


if maximum_id != LAST_PROBLEM_ID:

    raise RuntimeError(
        f"Expected maximum problem ID "
        f"{LAST_PROBLEM_ID}."
    )


# ============================================================
# VERIFY EXACT PROBLEM IDS
# ============================================================

problem_ids = sorted(
    df[
        "problem_id"
    ].unique()
)


expected_problem_ids = list(
    range(
        FIRST_PROBLEM_ID,
        LAST_PROBLEM_ID + 1,
    )
)


if problem_ids != expected_problem_ids:

    raise RuntimeError(
        "Problem IDs are not exactly "
        "101 through 200."
    )


print(
    "Unique problems:",
    len(problem_ids)
)


# ============================================================
# VERIFY LANGUAGES
# ============================================================

language_values = set(
    df[
        "language"
    ].unique()
)


if language_values != {
    "arabic",
    "english",
}:

    raise RuntimeError(
        "Unexpected language values: "
        f"{language_values}"
    )


arabic_rows = int(
    (
        df[
            "language"
        ]
        ==
        "arabic"
    ).sum()
)


english_rows = int(
    (
        df[
            "language"
        ]
        ==
        "english"
    ).sum()
)


print(
    "\nArabic rows :",
    arabic_rows
)

print(
    "English rows:",
    english_rows
)


if arabic_rows != 100:

    raise RuntimeError(
        f"Expected 100 Arabic rows, "
        f"found {arabic_rows}."
    )


if english_rows != 100:

    raise RuntimeError(
        f"Expected 100 English rows, "
        f"found {english_rows}."
    )


# ============================================================
# VERIFY UNIQUE PROBLEM/LANGUAGE PAIRS
# ============================================================

duplicate_pairs = int(

    df.duplicated(
        subset=[
            "problem_id",
            "language",
        ]
    ).sum()

)


if duplicate_pairs:

    raise RuntimeError(
        f"Found {duplicate_pairs} duplicate "
        "problem/language pairs."
    )


print(
    "Duplicate problem/language pairs:",
    duplicate_pairs
)


# ============================================================
# VERIFY ALL GENERATIONS SUCCEEDED
# ============================================================

if "status" in df.columns:

    failed = df[
        df[
            "status"
        ]
        !=
        "success"
    ]


    print(
        "Failed generations:",
        len(failed)
    )


    if len(failed):

        raise RuntimeError(
            "Some generations were not successful. "
            "Rerun the extension runner before reparsing."
        )


# ============================================================
# PRESERVE OLD AUTOMATIC RESULTS
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


df[
    "old_review_reason"
] = df[
    "review_reason"
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

    response = row[
        "generated_response"
    ]


    if pd.isna(
        response
    ):

        response = ""


    parsed = extract_qwen_answer(
        str(response)
    )


    prediction = parsed[
        "answer"
    ]


    correct = numeric_equal(
        prediction,
        row[
            "gold_answer"
        ],
    )


    new_answers.append(
        prediction
    )


    new_methods.append(
        parsed[
            "method"
        ]
    )


    new_correct.append(
        int(
            correct
        )
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


# ============================================================
# APPLY REPARSED VALUES
# ============================================================

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
# REVISED AUTOMATIC RESULTS
# ============================================================

print(
    "\n"
    + "=" * 78
)

print(
    "REVISED AUTOMATIC RESULTS"
)

print(
    "=" * 78
)


for language in [
    "arabic",
    "english",
]:

    rows = df[
        df[
            "language"
        ]
        ==
        language
    ]


    correct = int(
        rows[
            "is_correct"
        ].sum()
    )


    total = len(
        rows
    )


    accuracy = (
        correct / total
        if total
        else 0
    )


    print(
        f"\n{language.upper()}"
    )


    print(
        f"Correct: "
        f"{correct}/{total}"
    )


    print(
        f"Accuracy: "
        f"{accuracy:.4f}"
    )


# ============================================================
# SCORING CHANGES
# ============================================================

old_correct = pd.to_numeric(
    df[
        "old_is_correct"
    ],
    errors="coerce",
).fillna(
    0
).astype(
    int
)


changed = df[
    old_correct
    !=
    df[
        "is_correct"
    ]
].copy()


print(
    "\n"
    + "=" * 78
)

print(
    "SCORING CHANGES"
)

print(
    "=" * 78
)


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
                "old_extraction_method",
                "extraction_method",
            ]
        ].to_string(
            index=False
        )

    )


# ============================================================
# EXTRACTION METHOD SUMMARY
# ============================================================

print(
    "\n"
    + "=" * 78
)

print(
    "EXTRACTION METHOD SUMMARY"
)

print(
    "=" * 78
)


print(
    "\n"
    + df[
        "extraction_method"
    ].value_counts().to_string()
)


# ============================================================
# MANUAL REVIEW CASES
# ============================================================

review = df[
    df[
        "needs_manual_review"
    ]
    ==
    1
].copy()


review = review.sort_values(
    [
        "problem_id",
        "language",
    ]
)


print(
    "\n"
    + "=" * 78
)

print(
    "NEW MANUAL REVIEW SUMMARY"
)

print(
    "=" * 78
)


print(
    "\nCases requiring manual review:",
    len(review)
)


if len(review):

    print(
        "\nReview cases by language:"
    )

    print(
        review[
            "language"
        ].value_counts()
    )


    print(
        "\nReview cases:"
    )


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
# IMPORTANT SEMANTIC CHECK
#
# Even automatically correct Arabic answers should later be
# inspected for semantic grounding because the first Qwen
# experiment showed that an unrelated generated task can
# coincidentally produce the correct numeric answer.
# ============================================================

arabic_auto_correct = df[
    (
        df[
            "language"
        ]
        ==
        "arabic"
    )
    &
    (
        df[
            "is_correct"
        ]
        ==
        1
    )
].copy()


print(
    "\n"
    + "=" * 78
)

print(
    "ARABIC AUTOMATIC-CORRECT CASES "
    "FOR SEMANTIC CHECK"
)

print(
    "=" * 78
)


print(
    "\nCount:",
    len(
        arabic_auto_correct
    )
)


if len(
    arabic_auto_correct
):

    print(

        arabic_auto_correct[
            [
                "problem_id",
                "gold_answer",
                "extracted_answer",
                "extraction_method",
                "needs_manual_review",
            ]
        ].to_string(
            index=False
        )

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
# SAVE CASES REQUIRING MANUAL REVIEW
#
# In addition, append all automatically-correct Arabic cases
# so we can inspect them for semantic grounding even when the
# parser itself considers them clean.
# ============================================================

review_keys = set(
    zip(
        review[
            "problem_id"
        ],
        review[
            "language"
        ],
    )
)


semantic_extra = arabic_auto_correct[

    ~arabic_auto_correct.apply(

        lambda row: (
            int(
                row[
                    "problem_id"
                ]
            ),
            row[
                "language"
            ],
        )
        in
        review_keys,

        axis=1,

    )

].copy()


manual_file_rows = pd.concat(
    [
        review,
        semantic_extra,
    ],
    ignore_index=True,
)


manual_file_rows = manual_file_rows.sort_values(
    [
        "problem_id",
        "language",
    ]
)


with open(
    REVIEW_FILE,
    "w",
    encoding="utf-8",
) as f:

    for _, row in manual_file_rows.iterrows():

        key = (
            int(
                row[
                    "problem_id"
                ]
            ),
            row[
                "language"
            ],
        )


        parser_review = (
            key
            in
            review_keys
        )


        semantic_check = (
            row[
                "language"
            ]
            ==
            "arabic"
            and
            int(
                row[
                    "is_correct"
                ]
            )
            ==
            1
        )


        f.write(
            "=" * 90
            + "\n"
        )


        f.write(
            f"PROBLEM "
            f"{int(row['problem_id'])} "
            f"| "
            f"{str(row['language']).upper()}\n"
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
            f"PARSER REVIEW REQUIRED: "
            f"{int(parser_review)}\n"
        )


        f.write(
            f"ARABIC SEMANTIC CHECK: "
            f"{int(semantic_check)}\n"
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
            str(
                row[
                    "question"
                ]
            )
            +
            "\n\n"
        )


        f.write(
            "MODEL RESPONSE:\n"
        )


        f.write(
            str(
                row[
                    "generated_response"
                ]
            )
            +
            "\n\n"
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
# FINAL FILE SUMMARY
# ============================================================

print(
    "\n"
    + "=" * 78
)

print(
    "FILES CREATED"
)

print(
    "=" * 78
)


print(
    "\n",
    OUTPUT_FILE
)


print(
    " ",
    REVIEW_FILE
)


print(
    "\nRows in reparsed CSV:",
    len(df)
)


print(
    "Parser-flagged review cases:",
    len(review)
)


print(
    "Additional Arabic semantic-check cases:",
    len(
        semantic_extra
    )
)


print(
    "Total cases written to manual-review file:",
    len(
        manual_file_rows
    )
)


print(
    "\nNEXT STEP:"
)


print(
    "Upload qwen_mgsm_101_200_manual_review.txt "
    "after checking the revised automatic results."
)