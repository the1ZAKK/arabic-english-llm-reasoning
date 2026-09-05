import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openai import OpenAI


DATASET_FILE = (
    Path("data")
    / "processed"
    / "global_mgsm_ar_en_200.jsonl"
)

OUTPUT_FILE = Path(
    "qwen35_27b_mgsm_200_results.csv"
)

MODEL_NAME = "qwen/qwen3.5-27b"
BASE_URL = "https://api.novita.ai/openai"

PROBLEM_ID = 38
LANGUAGE = "english"

MAX_TOKENS = 512
TEMPERATURE = 0


api_key = os.getenv("NOVITA_API_KEY")

if not api_key:
    raise RuntimeError(
        "NOVITA_API_KEY is not set."
    )


client = OpenAI(
    api_key=api_key,
    base_url=BASE_URL,
    timeout=300.0,
    max_retries=0,
)


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


def normalize_number(value):

    if value is None:
        return None

    value = normalize_digits(value)

    value = (
        value.strip()
        .replace(",", "")
        .replace("٬", "")
        .replace("٫", ".")
        .replace("$", "")
        .strip()
    )

    try:

        number = Decimal(value)

        if number == number.to_integral():
            return str(int(number))

        return format(
            number.normalize(),
            "f",
        )

    except InvalidOperation:

        return value


def numeric_equal(predicted, expected):

    if predicted is None:
        return False

    predicted = normalize_number(
        predicted
    )

    expected = normalize_number(
        expected
    )

    try:

        return (
            Decimal(predicted)
            ==
            Decimal(expected)
        )

    except Exception:

        return predicted == expected


NUMBER_PATTERN = (
    r"[-+]?"
    r"(?:\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.\d+)?"
)


def extract_answer(response):

    text = normalize_digits(
        response
    )

    matches = list(
        re.finditer(
            rf"FINAL\s+ANSWER\s*:\s*({NUMBER_PATTERN})",
            text,
            flags=re.IGNORECASE,
        )
    )

    if matches:

        values = [
            normalize_number(
                m.group(1)
            )
            for m in matches
        ]

        conflict = (
            len(set(values)) > 1
        )

        return {
            "answer": values[0],
            "method": "english_final_marker",
            "needs_manual_review": int(
                conflict
            ),
            "review_reason": (
                "conflicting_explicit_final_answers"
                if conflict
                else ""
            ),
            "all_explicit_answers": "|".join(
                values
            ),
        }

    boxed = list(
        re.finditer(
            rf"\\boxed\s*\{{\s*({NUMBER_PATTERN})\s*\}}",
            text,
        )
    )

    if boxed:

        value = normalize_number(
            boxed[-1].group(1)
        )

        return {
            "answer": value,
            "method": "boxed",
            "needs_manual_review": 1,
            "review_reason": "no_requested_final_marker",
            "all_explicit_answers": value,
        }

    numbers = re.findall(
        NUMBER_PATTERN,
        text,
    )

    if numbers:

        value = normalize_number(
            numbers[-1]
        )

        return {
            "answer": value,
            "method": "last_number_fallback",
            "needs_manual_review": 1,
            "review_reason": "fallback_extraction",
            "all_explicit_answers": "",
        }

    return {
        "answer": None,
        "method": "no_number",
        "needs_manual_review": 1,
        "review_reason": "no_numeric_answer",
        "all_explicit_answers": "",
    }


# ------------------------------------------------------------
# Load problem 38
# ------------------------------------------------------------

records = []

with DATASET_FILE.open(
    "r",
    encoding="utf-8",
) as f:

    for line in f:

        if line.strip():
            records.append(
                json.loads(line)
            )


record = next(
    x
    for x in records
    if int(x["id"]) == PROBLEM_ID
)


question = record[
    "question_en"
]

gold_answer = record[
    "gold_answer"
]


prompt = (
    "Solve the following mathematics problem carefully. "
    "Reason step by step using only the information in the problem. "
    "Do not change the quantities or meaning of the problem. "
    "At the end, provide exactly one final numerical answer using "
    "this format:\n"
    "FINAL ANSWER: <number>\n\n"
    "Problem:\n"
    f"{question}"
)


print("=" * 76)
print("REPAIRING QWEN3.5-27B PROBLEM 38 ENGLISH")
print("=" * 76)

print("\nQuestion:")
print(question)

print("\nGold answer:")
print(gold_answer)

print("\nSending streaming request with 300-second timeout...")


start = time.perf_counter()

stream = client.chat.completions.create(
    model=MODEL_NAME,
    messages=[
        {
            "role": "user",
            "content": prompt,
        }
    ],
    temperature=TEMPERATURE,
    max_tokens=MAX_TOKENS,
    stream=True,
    stream_options={
        "include_usage": True
    },
)

content_parts = []
reasoning_parts = []

input_tokens = ""
output_tokens = ""
total_tokens = ""

finish_reason = ""
api_response_id = ""
usage_details = ""


print("\nStreaming response...\n")


for chunk in stream:

    if getattr(
        chunk,
        "id",
        None,
    ):
        api_response_id = chunk.id

    if getattr(
        chunk,
        "usage",
        None,
    ):

        usage = chunk.usage

        input_tokens = getattr(
            usage,
            "prompt_tokens",
            "",
        )

        output_tokens = getattr(
            usage,
            "completion_tokens",
            "",
        )

        total_tokens = getattr(
            usage,
            "total_tokens",
            "",
        )

        try:

            usage_details = json.dumps(
                usage.model_dump(),
                ensure_ascii=False,
            )

        except Exception:

            usage_details = str(
                usage
            )

    if not chunk.choices:
        continue

    delta = chunk.choices[0].delta

    piece = getattr(
        delta,
        "content",
        None,
    )

    if piece:

        content_parts.append(
            piece
        )

        print(
            piece,
            end="",
            flush=True,
        )

    reasoning_piece = getattr(
        delta,
        "reasoning_content",
        None,
    )

    if reasoning_piece:

        reasoning_parts.append(
            reasoning_piece
        )

    if chunk.choices[0].finish_reason:

        finish_reason = (
            chunk.choices[0].finish_reason
        )


elapsed = (
    time.perf_counter()
    - start
)


content = "".join(
    content_parts
).strip()


reasoning_content = "".join(
    reasoning_parts
)


print("\n\nStreaming finished.")


extracted = extract_answer(
    content
)

predicted = extracted[
    "answer"
]


correct = int(
    numeric_equal(
        predicted,
        gold_answer,
    )
)


# If the generation ended due to the output limit,
# force manual review.
needs_manual_review = int(
    extracted[
        "needs_manual_review"
    ]
)

review_reason = extracted[
    "review_reason"
]


if finish_reason == "length":

    needs_manual_review = 1

    if review_reason:

        review_reason += (
            "|generation_truncated"
        )

    else:

        review_reason = (
            "generation_truncated"
        )


print("\n" + "=" * 76)
print("RESULT")
print("=" * 76)

print("\nResponse:")
print(content)

print("\nGold answer:", gold_answer)
print("Extracted:", predicted)
print("Correct:", correct)
print(
    "Extraction method:",
    extracted["method"],
)
print(
    "Manual review:",
    needs_manual_review,
)
print(
    "Review reason:",
    review_reason,
)
print(
    "Input tokens:",
    input_tokens,
)
print(
    "Output tokens:",
    output_tokens,
)
print(
    "Total tokens:",
    total_tokens,
)
print(
    "Finish reason:",
    finish_reason,
)
print(
    "Seconds:",
    round(
        elapsed,
        2,
    ),
)


# ------------------------------------------------------------
# Safety check:
# require at least some generated text before replacing CSV row
# ------------------------------------------------------------

if not content:

    raise RuntimeError(
        "The streaming request returned no visible response. "
        "The CSV will NOT be modified."
    )


# ------------------------------------------------------------
# Replace only the failed CSV row
# ------------------------------------------------------------

with OUTPUT_FILE.open(
    "r",
    encoding="utf-8-sig",
) as f:

    reader = csv.DictReader(
        f
    )

    fieldnames = reader.fieldnames

    rows = list(
        reader
    )


replacement = {
    "problem_id": PROBLEM_ID,
    "source_index": record.get(
        "source_index",
        "",
    ),
    "model": MODEL_NAME,
    "provider": "Novita AI",
    "language": LANGUAGE,
    "gold_answer": gold_answer,
    "extracted_answer": (
        predicted
        if predicted is not None
        else ""
    ),
    "is_correct": correct,
    "extraction_method": extracted[
        "method"
    ],
    "needs_manual_review": (
        needs_manual_review
    ),
    "review_reason": (
        review_reason
    ),
    "all_explicit_answers": extracted[
        "all_explicit_answers"
    ],
    "question": question,
    "generated_response": content,
    "reasoning_content": str(
        reasoning_content
    ),
    "input_tokens": input_tokens,
    "output_tokens": output_tokens,
    "total_tokens": total_tokens,
    "usage_details": usage_details,
    "generation_seconds": round(
        elapsed,
        4,
    ),
    "finish_reason": (
        finish_reason
    ),
    "api_response_id": (
        api_response_id
    ),
    "temperature": TEMPERATURE,
    "max_tokens": MAX_TOKENS,
    "timestamp_utc": datetime.now(
        timezone.utc
    ).isoformat(),
    "status": "success",
    "error": "",
}


found = False


for i, row in enumerate(
    rows
):

    if (
        int(row["problem_id"])
        == PROBLEM_ID
        and
        row["language"]
        == LANGUAGE
    ):

        rows[i] = replacement

        found = True

        break


if not found:

    raise RuntimeError(
        "Problem 38 English row not found. "
        "The CSV was not modified."
    )


temp_file = OUTPUT_FILE.with_suffix(
    ".repair.tmp"
)


with temp_file.open(
    "w",
    newline="",
    encoding="utf-8-sig",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames,
    )

    writer.writeheader()

    writer.writerows(
        rows
    )


temp_file.replace(
    OUTPUT_FILE
)


print("\n" + "=" * 76)
print("REPAIR COMPLETE")
print("=" * 76)

print(
    "\nProblem 38 English row replaced with success."
)

print(
    "Updated file:",
    OUTPUT_FILE,
)