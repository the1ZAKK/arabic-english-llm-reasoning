import argparse
import csv
import json
import re
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


# ============================================================
# CONFIG
# ============================================================

DATASET_FILE = (
    Path("data")
    / "processed"
    / "global_mgsm_ar_en_200.jsonl"
)

MODEL_CONFIGS = {
    "qwen": {
        "model_name": "Qwen/Qwen2.5-Math-1.5B-Instruct",
        "output_file": "qwen_mgsm_101_200_results.csv",
    },

    "gemma": {
        "model_name": "google/gemma-3-1b-it",
        "output_file": "gemma_mgsm_101_200_results.csv",
    },
}

FIRST_PROBLEM_ID = 101
LAST_PROBLEM_ID = 200

EXPECTED_PROBLEMS = 100
EXPECTED_EVALUATIONS = 200

MAX_NEW_TOKENS = 512

SEED = 42


# ============================================================
# ARGUMENTS
# ============================================================

parser = argparse.ArgumentParser()

parser.add_argument(
    "--model",
    required=True,
    choices=["qwen", "gemma"],
)

args = parser.parse_args()

MODEL_KEY = args.model

MODEL_NAME = MODEL_CONFIGS[
    MODEL_KEY
]["model_name"]

OUTPUT_FILE = MODEL_CONFIGS[
    MODEL_KEY
]["output_file"]


# ============================================================
# REPRODUCIBILITY
# ============================================================

torch.manual_seed(SEED)

if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)


# ============================================================
# LOAD DATASET
# ============================================================

if not DATASET_FILE.exists():

    raise FileNotFoundError(
        f"Dataset not found: {DATASET_FILE}"
    )


all_records = []

with DATASET_FILE.open(
    "r",
    encoding="utf-8",
) as f:

    for line in f:

        all_records.append(
            json.loads(line)
        )


# ------------------------------------------------------------
# Verify the complete 200-problem file first
# ------------------------------------------------------------

if len(all_records) != 200:

    raise RuntimeError(
        "The extension runner expects the complete "
        "200-problem dataset.\n"
        f"Found {len(all_records)} rows in {DATASET_FILE}."
    )


# ------------------------------------------------------------
# CRITICAL:
# Evaluate ONLY Problems 101-200.
#
# Problems 1-100 have already been generated and adjudicated.
# ------------------------------------------------------------

records = [

    row

    for row in all_records

    if (
        FIRST_PROBLEM_ID
        <= int(row["id"])
        <= LAST_PROBLEM_ID
    )

]


if len(records) != EXPECTED_PROBLEMS:

    raise RuntimeError(
        f"Expected {EXPECTED_PROBLEMS} extension problems "
        f"({FIRST_PROBLEM_ID}-{LAST_PROBLEM_ID}), "
        f"found {len(records)}."
    )


# ------------------------------------------------------------
# Verify exact IDs 101-200
# ------------------------------------------------------------

actual_ids = sorted(
    int(row["id"])
    for row in records
)

expected_ids = list(
    range(
        FIRST_PROBLEM_ID,
        LAST_PROBLEM_ID + 1,
    )
)


if actual_ids != expected_ids:

    raise RuntimeError(
        "Extension problem IDs are not exactly 101-200."
    )


print("=" * 76)

print(
    "MGSM PROBLEMS 101-200 "
    "BILINGUAL REASONING EXTENSION"
)

print("=" * 76)

print("\nModel:")
print(MODEL_NAME)

print("\nDataset:")
print(DATASET_FILE)

print(
    "\nFull dataset problems:",
    len(all_records)
)

print(
    "Extension problems:",
    len(records)
)

print(
    "Problem IDs:",
    f"{FIRST_PROBLEM_ID}-{LAST_PROBLEM_ID}"
)

print("Languages: 2")

print(
    "Total extension evaluations:",
    EXPECTED_EVALUATIONS
)

print(
    "\nIMPORTANT: Problems 1-100 will NOT be generated."
)


# ============================================================
# DEVICE
# ============================================================

print("\n" + "=" * 76)
print("DEVICE")
print("=" * 76)


if torch.cuda.is_available():

    print(
        "\nGPU:",
        torch.cuda.get_device_name(0)
    )

    print(
        "VRAM:",
        round(
            torch.cuda.get_device_properties(0).total_memory
            / 1024**3,
            2
        ),
        "GB",
    )

else:

    print(
        "\nCUDA unavailable. Using CPU."
    )


# ============================================================
# LOAD TOKENIZER
# ============================================================

print("\n" + "=" * 76)
print("LOADING TOKENIZER")
print("=" * 76)


tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME
)


if tokenizer.pad_token_id is None:

    tokenizer.pad_token_id = (
        tokenizer.eos_token_id
    )


print(
    "\nTokenizer loaded."
)


# ============================================================
# LOAD MODEL
# ============================================================

print("\n" + "=" * 76)
print("LOADING MODEL")
print("=" * 76)


if torch.cuda.is_available():

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        dtype=torch.float16,
        device_map="auto",
    )

else:

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        dtype=torch.float32,
    )


model.eval()


try:

    model_device = (
        model.model
        .embed_tokens
        .weight
        .device
    )

except Exception:

    model_device = next(
        model.parameters()
    ).device


print(
    "\nModel loaded successfully."
)

print(
    "Input device:",
    model_device
)


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
# NUMERIC COMPARISON
# ============================================================

def numeric_equal(
    predicted,
    expected,
):

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

        return (
            predicted
            ==
            expected
        )


# ============================================================
# BUILD PROMPT
#
# IMPORTANT:
# Keep the same prompts used for Problems 1-100.
# ============================================================

def build_messages(
    question,
    language,
):

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
            language
        )


    return [
        {
            "role": "user",
            "content": prompt,
        }
    ]


# ============================================================
# ROBUST ANSWER EXTRACTION
#
# IMPORTANT:
# Keep the same automatic extraction behavior used in the
# original 100-problem generation experiment.
#
# Qwen can be reparsed later using the same Qwen-specific
# reparser used for Problems 1-100.
# ============================================================

NUMBER_PATTERN = (
    r"[-+]?"
    r"(?:\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.\d+)?"
)


def extract_answer(response):

    """
    Choose the FIRST explicit requested final-answer marker.

    Earlier experiments showed that a model can correctly answer
    and then enter repetitive generation. Choosing the final
    repeated marker can therefore create false negatives.

    If several explicit requested markers disagree, flag the
    response for manual review.
    """

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
                "position":
                    match.start(),

                "value":
                    normalize_number(
                        match.group(1)
                    ),

                "method":
                    method,
            })


    # --------------------------------------------------------
    # Explicit requested markers
    # --------------------------------------------------------

    if explicit_matches:

        explicit_matches.sort(
            key=lambda x: x["position"]
        )


        first = explicit_matches[
            0
        ]


        unique_values = {

            item["value"]

            for item in explicit_matches

        }


        conflict = (
            len(unique_values)
            >
            1
        )


        return {
            "answer":
                first["value"],

            "method":
                first["method"],

            "needs_manual_review":
                int(conflict),

            "review_reason":
                (
                    "conflicting_explicit_final_answers"
                    if conflict
                    else ""
                ),

            "all_explicit_answers":
                "|".join(
                    item["value"]
                    for item
                    in explicit_matches
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
            "answer":
                value,

            "method":
                "boxed",

            "needs_manual_review":
                1,

            "review_reason":
                "no_requested_final_marker",

            "all_explicit_answers":
                value,
        }


    # --------------------------------------------------------
    # Fallback: last number
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
            "answer":
                value,

            "method":
                "last_number_fallback",

            "needs_manual_review":
                1,

            "review_reason":
                "fallback_extraction",

            "all_explicit_answers":
                "",
        }


    # --------------------------------------------------------
    # No numeric answer
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

        "all_explicit_answers":
            "",
    }


# ============================================================
# GENERATE
# ============================================================

def solve(
    question,
    language,
):

    messages = build_messages(
        question,
        language,
    )


    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )


    inputs = tokenizer(
        prompt,
        return_tensors="pt",
    )


    inputs = {

        key:
            value.to(
                model_device
            )

        for key, value
        in inputs.items()

    }


    input_length = (
        inputs[
            "input_ids"
        ].shape[1]
    )


    start = (
        time.perf_counter()
    )


    with torch.inference_mode():

        generated = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
            use_cache=True,
        )


    elapsed = (
        time.perf_counter()
        -
        start
    )


    generated_ids = generated[
        0,
        input_length:
    ]


    response = tokenizer.decode(
        generated_ids,
        skip_special_tokens=True,
    ).strip()


    output_tokens = len(
        generated_ids
    )


    del generated
    del inputs


    if torch.cuda.is_available():

        torch.cuda.empty_cache()


    return {
        "response":
            response,

        "input_tokens":
            input_length,

        "output_tokens":
            output_tokens,

        "seconds":
            elapsed,
    }


# ============================================================
# CSV FIELDS
# ============================================================

FIELDNAMES = [
    "problem_id",
    "source_index",
    "model",
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
    "input_tokens",
    "output_tokens",
    "generation_seconds",
    "status",
]


# ============================================================
# RESULT STORAGE
#
# A dictionary keyed by:
#     (problem_id, language)
#
# prevents duplicate rows if a previous attempt failed and the
# script is later resumed successfully.
# ============================================================

results_by_key = {}


def sorted_results():

    def language_order(language):

        if language == "english":
            return 0

        return 1


    return sorted(

        results_by_key.values(),

        key=lambda row: (
            int(
                row["problem_id"]
            ),
            language_order(
                row["language"]
            ),
        ),

    )


# ============================================================
# SAVE
# ============================================================

def save_results():

    with open(
        OUTPUT_FILE,
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
            sorted_results()
        )


# ============================================================
# RESUME EXISTING RUN
# ============================================================

completed_keys = set()


if Path(
    OUTPUT_FILE
).exists():

    print(
        "\n"
        + "=" * 76
    )

    print(
        "RESUME MODE"
    )

    print(
        "=" * 76
    )


    with open(
        OUTPUT_FILE,
        "r",
        encoding="utf-8-sig",
    ) as f:

        reader = csv.DictReader(
            f
        )


        for row in reader:

            try:

                problem_id = int(
                    row[
                        "problem_id"
                    ]
                )

            except Exception:

                continue


            language = row.get(
                "language",
                ""
            )


            # Ignore accidental rows belonging
            # outside the extension.
            if not (
                FIRST_PROBLEM_ID
                <= problem_id
                <= LAST_PROBLEM_ID
            ):

                continue


            if language not in {
                "arabic",
                "english",
            }:

                continue


            key = (
                problem_id,
                language,
            )


            # Keep the latest row for each key.
            results_by_key[
                key
            ] = row


    # --------------------------------------------------------
    # Only successful rows count as completed.
    #
    # Error rows will therefore be retried and replaced.
    # --------------------------------------------------------

    completed_keys = {

        key

        for key, row
        in results_by_key.items()

        if row.get(
            "status"
        ) == "success"

    }


    print(
        "\nExisting unique rows:",
        len(
            results_by_key
        )
    )


    print(
        "Successful completed evaluations:",
        len(
            completed_keys
        )
    )


    error_rows = [

        key

        for key, row
        in results_by_key.items()

        if row.get(
            "status"
        ) != "success"

    ]


    print(
        "Rows that will be retried:",
        len(error_rows)
    )


# ============================================================
# RUN 200 EXTENSION EVALUATIONS
# ============================================================

print(
    "\n"
    + "=" * 76
)

print(
    "STARTING / RESUMING EXTENSION EVALUATION"
)

print(
    "=" * 76
)


planned = (
    EXPECTED_EVALUATIONS
)


current_completed = len(
    completed_keys
)


for record in records:

    problem_id = int(
        record["id"]
    )


    source_index = int(
        record["source_index"]
    )


    gold_answer = normalize_number(
        record["gold_answer"]
    )


    # --------------------------------------------------------
    # Alternate language order by problem.
    #
    # Odd IDs:  English -> Arabic
    # Even IDs: Arabic -> English
    #
    # This preserves the design used in Problems 1-100.
    # --------------------------------------------------------

    if problem_id % 2 == 1:

        cases = [
            (
                "english",
                record[
                    "question_en"
                ],
            ),

            (
                "arabic",
                record[
                    "question_ar"
                ],
            ),
        ]

    else:

        cases = [
            (
                "arabic",
                record[
                    "question_ar"
                ],
            ),

            (
                "english",
                record[
                    "question_en"
                ],
            ),
        ]


    for language, question in cases:

        key = (
            problem_id,
            language,
        )


        if key in completed_keys:

            continue


        print(
            "\n"
            + "-" * 76
        )


        print(
            f"[{current_completed + 1}/{planned}] "
            f"Problem {problem_id} "
            f"- {language.upper()}"
        )


        print(
            "Gold answer:",
            gold_answer
        )


        try:

            generation = solve(
                question,
                language,
            )


            extraction = extract_answer(
                generation[
                    "response"
                ]
            )


            predicted = extraction[
                "answer"
            ]


            correct = numeric_equal(
                predicted,
                gold_answer,
            )


            print(
                "\nExtracted:",
                predicted
            )


            print(
                "Correct:",
                correct
            )


            print(
                "Method:",
                extraction[
                    "method"
                ]
            )


            print(
                "Manual review:",
                bool(
                    extraction[
                        "needs_manual_review"
                    ]
                )
            )


            print(
                "Time:",
                f"{generation['seconds']:.2f}s"
            )


            new_row = {
                "problem_id":
                    problem_id,

                "source_index":
                    source_index,

                "model":
                    MODEL_KEY,

                "language":
                    language,

                "gold_answer":
                    gold_answer,

                "extracted_answer":
                    predicted,

                "is_correct":
                    int(
                        correct
                    ),

                "extraction_method":
                    extraction[
                        "method"
                    ],

                "needs_manual_review":
                    extraction[
                        "needs_manual_review"
                    ],

                "review_reason":
                    extraction[
                        "review_reason"
                    ],

                "all_explicit_answers":
                    extraction[
                        "all_explicit_answers"
                    ],

                "question":
                    question,

                "generated_response":
                    generation[
                        "response"
                    ],

                "input_tokens":
                    generation[
                        "input_tokens"
                    ],

                "output_tokens":
                    generation[
                        "output_tokens"
                    ],

                "generation_seconds":
                    generation[
                        "seconds"
                    ],

                "status":
                    "success",
            }


            # Replace any previous error row
            # for this exact problem/language.
            results_by_key[
                key
            ] = new_row


            completed_keys.add(
                key
            )


            current_completed += 1


        except Exception as error:

            print(
                "\nERROR:",
                type(error).__name__,
                str(error)
            )


            new_row = {
                "problem_id":
                    problem_id,

                "source_index":
                    source_index,

                "model":
                    MODEL_KEY,

                "language":
                    language,

                "gold_answer":
                    gold_answer,

                "extracted_answer":
                    "",

                "is_correct":
                    0,

                "extraction_method":
                    "error",

                "needs_manual_review":
                    1,

                "review_reason":
                    (
                        "generation_error:"
                        + type(error).__name__
                    ),

                "all_explicit_answers":
                    "",

                "question":
                    question,

                "generated_response":
                    "",

                "input_tokens":
                    "",

                "output_tokens":
                    "",

                "generation_seconds":
                    "",

                "status":
                    (
                        "ERROR:"
                        + type(error).__name__
                    ),
            }


            # Store only one row for the key.
            # A later rerun will replace it.
            results_by_key[
                key
            ] = new_row


        # ----------------------------------------------------
        # Save after every attempted generation.
        # ----------------------------------------------------

        save_results()


# ============================================================
# FINAL VALIDATION
# ============================================================

results = sorted_results()


successful_results = [

    row

    for row in results

    if row[
        "status"
    ] == "success"

]


failed_results = [

    row

    for row in results

    if row[
        "status"
    ] != "success"

]


print(
    "\n"
    + "=" * 76
)

print(
    "RUN VALIDATION"
)

print(
    "=" * 76
)


print(
    "\nUnique output rows:",
    len(results)
)


print(
    "Successful evaluations:",
    len(successful_results)
)


print(
    "Failed evaluations:",
    len(failed_results)
)


if failed_results:

    print(
        "\nWARNING: generation errors remain."
    )

    print(
        "Rerun the SAME command to retry them."
    )


# ============================================================
# AUTOMATIC RESULTS
# ============================================================

print(
    "\n"
    + "=" * 76
)

print(
    "AUTOMATIC RESULTS"
)

print(
    "=" * 76
)


for language in [
    "arabic",
    "english",
]:

    rows = [

        row

        for row
        in successful_results

        if row[
            "language"
        ] == language

    ]


    correct = sum(

        int(
            row[
                "is_correct"
            ]
        )

        for row in rows

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
# MANUAL REVIEW CASES
# ============================================================

review_cases = [

    row

    for row
    in successful_results

    if int(
        row[
            "needs_manual_review"
        ]
    ) == 1

]


print(
    "\n"
    + "=" * 76
)

print(
    "MANUAL REVIEW SUMMARY"
)

print(
    "=" * 76
)


print(
    "\nCases requiring manual review:",
    len(review_cases)
)


for row in review_cases:

    print(
        f"Problem "
        f"{int(row['problem_id']):3d} | "
        f"{row['language']:7s} | "
        f"gold={row['gold_answer']} | "
        f"pred={row['extracted_answer']} | "
        f"{row['review_reason']}"
    )


# ============================================================
# EXPERIMENT COMPLETE
# ============================================================

print(
    "\n"
    + "=" * 76
)

print(
    "EXTENSION RUN COMPLETE"
)

print(
    "=" * 76
)


print(
    "\nModel:",
    MODEL_NAME
)


print(
    "Output:",
    OUTPUT_FILE
)


print(
    "Problem range:",
    f"{FIRST_PROBLEM_ID}-{LAST_PROBLEM_ID}"
)


if (
    len(successful_results)
    ==
    EXPECTED_EVALUATIONS
):

    print(
        "\nSUCCESS: all 200 extension evaluations completed."
    )

else:

    print(
        "\nINCOMPLETE: rerun the same command until "
        "all 200 evaluations are successful."
    )


print(
    "\nDo not run final statistical analysis until "
    "manual-review cases and suspicious failures "
    "have been checked."
)