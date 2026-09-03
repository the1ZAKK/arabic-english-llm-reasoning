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

OLD_FILE = (
    Path("data")
    / "processed"
    / "global_mgsm_ar_en_100.jsonl"
)

OUTPUT_DIR = Path("data") / "processed"

JSONL_OUTPUT = (
    OUTPUT_DIR
    / "global_mgsm_ar_en_200.jsonl"
)

CSV_OUTPUT = (
    OUTPUT_DIR
    / "global_mgsm_ar_en_200_review.csv"
)

NEW_ONLY_CSV = (
    OUTPUT_DIR
    / "global_mgsm_ar_en_101_200_review.csv"
)

OLD_SIZE = 100
NEW_SIZE = 100
FINAL_SIZE = 200

EXTENSION_SEED = 42


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
    value = value.replace(",", "")
    value = value.replace("٬", "")
    value = value.replace("٫", ".")
    value = value.replace("$", "")
    value = value.replace(" ", "")

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

    return [
        normalize_answer(number)
        for number in numbers
    ]


# ============================================================
# LOAD ORIGINAL 100
# ============================================================

print("=" * 78)
print("EXTENDING GLOBAL-MGSM FROM 100 TO 200 MATCHED PROBLEMS")
print("=" * 78)


if not OLD_FILE.exists():

    raise FileNotFoundError(
        f"Original 100-problem file not found: {OLD_FILE}"
    )


old_records = []

with OLD_FILE.open(
    "r",
    encoding="utf-8",
) as f:

    for line in f:

        old_records.append(
            json.loads(line)
        )


if len(old_records) != OLD_SIZE:

    raise RuntimeError(
        f"Expected {OLD_SIZE} original problems, "
        f"found {len(old_records)}."
    )


old_ids = [
    int(row["id"])
    for row in old_records
]


if old_ids != list(
    range(1, 101)
):

    raise RuntimeError(
        "Original IDs are not exactly 1-100."
    )


old_source_indices = {
    int(row["source_index"])
    for row in old_records
}


if len(old_source_indices) != 100:

    raise RuntimeError(
        "Original source indices are not unique."
    )


print("\nOriginal problems:", len(old_records))
print("Original unique source indices:", len(old_source_indices))


# ============================================================
# LOAD COMPLETE DATASET
# ============================================================

print("\nLoading English Global-MGSM...")

english = load_dataset(
    DATASET_NAME,
    "en",
    split="test",
)


print("Loading Arabic Global-MGSM...")

arabic = load_dataset(
    DATASET_NAME,
    "ar",
    split="test",
)


print("\nEnglish rows:", len(english))
print("Arabic rows :", len(arabic))


if len(english) != len(arabic):

    raise RuntimeError(
        "Arabic and English dataset sizes differ."
    )


if len(english) < FINAL_SIZE:

    raise RuntimeError(
        "Dataset does not contain enough rows."
    )


# ============================================================
# VERIFY FULL ANSWER ALIGNMENT
# ============================================================

print("\n" + "=" * 78)
print("VERIFYING FULL ARABIC-ENGLISH ANSWER ALIGNMENT")
print("=" * 78)


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

        answer_mismatches.append(
            {
                "source_index": index,
                "english_answer": en_answer,
                "arabic_answer": ar_answer,
            }
        )


print("\nAnswer mismatches:", len(answer_mismatches))


if answer_mismatches:

    print(
        pd.DataFrame(
            answer_mismatches
        ).head(20)
    )

    raise RuntimeError(
        "Stopping because answer alignment failed."
    )


# ============================================================
# SELECT 100 NEW UNUSED PROBLEMS
# ============================================================

remaining_indices = [

    index

    for index in range(
        len(english)
    )

    if index not in old_source_indices

]


print("\nRemaining unused rows:", len(remaining_indices))


if len(remaining_indices) < NEW_SIZE:

    raise RuntimeError(
        "Not enough unused problems."
    )


rng = random.Random(
    EXTENSION_SEED
)


new_source_indices = rng.sample(
    remaining_indices,
    NEW_SIZE,
)


# Sort for stable dataset order
new_source_indices = sorted(
    new_source_indices
)


if (
    set(new_source_indices)
    &
    old_source_indices
):

    raise RuntimeError(
        "New sample overlaps the original 100."
    )


print("\nExtension seed:", EXTENSION_SEED)
print("New problems selected:", len(new_source_indices))


# ============================================================
# BUILD PROBLEMS 101-200
# ============================================================

new_records = []

number_mismatch_count = 0


for new_id, source_index in enumerate(
    new_source_indices,
    start=101,
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


    ar_answer = normalize_answer(
        ar["answer"]
    )


    if gold_answer != ar_answer:

        raise RuntimeError(
            f"Answer mismatch at source index {source_index}."
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
                ensure_ascii=False,
            ),

        "numbers_ar":
            json.dumps(
                numbers_ar,
                ensure_ascii=False,
            ),

        "question_numbers_match":
            numbers_match,

        "manual_review":
            "PENDING",
    }


    new_records.append(
        record
    )


# ============================================================
# COMBINE ORIGINAL + NEW
# ============================================================

records = (
    old_records
    +
    new_records
)


if len(records) != FINAL_SIZE:

    raise RuntimeError(
        f"Expected {FINAL_SIZE} total records, "
        f"found {len(records)}."
    )


df = pd.DataFrame(
    records
)


# ============================================================
# FINAL VALIDATION
# ============================================================

print("\n" + "=" * 78)
print("FINAL VALIDATION")
print("=" * 78)


print("\nMatched problems:", len(df))
print("Unique IDs:", df["id"].nunique())
print(
    "Unique source indices:",
    df["source_index"].nunique(),
)


if df["id"].nunique() != 200:

    raise RuntimeError(
        "Expected 200 unique IDs."
    )


if df["source_index"].nunique() != 200:

    raise RuntimeError(
        "Expected 200 unique source indices."
    )


expected_ids = list(
    range(1, 201)
)


actual_ids = (
    df["id"]
    .astype(int)
    .tolist()
)


if actual_ids != expected_ids:

    raise RuntimeError(
        "Problem IDs are not exactly 1-200."
    )


# ============================================================
# VERIFY ORIGINAL 100 WERE PRESERVED
# ============================================================

for position in range(100):

    old = old_records[position]
    combined = records[position]

    if old != combined:

        raise RuntimeError(
            f"Original Problem {position + 1} changed."
        )


print(
    "Original Problems 1-100 preserved exactly: YES"
)


print(
    "New Problems 101-200:",
    len(new_records)
)


print(
    "New numeric-token mismatches:",
    number_mismatch_count
)


# ============================================================
# SAVE FULL 200 JSONL
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


with JSONL_OUTPUT.open(
    "w",
    encoding="utf-8",
) as f:

    for record in records:

        f.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )


# ============================================================
# SAVE FULL REVIEW CSV
# ============================================================

df.to_csv(
    CSV_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# SAVE NEW 101-200 REVIEW FILE
# ============================================================

new_df = pd.DataFrame(
    new_records
)


new_df.to_csv(
    NEW_ONLY_CSV,
    index=False,
    encoding="utf-8-sig",
)


print("\n" + "=" * 78)
print("FILES CREATED")
print("=" * 78)


print("\n", JSONL_OUTPUT)
print(" ", CSV_OUTPUT)
print(" ", NEW_ONLY_CSV)


print("\n" + "=" * 78)
print("NEXT STEP")
print("=" * 78)


print(
    "\nSemantically review Problems 101-200 before "
    "running the additional model generations."
)