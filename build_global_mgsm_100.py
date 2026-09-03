import json
import random
import re
from pathlib import Path

import pandas as pd
from datasets import load_dataset


# ============================================================
# CONFIGURATION
# ============================================================

DATASET_NAME = "CohereLabs/global-mgsm"

SAMPLE_SIZE = 100
RANDOM_SEED = 42

OUTPUT_DIR = Path("data") / "processed"

JSONL_OUTPUT = (
    OUTPUT_DIR
    / "global_mgsm_ar_en_100.jsonl"
)

CSV_OUTPUT = (
    OUTPUT_DIR
    / "global_mgsm_ar_en_100_review.csv"
)


# ============================================================
# NUMBER NORMALIZATION
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


def normalize_text_digits(text):

    return str(text).translate(
        DIGIT_TRANSLATION
    )


def normalize_answer(answer):

    value = normalize_text_digits(
        answer
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
        " ",
        ""
    )

    # Normalize integer-looking decimal answers
    try:

        number = float(value)

        if number.is_integer():

            return str(
                int(number)
            )

    except Exception:
        pass

    return value


def extract_numbers(text):

    text = normalize_text_digits(
        text
    )

    text = text.replace(
        "٬",
        ","
    )

    text = text.replace(
        "٫",
        "."
    )

    numbers = re.findall(
        r"[-+]?\d[\d,]*(?:\.\d+)?",
        text,
    )

    normalized = []

    for number in numbers:

        normalized.append(
            normalize_answer(
                number
            )
        )

    return normalized


# ============================================================
# START
# ============================================================

print("=" * 72)
print("BUILDING 100 MATCHED ARABIC-ENGLISH MGSM PROBLEMS")
print("=" * 72)


OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# DOWNLOAD ENGLISH
# ============================================================

print("\nDownloading English Global-MGSM...")

english = load_dataset(
    DATASET_NAME,
    "en",
    split="test",
)


# ============================================================
# DOWNLOAD ARABIC
# ============================================================

print("\nDownloading Arabic Global-MGSM...")

arabic = load_dataset(
    DATASET_NAME,
    "ar",
    split="test",
)


print("\nEnglish rows:", len(english))
print("Arabic rows :", len(arabic))


# ============================================================
# BASIC VALIDATION
# ============================================================

if len(english) != len(arabic):

    raise RuntimeError(
        "Arabic and English dataset sizes are different. "
        "Do not continue until alignment is checked."
    )


if len(english) < SAMPLE_SIZE:

    raise RuntimeError(
        f"Dataset contains only {len(english)} rows, "
        f"but {SAMPLE_SIZE} were requested."
    )


# ============================================================
# VERIFY ANSWER ALIGNMENT ACROSS THE FULL DATASET
# ============================================================

print("\n" + "=" * 72)
print("CHECKING ARABIC-ENGLISH ANSWER ALIGNMENT")
print("=" * 72)


answer_mismatches = []


for index in range(
    len(english)
):

    en_answer = normalize_answer(
        english[index]["answer"]
    )

    ar_answer = normalize_answer(
        arabic[index]["answer"]
    )


    if en_answer != ar_answer:

        answer_mismatches.append({
            "index": index,
            "english_answer": en_answer,
            "arabic_answer": ar_answer,
        })


print(
    "\nAnswer mismatches:",
    len(answer_mismatches)
)


if answer_mismatches:

    print(
        "\nWARNING: datasets do not appear to be "
        "perfectly aligned row-by-row."
    )

    print(
        "\nFirst mismatches:"
    )

    for mismatch in answer_mismatches[:20]:

        print(
            mismatch
        )

    raise RuntimeError(
        "Stopping because English-Arabic answer "
        "alignment was not verified."
    )


print(
    "SUCCESS: all rows have matching "
    "Arabic-English ground-truth answers."
)


# ============================================================
# SELECT REPRODUCIBLE SAMPLE OF 100
# ============================================================

rng = random.Random(
    RANDOM_SEED
)


selected_indices = rng.sample(
    range(len(english)),
    SAMPLE_SIZE,
)


# Sort after sampling so results appear in dataset order
selected_indices = sorted(
    selected_indices
)


print("\n" + "=" * 72)
print("SELECTING 100 PROBLEMS")
print("=" * 72)


print(
    "\nRandom seed:",
    RANDOM_SEED
)

print(
    "Selected problems:",
    len(selected_indices)
)


# ============================================================
# BUILD MATCHED RECORDS
# ============================================================

records = []

number_mismatch_count = 0


for new_id, source_index in enumerate(
    selected_indices,
    start=1,
):

    en = english[
        source_index
    ]

    ar = arabic[
        source_index
    ]


    question_en = str(
        en["question"]
    ).strip()


    question_ar = str(
        ar["question"]
    ).strip()


    gold_answer = normalize_answer(
        en["answer"]
    )


    numbers_en = extract_numbers(
        question_en
    )


    numbers_ar = extract_numbers(
        question_ar
    )


    numbers_match = (
        sorted(numbers_en)
        ==
        sorted(numbers_ar)
    )


    if not numbers_match:

        number_mismatch_count += 1


    record = {

        "id":
            new_id,

        "source_index":
            source_index,

        "question_en":
            question_en,

        "question_ar":
            question_ar,

        "gold_answer":
            gold_answer,

        "instruction_en":
            str(
                en["instruction"]
            ).strip(),

        "instruction_ar":
            str(
                ar["instruction"]
            ).strip(),

        "answer_prefix_en":
            str(
                en["answer_prefix"]
            ).strip(),

        "answer_prefix_ar":
            str(
                ar["answer_prefix"]
            ).strip(),

        "numbers_en":
            json.dumps(
                numbers_en,
                ensure_ascii=False
            ),

        "numbers_ar":
            json.dumps(
                numbers_ar,
                ensure_ascii=False
            ),

        "question_numbers_match":
            numbers_match,

        "manual_review":
            "PENDING",
    }


    records.append(
        record
    )


# ============================================================
# SAVE JSONL
# ============================================================

with JSONL_OUTPUT.open(
    "w",
    encoding="utf-8",
) as file:

    for record in records:

        file.write(
            json.dumps(
                record,
                ensure_ascii=False
            )
            + "\n"
        )


# ============================================================
# SAVE REVIEW CSV
# ============================================================

df = pd.DataFrame(
    records
)


df.to_csv(
    CSV_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# VALIDATE OUTPUT
# ============================================================

print("\n" + "=" * 72)
print("FINAL VALIDATION")
print("=" * 72)


print(
    "\nMatched problems:",
    len(records)
)


print(
    "Unique IDs:",
    df["id"].nunique()
)


print(
    "Unique source indices:",
    df["source_index"].nunique()
)


print(
    "Question-number mismatches:",
    number_mismatch_count
)


missing_english = (
    df["question_en"]
    .astype(str)
    .str.strip()
    .eq("")
    .sum()
)


missing_arabic = (
    df["question_ar"]
    .astype(str)
    .str.strip()
    .eq("")
    .sum()
)


missing_answers = (
    df["gold_answer"]
    .astype(str)
    .str.strip()
    .eq("")
    .sum()
)


print(
    "Missing English questions:",
    missing_english
)

print(
    "Missing Arabic questions :",
    missing_arabic
)

print(
    "Missing answers          :",
    missing_answers
)


if len(records) != 100:

    raise RuntimeError(
        "Expected exactly 100 records."
    )


if df["id"].nunique() != 100:

    raise RuntimeError(
        "Problem IDs are not unique."
    )


if df["source_index"].nunique() != 100:

    raise RuntimeError(
        "Source indices are not unique."
    )


if (
    missing_english
    or missing_arabic
    or missing_answers
):

    raise RuntimeError(
        "Dataset contains missing values."
    )


# ============================================================
# DISPLAY FIRST 5
# ============================================================

print("\n" + "=" * 72)
print("FIRST FIVE MATCHED PROBLEMS")
print("=" * 72)


for record in records[:5]:

    print(
        f"\nProblem {record['id']}"
    )

    print(
        "Source index:",
        record["source_index"]
    )

    print(
        "Answer:",
        record["gold_answer"]
    )

    print(
        "\nEN:",
        record["question_en"]
    )

    print(
        "\nAR:",
        record["question_ar"]
    )

    print(
        "\nNumbers match:",
        record[
            "question_numbers_match"
        ]
    )

    print(
        "-" * 72
    )


# ============================================================
# FINISH
# ============================================================

print("\n" + "=" * 72)
print("DATASET BUILD COMPLETE")
print("=" * 72)


print(
    "\nJSONL:"
)

print(
    JSONL_OUTPUT
)


print(
    "\nReview CSV:"
)

print(
    CSV_OUTPUT
)


if number_mismatch_count == 0:

    print(
        "\nAll 100 selected problems preserved "
        "their explicit numerical quantities."
    )

else:

    print(
        f"\nIMPORTANT: {number_mismatch_count} problems "
        "have different explicit numeric tokens between "
        "Arabic and English."
    )

    print(
        "Inspect those rows manually before evaluation."
    )


print(
    "\nNEXT STEP:"
)

print(
    "Run Qwen and Gemma on the verified "
    "100-problem bilingual dataset."
)