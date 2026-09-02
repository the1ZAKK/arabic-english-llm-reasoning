import ast
import csv
import re
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM


# ============================================================
# CONFIG
# ============================================================

MODEL_PATH = "google/gemma-3-1b-it"

ARABIC_SOURCE = "test_arabic_prm.py"
ENGLISH_SOURCE = "test_english_prm.py"

OUTPUT_FILE = "gemma3_reasoning_results.csv"

MAX_NEW_TOKENS = 256
SEED = 42


EXPECTED_ANSWERS = {
    1: 18,
    2: 17,
    3: 15,
    4: 18,
    5: 30,
    6: 4,
    7: 30,
    8: 35,
    9: 35,
    10: 32,
    11: 13,
    12: 48,
    13: 65,
    14: 30,
    15: 25,
    16: 100,
    17: 9,
    18: 28,
    19: 16,
    20: 84,
}


# ============================================================
# REPRODUCIBILITY
# ============================================================

torch.manual_seed(SEED)

if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)


# ============================================================
# LOAD EXISTING DATASET WITHOUT EXECUTING SOURCE SCRIPT
# ============================================================

def load_examples(path):

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {path}"
        )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    for node in tree.body:

        if isinstance(node, ast.Assign):

            for target in node.targets:

                if (
                    isinstance(target, ast.Name)
                    and target.id == "examples"
                ):

                    return ast.literal_eval(
                        node.value
                    )

    raise RuntimeError(
        f"Could not find examples = [...] in {path}"
    )


print("=" * 72)
print("GEMMA 3 BILINGUAL REASONING EXPERIMENT")
print("=" * 72)


arabic_examples = load_examples(
    ARABIC_SOURCE
)

english_examples = load_examples(
    ENGLISH_SOURCE
)


arabic_by_id = {
    int(x["id"]): x
    for x in arabic_examples
}

english_by_id = {
    int(x["id"]): x
    for x in english_examples
}


expected_ids = set(range(1, 21))


if set(arabic_by_id.keys()) != expected_ids:
    raise RuntimeError(
        "Arabic IDs must be exactly 1-20."
    )


if set(english_by_id.keys()) != expected_ids:
    raise RuntimeError(
        "English IDs must be exactly 1-20."
    )


print("\nArabic problems :", len(arabic_by_id))
print("English problems:", len(english_by_id))
print("Total evaluations: 40")


# ============================================================
# DEVICE INFO
# ============================================================

print("\n" + "=" * 72)
print("DEVICE")
print("=" * 72)


if torch.cuda.is_available():

    print(
        "GPU:",
        torch.cuda.get_device_name(0)
    )

    print(
        "VRAM:",
        round(
            torch.cuda.get_device_properties(0).total_memory
            / 1024**3,
            2
        ),
        "GB"
    )

else:

    print("CUDA not available - using CPU.")


# ============================================================
# LOAD GEMMA
# ============================================================

print("\n" + "=" * 72)
print("LOADING GEMMA 3 TOKENIZER")
print("=" * 72)


tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH
)


print("Tokenizer loaded.")


print("\n" + "=" * 72)
print("LOADING GEMMA 3 MODEL")
print("=" * 72)


if torch.cuda.is_available():

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        dtype=torch.float16,
        device_map="auto",
    )

else:

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        dtype=torch.float32,
    )


model.eval()


try:
    model_device = model.model.embed_tokens.weight.device

except Exception:
    model_device = next(model.parameters()).device


print("\nModel loaded successfully.")
print("Input device:", model_device)


# ============================================================
# PROMPTS
#
# Gemma uses a user/model chat structure.
# We therefore place the complete instruction in the user turn.
# ============================================================

def build_messages(problem, language):

    if language == "english":

        content = (
            "Solve the following mathematical problem carefully. "
            "Reason step by step and do not guess. "
            "Use the information exactly as stated in the problem. "
            "At the end, write exactly one final line in this format:\n"
            "FINAL ANSWER: <number>\n\n"
            "Problem:\n"
            f"{problem}"
        )

    elif language == "arabic":

        content = (
            "حل المسألة الرياضية التالية بعناية. "
            "استدل خطوة بخطوة ولا تخمن. "
            "استخدم المعلومات كما وردت في المسألة بالضبط. "
            "في النهاية، اكتب سطرًا نهائيًا واحدًا فقط بهذا الشكل:\n"
            "الإجابة النهائية: <number>\n\n"
            "المسألة:\n"
            f"{problem}"
        )

    else:
        raise ValueError(language)

    return [
        {
            "role": "user",
            "content": content,
        }
    ]


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


def normalize_digits(text):

    return str(text).translate(
        DIGIT_TRANSLATION
    )


def clean_number(value):

    value = normalize_digits(value)

    value = value.strip()

    value = value.replace(",", "")
    value = value.replace("٬", "")
    value = value.replace("٫", ".")

    return value


# ============================================================
# ANSWER EXTRACTION
# ============================================================

def extract_answer(response):

    text = normalize_digits(
        response
    )


    # 1. English required marker
    matches = re.findall(
        r"FINAL\s+ANSWER\s*:\s*"
        r"([-+]?\d[\d,]*(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )

    if matches:
        return (
            clean_number(matches[-1]),
            "english_final_marker"
        )


    # 2. Arabic required marker
    matches = re.findall(
        r"الإجابة\s+النهائية\s*:\s*"
        r"([-+]?\d[\d,]*(?:\.\d+)?)",
        text,
    )

    if matches:
        return (
            clean_number(matches[-1]),
            "arabic_final_marker"
        )


    # 3. LaTeX boxed answer
    matches = re.findall(
        r"\\boxed\s*\{\s*"
        r"([-+]?\d[\d,]*(?:\.\d+)?)"
        r"\s*\}",
        text,
    )

    if matches:
        return (
            clean_number(matches[-1]),
            "boxed"
        )


    # 4. Fallback.
    #
    # IMPORTANT:
    # Fallback cases will be flagged for manual review.
    numbers = re.findall(
        r"[-+]?\d[\d,]*(?:\.\d+)?",
        text,
    )

    if numbers:
        return (
            clean_number(numbers[-1]),
            "last_number_fallback"
        )


    return (
        None,
        "no_number"
    )


def numeric_equal(predicted, expected):

    if predicted is None:
        return False

    try:

        return (
            Decimal(str(predicted))
            ==
            Decimal(str(expected))
        )

    except (
        InvalidOperation,
        ValueError,
    ):

        return False


# ============================================================
# GENERATION
# ============================================================

def solve(problem, language):

    messages = build_messages(
        problem,
        language
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
        key: value.to(model_device)
        for key, value in inputs.items()
    }


    input_length = (
        inputs["input_ids"].shape[1]
    )


    start = time.perf_counter()


    with torch.inference_mode():

        output = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
            use_cache=True,
        )


    elapsed = (
        time.perf_counter()
        - start
    )


    generated_ids = output[
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


    del output
    del inputs

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


    return (
        response,
        input_length,
        output_tokens,
        elapsed,
    )


# ============================================================
# CSV
# ============================================================

FIELDS = [
    "problem_id",
    "language",
    "expected_answer",
    "extracted_answer",
    "is_correct",
    "extraction_method",
    "needs_manual_review",
    "problem",
    "generated_response",
    "input_tokens",
    "output_tokens",
    "generation_seconds",
    "status",
]


def save_results(results):

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=FIELDS,
        )

        writer.writeheader()
        writer.writerows(results)


# ============================================================
# RUN 40 EVALUATIONS
# ============================================================

results = []

evaluation_number = 0


print("\n" + "=" * 72)
print("STARTING 40 EVALUATIONS")
print("=" * 72)


for problem_id in range(1, 21):

    expected = EXPECTED_ANSWERS[
        problem_id
    ]


    # Balance presentation order.
    #
    # Odd IDs: English then Arabic
    # Even IDs: Arabic then English
    #
    # This avoids always running one language first.

    if problem_id % 2 == 1:

        cases = [
            (
                "english",
                english_by_id[problem_id]["problem"]
            ),
            (
                "arabic",
                arabic_by_id[problem_id]["problem"]
            ),
        ]

    else:

        cases = [
            (
                "arabic",
                arabic_by_id[problem_id]["problem"]
            ),
            (
                "english",
                english_by_id[problem_id]["problem"]
            ),
        ]


    for language, problem in cases:

        evaluation_number += 1


        print("\n" + "-" * 72)

        print(
            f"[{evaluation_number}/40] "
            f"Problem {problem_id} "
            f"- {language.upper()}"
        )

        print(
            "Expected:",
            expected
        )


        try:

            (
                response,
                input_tokens,
                output_tokens,
                elapsed,
            ) = solve(
                problem,
                language,
            )


            (
                extracted,
                extraction_method,
            ) = extract_answer(
                response
            )


            correct = numeric_equal(
                extracted,
                expected
            )


            # Manual review is especially important when
            # the model ignored our requested final-answer marker.

            needs_manual_review = int(
                extraction_method
                in {
                    "last_number_fallback",
                    "no_number",
                }
            )


            print("\nResponse:")
            print(response)

            print(
                "\nExtracted:",
                extracted
            )

            print(
                "Extraction method:",
                extraction_method
            )

            print(
                "Correct:",
                correct
            )

            print(
                "Manual review:",
                bool(needs_manual_review)
            )


            results.append({
                "problem_id": problem_id,
                "language": language,
                "expected_answer": expected,
                "extracted_answer": extracted,
                "is_correct": int(correct),
                "extraction_method": extraction_method,
                "needs_manual_review": needs_manual_review,
                "problem": problem,
                "generated_response": response,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "generation_seconds": elapsed,
                "status": "success",
            })


        except Exception as error:

            print(
                "\nERROR:",
                type(error).__name__,
                str(error)
            )


            results.append({
                "problem_id": problem_id,
                "language": language,
                "expected_answer": expected,
                "extracted_answer": None,
                "is_correct": 0,
                "extraction_method": "error",
                "needs_manual_review": 1,
                "problem": problem,
                "generated_response": "",
                "input_tokens": None,
                "output_tokens": None,
                "generation_seconds": None,
                "status": (
                    "ERROR: "
                    + type(error).__name__
                ),
            })


        # Save after every generation
        save_results(
            results
        )


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 72)
print("AUTOMATIC RESULTS")
print("=" * 72)


for language in [
    "arabic",
    "english",
]:

    rows = [
        row
        for row in results
        if (
            row["language"] == language
            and row["status"] == "success"
        )
    ]


    correct = sum(
        row["is_correct"]
        for row in rows
    )


    total = len(rows)


    accuracy = (
        correct / total
        if total
        else 0
    )


    print(
        f"\n{language.upper()}"
    )

    print(
        f"Correct: {correct}/{total}"
    )

    print(
        f"Accuracy: {accuracy:.4f}"
    )


# ============================================================
# MANUAL REVIEW SUMMARY
# ============================================================

review_rows = [
    row
    for row in results
    if row[
        "needs_manual_review"
    ] == 1
]


print("\n" + "=" * 72)
print("MANUAL REVIEW REQUIRED")
print("=" * 72)


print(
    "\nCases requiring review:",
    len(review_rows)
)


for row in review_rows:

    print(
        f"Problem {row['problem_id']:2d} | "
        f"{row['language']:7s} | "
        f"expected={row['expected_answer']} | "
        f"extracted={row['extracted_answer']} | "
        f"method={row['extraction_method']}"
    )


print("\n" + "=" * 72)
print("EXPERIMENT COMPLETE")
print("=" * 72)


print(
    "\nSaved:",
    OUTPUT_FILE
)

print(
    "\nDo NOT run the statistical comparison yet "
    "until failures/fallback cases have been manually reviewed."
)