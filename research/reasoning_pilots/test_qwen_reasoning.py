import ast
import csv
import math
import re
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import torch

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
)


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_PATH = "Qwen/Qwen2.5-Math-1.5B-Instruct"

ARABIC_SOURCE = "test_arabic_prm.py"
ENGLISH_SOURCE = "test_english_prm.py"

OUTPUT_FILE = "qwen_reasoning_results.csv"

MAX_NEW_TOKENS = 256

SEED = 42


# ============================================================
# GROUND-TRUTH ANSWERS
# ============================================================

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
# LOAD PROBLEMS FROM EXISTING SCRIPTS
# ============================================================

def load_examples_from_script(path):
    """
    Extract `examples = [...]` from one of the existing PRM scripts
    WITHOUT executing the script.
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Could not find source file: {path}"
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

                    examples = ast.literal_eval(
                        node.value
                    )

                    return examples

    raise RuntimeError(
        f"Could not find `examples = [...]` in {path}"
    )


# ============================================================
# LOAD DATASETS
# ============================================================

print("=" * 72)
print("QWEN BILINGUAL REASONING EXPERIMENT")
print("=" * 72)

print("\nLoading Arabic dataset...")

arabic_examples = load_examples_from_script(
    ARABIC_SOURCE
)

print("Loading English dataset...")

english_examples = load_examples_from_script(
    ENGLISH_SOURCE
)


# ============================================================
# VALIDATE DATASETS
# ============================================================

print("\nValidating bilingual datasets...")


if len(arabic_examples) != 20:

    raise RuntimeError(
        f"Expected 20 Arabic problems, "
        f"found {len(arabic_examples)}."
    )


if len(english_examples) != 20:

    raise RuntimeError(
        f"Expected 20 English problems, "
        f"found {len(english_examples)}."
    )


arabic_by_id = {
    int(example["id"]): example
    for example in arabic_examples
}


english_by_id = {
    int(example["id"]): example
    for example in english_examples
}


expected_ids = set(
    range(1, 21)
)


if set(arabic_by_id.keys()) != expected_ids:

    raise RuntimeError(
        "Arabic problem IDs are not exactly 1-20."
    )


if set(english_by_id.keys()) != expected_ids:

    raise RuntimeError(
        "English problem IDs are not exactly 1-20."
    )


if set(EXPECTED_ANSWERS.keys()) != expected_ids:

    raise RuntimeError(
        "Ground-truth answer IDs do not match 1-20."
    )


print("Dataset validation successful.")

print("Arabic problems :", len(arabic_examples))
print("English problems:", len(english_examples))

print(
    "Total planned evaluations:",
    len(arabic_examples)
    + len(english_examples)
)


# ============================================================
# GPU INFORMATION
# ============================================================

print("\n" + "=" * 72)
print("DEVICE INFORMATION")
print("=" * 72)


if torch.cuda.is_available():

    print(
        "\nGPU:",
        torch.cuda.get_device_name(0)
    )

    print(
        "VRAM GB:",
        round(
            torch.cuda
            .get_device_properties(0)
            .total_memory
            / 1024**3,
            2
        )
    )

else:

    print("\nCUDA is not available.")
    print("The experiment will run on CPU.")


# ============================================================
# LOAD TOKENIZER
# ============================================================

print("\n" + "=" * 72)
print("LOADING TOKENIZER")
print("=" * 72)


tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True,
)


if tokenizer.pad_token_id is None:

    tokenizer.pad_token_id = (
        tokenizer.eos_token_id
    )


print("\nTokenizer loaded.")

print(
    "pad_token_id:",
    tokenizer.pad_token_id
)


# ============================================================
# LOAD MODEL
# ============================================================

print("\n" + "=" * 72)
print("LOADING QWEN MODEL")
print("=" * 72)


if torch.cuda.is_available():

    model = AutoModelForCausalLM.from_pretrained(

        MODEL_PATH,

        torch_dtype=torch.float16,

        device_map="auto",

        trust_remote_code=True,
    )

else:

    model = AutoModelForCausalLM.from_pretrained(

        MODEL_PATH,

        torch_dtype=torch.float32,

        trust_remote_code=True,
    )


model.eval()


try:

    model_device = (
        model.model.embed_tokens.weight.device
    )

except Exception:

    model_device = next(
        model.parameters()
    ).device


print("\nModel loaded successfully.")

print(
    "Model input device:",
    model_device
)


# ============================================================
# PROMPT BUILDING
# ============================================================

def build_messages(
    problem,
    language
):

    """
    Build semantically matched instructions.

    Only the language changes.
    """


    if language == "english":

        system_message = (
            "You are a mathematical reasoning assistant. "
            "Solve the problem carefully and step by step. "
            "Do not guess. "
            "At the end, write exactly one line in this format:\n"
            "FINAL ANSWER: <number>"
        )


        user_message = (
            "Solve the following problem step by step.\n\n"
            f"{problem}"
        )


    elif language == "arabic":

        system_message = (
            "أنت مساعد متخصص في الاستدلال الرياضي. "
            "حل المسألة بعناية خطوة بخطوة ولا تخمن. "
            "في النهاية، اكتب سطرًا واحدًا فقط بهذا الشكل:\n"
            "الإجابة النهائية: <number>"
        )


        user_message = (
            "حل المسألة التالية خطوة بخطوة.\n\n"
            f"{problem}"
        )


    else:

        raise ValueError(
            f"Unknown language: {language}"
        )


    return [

        {
            "role": "system",
            "content": system_message,
        },

        {
            "role": "user",
            "content": user_message,
        },

    ]


# ============================================================
# DIGIT NORMALIZATION
# ============================================================

ARABIC_DIGITS = str.maketrans({

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

    return text.translate(
        ARABIC_DIGITS
    )


# ============================================================
# ANSWER EXTRACTION
# ============================================================

def clean_numeric_string(value):

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

    return value


def extract_final_answer(
    response
):

    """
    Extract the final numerical answer.

    Priority:

    1. FINAL ANSWER:
    2. الإجابة النهائية:
    3. \\boxed{}
    4. Last numeric value in the response
    """

    normalized = normalize_digits(
        response
    )


    # --------------------------------------------------------
    # English final marker
    # --------------------------------------------------------

    english_matches = re.findall(

        r"FINAL\s+ANSWER\s*:\s*"
        r"([-+]?\d[\d,]*(?:\.\d+)?)",

        normalized,

        flags=re.IGNORECASE,
    )


    if english_matches:

        return clean_numeric_string(
            english_matches[-1]
        )


    # --------------------------------------------------------
    # Arabic final marker
    # --------------------------------------------------------

    arabic_matches = re.findall(

        r"الإجابة\s+النهائية\s*:\s*"
        r"([-+]?\d[\d,]*(?:\.\d+)?)",

        normalized,
    )


    if arabic_matches:

        return clean_numeric_string(
            arabic_matches[-1]
        )


    # --------------------------------------------------------
    # Boxed answer
    # --------------------------------------------------------

    boxed_matches = re.findall(

        r"\\boxed\s*\{\s*"
        r"([-+]?\d[\d,]*(?:\.\d+)?)"
        r"\s*\}",

        normalized,
    )


    if boxed_matches:

        return clean_numeric_string(
            boxed_matches[-1]
        )


    # --------------------------------------------------------
    # Fallback: last numerical value
    # --------------------------------------------------------

    all_numbers = re.findall(

        r"[-+]?\d[\d,]*(?:\.\d+)?",

        normalized,
    )


    if all_numbers:

        return clean_numeric_string(
            all_numbers[-1]
        )


    return None


# ============================================================
# NUMERIC COMPARISON
# ============================================================

def numeric_equal(
    predicted,
    expected
):

    if predicted is None:

        return False


    try:

        predicted_decimal = Decimal(
            str(predicted)
        )

        expected_decimal = Decimal(
            str(expected)
        )


        return (
            predicted_decimal
            == expected_decimal
        )


    except (
        InvalidOperation,
        ValueError,
    ):

        return False


# ============================================================
# GENERATION
# ============================================================

def solve_problem(
    problem,
    language
):


    messages = build_messages(
        problem,
        language
    )


    prompt_text = (
        tokenizer.apply_chat_template(

            messages,

            tokenize=False,

            add_generation_prompt=True,

        )
    )


    inputs = tokenizer(

        prompt_text,

        return_tensors="pt",

        padding=False,

    )


    input_ids = (
        inputs["input_ids"]
        .to(model_device)
    )


    attention_mask = (
        inputs.get(
            "attention_mask"
        )
    )


    if attention_mask is not None:

        attention_mask = (
            attention_mask
            .to(model_device)
        )


    input_length = (
        input_ids.shape[1]
    )


    start_time = time.perf_counter()


    with torch.no_grad():

        generation = model.generate(

            input_ids=input_ids,

            attention_mask=attention_mask,

            max_new_tokens=MAX_NEW_TOKENS,

            do_sample=False,

            pad_token_id=tokenizer.pad_token_id,

            eos_token_id=tokenizer.eos_token_id,

            use_cache=True,
        )


    elapsed = (
        time.perf_counter()
        - start_time
    )


    generated_ids = generation[
        0,
        input_length:
    ]


    output_tokens = len(
        generated_ids
    )


    response = tokenizer.decode(

        generated_ids,

        skip_special_tokens=True,

    ).strip()


    # Cleanup
    del generation
    del input_ids

    if attention_mask is not None:
        del attention_mask


    if torch.cuda.is_available():
        torch.cuda.empty_cache()


    return {
        "prompt": prompt_text,
        "response": response,
        "input_tokens": input_length,
        "output_tokens": output_tokens,
        "generation_seconds": elapsed,
    }


# ============================================================
# CSV SAVE FUNCTION
# ============================================================

FIELDNAMES = [
    "problem_id",
    "language",
    "expected_answer",
    "extracted_answer",
    "is_correct",
    "problem",
    "generated_response",
    "input_tokens",
    "output_tokens",
    "generation_seconds",
    "status",
]


def save_results(
    results
):

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:


        writer = csv.DictWriter(

            file,

            fieldnames=FIELDNAMES,

        )


        writer.writeheader()


        writer.writerows(
            results
        )


# ============================================================
# RUN EXPERIMENT
# ============================================================

print("\n")
print("=" * 72)
print("STARTING BILINGUAL REASONING EVALUATION")
print("=" * 72)


results = []

evaluation_number = 0

TOTAL_EVALUATIONS = 40


# ------------------------------------------------------------
# Alternate Arabic and English for each problem.
#
# This keeps the experiment naturally paired:
#
# Problem 1 Arabic
# Problem 1 English
# Problem 2 Arabic
# Problem 2 English
# ...
# ------------------------------------------------------------

for problem_id in range(
    1,
    21
):


    expected_answer = (
        EXPECTED_ANSWERS[
            problem_id
        ]
    )


    language_cases = [

        (
            "arabic",
            arabic_by_id[
                problem_id
            ]["problem"],
        ),

        (
            "english",
            english_by_id[
                problem_id
            ]["problem"],
        ),

    ]


    for (
        language,
        problem
    ) in language_cases:


        evaluation_number += 1


        print(
            "\n"
            + "-" * 72
        )


        print(
            f"[{evaluation_number}/"
            f"{TOTAL_EVALUATIONS}] "
            f"Problem {problem_id} "
            f"- {language.upper()}"
        )


        print(
            "Expected answer:",
            expected_answer
        )


        try:


            generation_result = solve_problem(

                problem,

                language,

            )


            response = (
                generation_result[
                    "response"
                ]
            )


            extracted_answer = (
                extract_final_answer(
                    response
                )
            )


            is_correct = numeric_equal(

                extracted_answer,

                expected_answer,

            )


            status = "success"


            print(
                "\nModel response:"
            )


            print(
                response
            )


            print(
                "\nExtracted answer:",
                extracted_answer
            )


            print(
                "Correct:",
                is_correct
            )


            print(
                "Generation time:",
                f"{generation_result['generation_seconds']:.2f}s"
            )


            results.append({

                "problem_id":
                    problem_id,

                "language":
                    language,

                "expected_answer":
                    expected_answer,

                "extracted_answer":
                    extracted_answer,

                "is_correct":
                    int(is_correct),

                "problem":
                    problem,

                "generated_response":
                    response,

                "input_tokens":
                    generation_result[
                        "input_tokens"
                    ],

                "output_tokens":
                    generation_result[
                        "output_tokens"
                    ],

                "generation_seconds":
                    generation_result[
                        "generation_seconds"
                    ],

                "status":
                    status,

            })


        except Exception as error:


            print(
                "\nERROR:",
                type(error).__name__,
                str(error)
            )


            results.append({

                "problem_id":
                    problem_id,

                "language":
                    language,

                "expected_answer":
                    expected_answer,

                "extracted_answer":
                    None,

                "is_correct":
                    0,

                "problem":
                    problem,

                "generated_response":
                    "",

                "input_tokens":
                    None,

                "output_tokens":
                    None,

                "generation_seconds":
                    None,

                "status":
                    (
                        "ERROR: "
                        + type(error).__name__
                    ),

            })


        # ----------------------------------------------------
        # Save after EVERY generation.
        #
        # If Windows/Python crashes halfway through,
        # completed generations are still preserved.
        # ----------------------------------------------------

        save_results(
            results
        )


# ============================================================
# COMPLETENESS CHECK
# ============================================================

print("\n")
print("=" * 72)
print("COMPLETENESS CHECK")
print("=" * 72)


successful = [

    row

    for row in results

    if row["status"]
    == "success"

]


print(
    "\nSuccessful generations:",
    len(successful)
)

print(
    "Expected generations:",
    TOTAL_EVALUATIONS
)


# ============================================================
# LANGUAGE ACCURACY
# ============================================================

print("\n")
print("=" * 72)
print("LANGUAGE ACCURACY")
print("=" * 72)


language_summary = {}


for language in [
    "arabic",
    "english",
]:


    rows = [

        row

        for row in results

        if (
            row["language"]
            == language

            and row["status"]
            == "success"
        )

    ]


    correct_count = sum(

        row["is_correct"]

        for row in rows

    )


    total_count = len(
        rows
    )


    accuracy = (

        correct_count
        / total_count

        if total_count > 0

        else 0

    )


    language_summary[
        language
    ] = {

        "correct":
            correct_count,

        "total":
            total_count,

        "accuracy":
            accuracy,

    }


    print(
        f"\n{language.upper()}"
    )

    print(
        "-" * 40
    )

    print(
        "Correct:",
        f"{correct_count}/{total_count}"
    )

    print(
        "Accuracy:",
        f"{accuracy:.4f}"
    )


# ============================================================
# RAW ACCURACY DIFFERENCE
# ============================================================

arabic_accuracy = (
    language_summary[
        "arabic"
    ]["accuracy"]
)


english_accuracy = (
    language_summary[
        "english"
    ]["accuracy"]
)


difference = (
    english_accuracy
    - arabic_accuracy
)


print("\n")
print("=" * 72)
print("ENGLISH vs ARABIC")
print("=" * 72)


print(
    f"\nArabic accuracy : "
    f"{arabic_accuracy:.4f}"
)

print(
    f"English accuracy: "
    f"{english_accuracy:.4f}"
)

print(
    f"English - Arabic: "
    f"{difference:+.4f}"
)


# ============================================================
# PAIRED PROBLEM SUMMARY
# ============================================================

print("\n")
print("=" * 72)
print("PAIRED PROBLEM RESULTS")
print("=" * 72)


for problem_id in range(
    1,
    21
):


    arabic_row = next(

        (
            row
            for row in results

            if (
                row["problem_id"]
                == problem_id

                and row["language"]
                == "arabic"
            )
        ),

        None,

    )


    english_row = next(

        (
            row
            for row in results

            if (
                row["problem_id"]
                == problem_id

                and row["language"]
                == "english"
            )
        ),

        None,

    )


    arabic_correct = (
        arabic_row["is_correct"]
        if arabic_row
        else 0
    )


    english_correct = (
        english_row["is_correct"]
        if english_row
        else 0
    )


    print(

        f"Problem {problem_id:2d}: "

        f"Arabic={arabic_correct} | "

        f"English={english_correct}"

    )


# ============================================================
# DISCORDANT PAIRS
# ============================================================

english_only_correct = 0

arabic_only_correct = 0

both_correct = 0

both_wrong = 0


for problem_id in range(
    1,
    21
):


    ar = next(

        row

        for row in results

        if (
            row["problem_id"]
            == problem_id

            and row["language"]
            == "arabic"
        )

    )


    en = next(

        row

        for row in results

        if (
            row["problem_id"]
            == problem_id

            and row["language"]
            == "english"
        )

    )


    ar_correct = bool(
        ar["is_correct"]
    )


    en_correct = bool(
        en["is_correct"]
    )


    if (
        ar_correct
        and en_correct
    ):

        both_correct += 1


    elif (
        not ar_correct
        and not en_correct
    ):

        both_wrong += 1


    elif (
        en_correct
        and not ar_correct
    ):

        english_only_correct += 1


    elif (
        ar_correct
        and not en_correct
    ):

        arabic_only_correct += 1


print("\n")
print("=" * 72)
print("PAIRED OUTCOME COUNTS")
print("=" * 72)


print(
    "\nBoth correct:",
    both_correct
)

print(
    "Both wrong:",
    both_wrong
)

print(
    "English correct / Arabic wrong:",
    english_only_correct
)

print(
    "Arabic correct / English wrong:",
    arabic_only_correct
)


# ============================================================
# FINISH
# ============================================================

save_results(
    results
)


print("\n")
print("=" * 72)
print("QWEN BILINGUAL REASONING EXPERIMENT COMPLETE")
print("=" * 72)


print(
    "\nResults saved to:"
)

print(
    OUTPUT_FILE
)


print(
    "\nNext step:"
)

print(
    "Run statistical analysis on the paired "
    "Arabic/English correctness results."
)