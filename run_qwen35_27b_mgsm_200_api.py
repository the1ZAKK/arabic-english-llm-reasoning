import argparse
import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openai import OpenAI, APIStatusError


# ============================================================
# CONFIG
# ============================================================

DATASET_FILE = (
    Path("data")
    / "processed"
    / "global_mgsm_ar_en_200.jsonl"
)

OUTPUT_FILE = Path(
    "qwen35_27b_mgsm_200_results.csv"
)

MODEL_NAME = "qwen/qwen3.5-27b"
API_PROVIDER = "Novita AI"

BASE_URL = "https://api.novita.ai/openai"

MAX_TOKENS = 512
TEMPERATURE = 0

EXPECTED_PROBLEMS = 200
EXPECTED_EVALUATIONS = 400

MAX_RETRIES = 3


# ============================================================
# ARGUMENTS
# ============================================================

parser = argparse.ArgumentParser()

parser.add_argument(
    "--limit",
    type=int,
    default=200,
    help="Number of problems to process, starting from problem 1.",
)

args = parser.parse_args()

if args.limit < 1 or args.limit > 200:
    raise ValueError("--limit must be between 1 and 200.")


# ============================================================
# API KEY
# ============================================================

api_key = os.getenv("NOVITA_API_KEY")

if not api_key:
    raise RuntimeError(
        "NOVITA_API_KEY is not set in this CMD session."
    )


# ============================================================
# CLIENT
# ============================================================

client = OpenAI(
    api_key=api_key,
    base_url=BASE_URL,
    timeout=90.0,
    max_retries=0,
)


# ============================================================
# LOAD DATASET
# ============================================================

if not DATASET_FILE.exists():
    raise FileNotFoundError(
        f"Dataset not found: {DATASET_FILE}"
    )


records = []

with DATASET_FILE.open(
    "r",
    encoding="utf-8",
) as f:

    for line in f:
        line = line.strip()

        if line:
            records.append(
                json.loads(line)
            )


if len(records) != EXPECTED_PROBLEMS:
    raise RuntimeError(
        f"Expected {EXPECTED_PROBLEMS} problems, "
        f"found {len(records)}."
    )


ids = [
    int(record["id"])
    for record in records
]

if sorted(ids) != list(range(1, 201)):
    raise RuntimeError(
        "Dataset IDs are not exactly 1 through 200."
    )


records = sorted(
    records,
    key=lambda x: int(x["id"]),
)

records = records[:args.limit]


print("=" * 76)
print("QWEN3.5-27B API - MGSM 200 BILINGUAL EXPERIMENT")
print("=" * 76)

print("\nProvider:")
print(API_PROVIDER)

print("\nModel:")
print(MODEL_NAME)

print("\nDataset:")
print(DATASET_FILE)

print("\nProblems available:", EXPECTED_PROBLEMS)
print("Problems selected:", len(records))
print("Languages per problem: 2")
print(
    "Evaluations selected:",
    len(records) * 2,
)

print("\nTemperature:", TEMPERATURE)
print("Max tokens:", MAX_TOKENS)


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

    value = normalize_digits(value)

    value = value.strip()

    value = value.replace(",", "")
    value = value.replace("٬", "")
    value = value.replace("٫", ".")
    value = value.replace("$", "")

    value = value.strip()

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


# ============================================================
# NUMERIC COMPARISON
# ============================================================

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


# ============================================================
# BUILD PROMPT
#
# Same bilingual prompt structure as previous MGSM experiment.
# User-only message: no manually added system prompt.
# ============================================================

def build_messages(question, language):

    if language == "english":

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

    elif language == "arabic":

        prompt = (
            "حل المسألة الرياضية التالية بعناية. "
            "استدل خطوة بخطوة باستخدام المعلومات الواردة في المسألة فقط. "
            "لا تغيّر الكميات أو معنى المسألة. "
            "في النهاية، قدم إجابة رقمية نهائية واحدة فقط بهذا الشكل:\n"
            "الإجابة النهائية: <number>\n\n"
            "المسألة:\n"
            f"{question}"
        )

    else:

        raise ValueError(
            f"Unknown language: {language}"
        )

    return [
        {
            "role": "user",
            "content": prompt,
        }
    ]


# ============================================================
# ANSWER EXTRACTION
# ============================================================

NUMBER_PATTERN = (
    r"[-+]?"
    r"(?:\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.\d+)?"
)


def extract_answer(response):

    text = normalize_digits(
        response
    )

    explicit_matches = []

    patterns = [
        (
            "english_final_marker",
            rf"FINAL\s+ANSWER\s*:\s*({NUMBER_PATTERN})",
        ),
        (
            "arabic_final_marker",
            rf"الإجابة\s+النهائية\s*:\s*({NUMBER_PATTERN})",
        ),
    ]

    for method, pattern in patterns:

        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):

            explicit_matches.append({
                "position": match.start(),
                "value": normalize_number(
                    match.group(1)
                ),
                "method": method,
            })

    # --------------------------------------------------------
    # Requested explicit final-answer markers
    # --------------------------------------------------------

    if explicit_matches:

        explicit_matches.sort(
            key=lambda x: x["position"]
        )

        first = explicit_matches[0]

        unique_values = {
            item["value"]
            for item in explicit_matches
        }

        conflict = (
            len(unique_values) > 1
        )

        return {
            "answer": first["value"],
            "method": first["method"],
            "needs_manual_review": int(
                conflict
            ),
            "review_reason": (
                "conflicting_explicit_final_answers"
                if conflict
                else ""
            ),
            "all_explicit_answers": "|".join(
                item["value"]
                for item in explicit_matches
            ),
        }

    # --------------------------------------------------------
    # Boxed answer
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Last-number fallback
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # No numeric answer
    # --------------------------------------------------------

    return {
        "answer": None,
        "method": "no_number",
        "needs_manual_review": 1,
        "review_reason": "no_numeric_answer",
        "all_explicit_answers": "",
    }


# ============================================================
# API GENERATION
# ============================================================

def solve(question, language):

    messages = build_messages(
        question,
        language,
    )

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            start = time.perf_counter()

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )

            elapsed = (
                time.perf_counter()
                - start
            )

            choice = response.choices[0]

            message = choice.message

            content = (
                message.content
                or ""
            ).strip()

            # Some reasoning APIs may expose reasoning separately.
            reasoning_content = getattr(
                message,
                "reasoning_content",
                None,
            )

            if reasoning_content is None:
                reasoning_content = ""

            reasoning_content = str(
                reasoning_content
            )

            usage = response.usage

            input_tokens = None
            output_tokens = None
            total_tokens = None
            usage_details = ""

            if usage is not None:

                input_tokens = getattr(
                    usage,
                    "prompt_tokens",
                    None,
                )

                output_tokens = getattr(
                    usage,
                    "completion_tokens",
                    None,
                )

                total_tokens = getattr(
                    usage,
                    "total_tokens",
                    None,
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

            return {
                "response": content,
                "reasoning_content": reasoning_content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "usage_details": usage_details,
                "seconds": elapsed,
                "finish_reason": choice.finish_reason or "",
                "api_response_id": getattr(
                    response,
                    "id",
                    "",
                ),
            }

        except APIStatusError as e:

            last_error = e

            status_code = getattr(
                e,
                "status_code",
                None,
            )

            print(
                f"\nAPI error {status_code} "
                f"(attempt {attempt}/{MAX_RETRIES}): {e}"
            )

            # Authentication/payment problems should not be retried.
            if status_code in {
                400,
                401,
                402,
                403,
            }:
                raise

            if attempt < MAX_RETRIES:

                wait_seconds = min(
                    2 ** attempt,
                    30,
                )

                print(
                    f"Waiting {wait_seconds} seconds..."
                )

                time.sleep(
                    wait_seconds
                )

        except Exception as e:

            last_error = e

            print(
                f"\nRequest error "
                f"(attempt {attempt}/{MAX_RETRIES}): {e}"
            )

            if attempt < MAX_RETRIES:

                wait_seconds = min(
                    2 ** attempt,
                    30,
                )

                print(
                    f"Waiting {wait_seconds} seconds..."
                )

                time.sleep(
                    wait_seconds
                )

    raise RuntimeError(
        f"Request failed after {MAX_RETRIES} attempts: "
        f"{last_error}"
    )


# ============================================================
# CSV FIELDS
# ============================================================

FIELDNAMES = [
    "problem_id",
    "source_index",
    "model",
    "provider",
    "language",
    "gold_answer",
    "extracted_answer",
    "is_correct",
    "extraction_method",
    "needs_manual_review",
    "review_reason",
    "all_explicit_answers",
    "question",
    "generated_response",
    "reasoning_content",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "usage_details",
    "generation_seconds",
    "finish_reason",
    "api_response_id",
    "temperature",
    "max_tokens",
    "timestamp_utc",
    "status",
    "error",
]


# ============================================================
# SAFE SAVE
# ============================================================

def save_results(results_by_key):

    language_order = {
        "english": 0,
        "arabic": 1,
    }

    rows = sorted(
        results_by_key.values(),
        key=lambda row: (
            int(row["problem_id"]),
            language_order.get(
                row["language"],
                99,
            ),
        ),
    )

    temp_file = OUTPUT_FILE.with_suffix(
        ".tmp"
    )

    with temp_file.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=FIELDNAMES,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )

    temp_file.replace(
        OUTPUT_FILE
    )


# ============================================================
# RESUME EXISTING RESULTS
# ============================================================

results_by_key = {}
completed_keys = set()


if OUTPUT_FILE.exists():

    print("\n" + "=" * 76)
    print("RESUME MODE")
    print("=" * 76)

    with OUTPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            problem_id = int(
                row["problem_id"]
            )

            language = row[
                "language"
            ]

            key = (
                problem_id,
                language,
            )

            results_by_key[
                key
            ] = row

            if row.get(
                "status"
            ) == "success":

                completed_keys.add(
                    key
                )

    print(
        "\nExisting rows:",
        len(results_by_key),
    )

    print(
        "Successful evaluations:",
        len(completed_keys),
    )


# ============================================================
# RUN
# ============================================================

print("\n" + "=" * 76)
print("STARTING / RESUMING API EVALUATION")
print("=" * 76)


for record in records:

    problem_id = int(
        record["id"]
    )

    source_index = record.get(
        "source_index",
        "",
    )

    gold_answer = record[
        "gold_answer"
    ]

    # Alternate language order to reduce systematic order effects.
    if problem_id % 2 == 1:

        language_order = [
            "english",
            "arabic",
        ]

    else:

        language_order = [
            "arabic",
            "english",
        ]

    for language in language_order:

        key = (
            problem_id,
            language,
        )

        if key in completed_keys:

            print(
                f"[SKIP] Problem {problem_id:03d} "
                f"{language} already complete."
            )

            continue

        if language == "english":

            question = record[
                "question_en"
            ]

        else:

            question = record[
                "question_ar"
            ]

        completed_before = len(
            completed_keys
        )

        target_total = (
            len(records) * 2
        )

        print("\n" + "-" * 76)

        print(
            f"Problem {problem_id:03d} | "
            f"{language.upper()} | "
            f"completed {completed_before}/{target_total}"
        )

        print("-" * 76)

        try:

            generation = solve(
                question,
                language,
            )

            extracted = extract_answer(
                generation["response"]
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

            needs_review = int(
                extracted[
                    "needs_manual_review"
                ]
            )

            review_reason = extracted[
                "review_reason"
            ]

            # If the API terminated because of length,
            # flag for manual review even if a number was extracted.
            if (
                generation[
                    "finish_reason"
                ]
                ==
                "length"
            ):

                needs_review = 1

                if review_reason:
                    review_reason += (
                        "|generation_truncated"
                    )
                else:
                    review_reason = (
                        "generation_truncated"
                    )

            row = {
                "problem_id": problem_id,
                "source_index": source_index,
                "model": MODEL_NAME,
                "provider": API_PROVIDER,
                "language": language,
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
                "needs_manual_review": needs_review,
                "review_reason": review_reason,
                "all_explicit_answers": extracted[
                    "all_explicit_answers"
                ],
                "question": question,
                "generated_response": generation[
                    "response"
                ],
                "reasoning_content": generation[
                    "reasoning_content"
                ],
                "input_tokens": generation[
                    "input_tokens"
                ],
                "output_tokens": generation[
                    "output_tokens"
                ],
                "total_tokens": generation[
                    "total_tokens"
                ],
                "usage_details": generation[
                    "usage_details"
                ],
                "generation_seconds": round(
                    generation[
                        "seconds"
                    ],
                    4,
                ),
                "finish_reason": generation[
                    "finish_reason"
                ],
                "api_response_id": generation[
                    "api_response_id"
                ],
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "timestamp_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "status": "success",
                "error": "",
            }

            results_by_key[
                key
            ] = row

            completed_keys.add(
                key
            )

            save_results(
                results_by_key
            )

            print(
                "Gold answer:",
                gold_answer,
            )

            print(
                "Extracted answer:",
                predicted,
            )

            print(
                "Correct:",
                correct,
            )

            print(
                "Extraction:",
                extracted["method"],
            )

            print(
                "Manual review:",
                needs_review,
            )

            print(
                "Input tokens:",
                generation[
                    "input_tokens"
                ],
            )

            print(
                "Output tokens:",
                generation[
                    "output_tokens"
                ],
            )

            print(
                "Finish reason:",
                generation[
                    "finish_reason"
                ],
            )

            print(
                "Seconds:",
                round(
                    generation[
                        "seconds"
                    ],
                    2,
                ),
            )

        except KeyboardInterrupt:

            print(
                "\n\nInterrupted by user."
            )

            print(
                "Progress has already been saved."
            )

            raise

        except Exception as e:

            print(
                "\nERROR:",
                repr(e),
            )

            error_row = {
                "problem_id": problem_id,
                "source_index": source_index,
                "model": MODEL_NAME,
                "provider": API_PROVIDER,
                "language": language,
                "gold_answer": gold_answer,
                "extracted_answer": "",
                "is_correct": "",
                "extraction_method": "",
                "needs_manual_review": 1,
                "review_reason": "api_error",
                "all_explicit_answers": "",
                "question": question,
                "generated_response": "",
                "reasoning_content": "",
                "input_tokens": "",
                "output_tokens": "",
                "total_tokens": "",
                "usage_details": "",
                "generation_seconds": "",
                "finish_reason": "",
                "api_response_id": "",
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "timestamp_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "status": "error",
                "error": repr(e),
            }

            results_by_key[
                key
            ] = error_row

            save_results(
                results_by_key
            )

            # Authentication/payment errors should stop the run
            # instead of spending time repeatedly failing.
            if isinstance(
                e,
                APIStatusError,
            ):

                status_code = getattr(
                    e,
                    "status_code",
                    None,
                )

                if status_code in {
                    400,
                    401,
                    402,
                    403,
                }:

                    print(
                        "\nFatal API/account error. "
                        "Stopping experiment."
                    )

                    raise


# ============================================================
# FINAL SUMMARY
# ============================================================

selected_ids = {
    int(record["id"])
    for record in records
}

successful_selected = [
    row
    for row in results_by_key.values()
    if (
        int(row["problem_id"])
        in selected_ids
        and row["status"] == "success"
    )
]

english_rows = [
    row
    for row in successful_selected
    if row["language"] == "english"
]

arabic_rows = [
    row
    for row in successful_selected
    if row["language"] == "arabic"
]


english_correct = sum(
    int(row["is_correct"])
    for row in english_rows
)

arabic_correct = sum(
    int(row["is_correct"])
    for row in arabic_rows
)


print("\n" + "=" * 76)
print("RUN SUMMARY")
print("=" * 76)

print(
    "\nSuccessful selected evaluations:",
    len(successful_selected),
    "/",
    len(records) * 2,
)

print(
    "English evaluations:",
    len(english_rows),
)

print(
    "Arabic evaluations:",
    len(arabic_rows),
)


if english_rows:

    print(
        "\nEnglish automatic accuracy:",
        f"{english_correct}/{len(english_rows)}",
        f"= {english_correct / len(english_rows):.4f}",
    )


if arabic_rows:

    print(
        "Arabic automatic accuracy:",
        f"{arabic_correct}/{len(arabic_rows)}",
        f"= {arabic_correct / len(arabic_rows):.4f}",
    )


if english_rows and arabic_rows:

    english_accuracy = (
        english_correct
        / len(english_rows)
    )

    arabic_accuracy = (
        arabic_correct
        / len(arabic_rows)
    )

    print(
        "Automatic English-Arabic gap:",
        f"{english_accuracy - arabic_accuracy:+.4f}",
    )


review_count = sum(
    int(row["needs_manual_review"])
    for row in successful_selected
)


print(
    "\nRows requiring manual review:",
    review_count,
)


total_input_tokens = sum(
    int(row["input_tokens"])
    for row in successful_selected
    if str(row["input_tokens"]).strip()
)

total_output_tokens = sum(
    int(row["output_tokens"])
    for row in successful_selected
    if str(row["output_tokens"]).strip()
)


print(
    "\nTotal reported input tokens:",
    total_input_tokens,
)

print(
    "Total reported output tokens:",
    total_output_tokens,
)

print(
    "\nResults saved to:",
    OUTPUT_FILE,
)

print("\nDone.")