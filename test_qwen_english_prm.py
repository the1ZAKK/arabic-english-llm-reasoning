import csv
import ast
from pathlib import Path

import torch
import torch.nn.functional as F

from transformers import (
    AutoTokenizer,
    AutoModel,
    AutoConfig,
    BitsAndBytesConfig,
)


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_PATH = "Qwen/Qwen2.5-Math-PRM-7B"

# Reuse the exact same 20 English problems from the
# already completed Skywork English experiment.
SOURCE_SCRIPT = "test_english_prm.py"

OUTPUT_FILE = "qwen_english_prm_results.csv"

CATEGORIES = [
    "correct",
    "arithmetic_error",
    "logic_error",
    "completely_wrong",
]

STEP_TOKEN = "<extra_0>"

PAD_TOKEN_ID = 151643

OFFLOAD_FOLDER = r"D:\qwen_offload"


# ============================================================
# LOAD THE SAME 20 ENGLISH PROBLEMS
# ============================================================

def load_examples_from_script(path):
    """
    Read the `examples = [...]` variable from the existing
    test_english_prm.py WITHOUT executing that script.

    This ensures that Qwen evaluates exactly the same
    20 English problems and four response categories
    already used in the Skywork English experiment.
    """

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
        "Could not find an `examples = [...]` "
        f"variable inside {path}."
    )


# ============================================================
# HEADER
# ============================================================

print("=" * 70)
print("QWEN QWEN2.5-MATH-PRM-7B")
print("ENGLISH LARGE-SCALE PRM EVALUATION")
print("=" * 70)


print("\nLoading SAME English dataset from:")
print(SOURCE_SCRIPT)


examples = load_examples_from_script(
    SOURCE_SCRIPT
)


# ============================================================
# DATASET VALIDATION
# ============================================================

print("\nValidating dataset...")


if len(examples) != 20:

    raise RuntimeError(
        f"Expected 20 problems, "
        f"but found {len(examples)}."
    )


expected_ids = list(
    range(1, 21)
)

actual_ids = [
    int(example["id"])
    for example in examples
]


if actual_ids != expected_ids:

    raise RuntimeError(
        "\nProblem IDs are not 1 through 20.\n"
        f"Expected: {expected_ids}\n"
        f"Found:    {actual_ids}"
    )


for example in examples:

    if "problem" not in example:

        raise RuntimeError(
            f"Problem {example['id']} "
            "has no problem text."
        )

    if "responses" not in example:

        raise RuntimeError(
            f"Problem {example['id']} "
            "has no responses dictionary."
        )

    missing_categories = [
        category
        for category in CATEGORIES
        if category not in example["responses"]
    ]

    if missing_categories:

        raise RuntimeError(
            f"Problem {example['id']} "
            f"is missing categories: "
            f"{missing_categories}"
        )


print("Dataset validation successful.")

print(
    f"Problems: {len(examples)}"
)

print(
    f"Categories per problem: "
    f"{len(CATEGORIES)}"
)

print(
    f"Expected evaluations: "
    f"{len(examples) * len(CATEGORIES)}"
)


# ============================================================
# GPU CHECK
# ============================================================

print("\n" + "=" * 70)
print("GPU CHECK")
print("=" * 70)


if not torch.cuda.is_available():

    raise RuntimeError(
        "CUDA is not available. "
        "This Qwen 7B experiment requires CUDA."
    )


gpu_name = torch.cuda.get_device_name(
    0
)

vram_gb = (
    torch.cuda
    .get_device_properties(0)
    .total_memory
    / 1024**3
)


print(
    "\nGPU:",
    gpu_name
)

print(
    "VRAM GB:",
    round(vram_gb, 2)
)


# ============================================================
# LOAD TOKENIZER
# ============================================================

print("\n" + "=" * 70)
print("LOADING TOKENIZER")
print("=" * 70)


tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True,
)


if tokenizer.pad_token_id is None:

    tokenizer.pad_token_id = PAD_TOKEN_ID


print(
    "\nTokenizer loaded successfully."
)

print(
    "Tokenizer pad_token_id:",
    tokenizer.pad_token_id
)


# ============================================================
# CHECK QWEN STEP TOKEN
# ============================================================

step_token_ids = tokenizer.encode(
    STEP_TOKEN,
    add_special_tokens=False,
)


if len(step_token_ids) != 1:

    raise RuntimeError(
        f"{STEP_TOKEN} should be one token, "
        f"but tokenizer returned "
        f"{step_token_ids}"
    )


STEP_SEP_ID = step_token_ids[0]


print(
    f"{STEP_TOKEN} token ID:",
    STEP_SEP_ID
)


# ============================================================
# LOAD MODEL CONFIG
# ============================================================

print("\n" + "=" * 70)
print("LOADING MODEL CONFIGURATION")
print("=" * 70)


config = AutoConfig.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True,
)


# Compatibility fix for newer Transformers versions.
if (
    not hasattr(config, "pad_token_id")
    or config.pad_token_id is None
):

    config.pad_token_id = PAD_TOKEN_ID


print(
    "\nConfig loaded successfully."
)

print(
    "Config pad_token_id:",
    config.pad_token_id
)

print(
    "Config bos_token_id:",
    getattr(
        config,
        "bos_token_id",
        None
    )
)

print(
    "Config eos_token_id:",
    getattr(
        config,
        "eos_token_id",
        None
    )
)


# ============================================================
# PREPARE OFFLOAD DIRECTORY
# ============================================================

Path(OFFLOAD_FOLDER).mkdir(
    parents=True,
    exist_ok=True,
)


print("\nOffload folder:")
print(OFFLOAD_FOLDER)


# ============================================================
# LOAD QWEN PRM IN 4-BIT + CPU OFFLOAD
# ============================================================

print("\n" + "=" * 70)
print("LOADING QWEN PRM")
print("=" * 70)


print(
    "\nUsing 4-bit NF4 quantization "
    "with CPU/disk offload for the RTX 2060 6 GB GPU."
)


bnb_config = BitsAndBytesConfig(

    load_in_4bit=True,

    bnb_4bit_quant_type="nf4",

    bnb_4bit_compute_dtype=torch.float16,

    bnb_4bit_use_double_quant=True,

    llm_int8_enable_fp32_cpu_offload=True,
)


# Leave some GPU space for activations.
# CPU budget is limited because your system has ~16 GB RAM.
max_memory = {
    0: "5GiB",
    "cpu": "9GiB",
}


model = AutoModel.from_pretrained(

    MODEL_PATH,

    config=config,

    trust_remote_code=True,

    quantization_config=bnb_config,

    device_map="auto",

    max_memory=max_memory,

    offload_folder=OFFLOAD_FOLDER,

    offload_state_dict=True,
)


model.eval()


# ============================================================
# DETERMINE INPUT DEVICE
# ============================================================

try:

    model_device = (
        model.model.embed_tokens.weight.device
    )

except Exception:

    try:

        model_device = next(
            model.parameters()
        ).device

    except StopIteration:

        model_device = torch.device(
            "cuda:0"
        )


print(
    "\nModel loaded successfully."
)

print(
    "Model input device:",
    model_device
)


# ============================================================
# SHOW DEVICE MAP
# ============================================================

if hasattr(model, "hf_device_map"):

    print("\n" + "=" * 70)
    print("DEVICE MAP")
    print("=" * 70)

    for module_name, module_device in model.hf_device_map.items():

        print(
            f"{module_name}: "
            f"{module_device}"
        )


# ============================================================
# QWEN PRM SCORING
# ============================================================

def score_response(
    problem,
    response
):

    """
    Score a single English reasoning response.

    Each non-empty reasoning line becomes one PRM step.

    Qwen PRM uses <extra_0> after each reasoning step.

    At each <extra_0> location:

        softmax(logits)[1]

    is used as the positive/correct step probability.
    """


    # --------------------------------------------------------
    # Normalize response
    # --------------------------------------------------------

    response = (
        response
        .replace("\r\n", "\n")
        .strip()
    )


    # --------------------------------------------------------
    # Split reasoning into steps
    # --------------------------------------------------------

    steps = [
        line.strip()
        for line in response.split("\n")
        if line.strip()
    ]


    if not steps:

        raise ValueError(
            "Response contains no reasoning steps."
        )


    # --------------------------------------------------------
    # Add <extra_0> after every step
    # --------------------------------------------------------

    formatted_solution = "".join(
        step + STEP_TOKEN
        for step in steps
    )


    # --------------------------------------------------------
    # Qwen chat format
    # --------------------------------------------------------

    messages = [

        {
            "role": "system",
            "content": (
                "Please reason step by step, "
                "and put your final answer within "
                "\\boxed{}."
            ),
        },

        {
            "role": "user",
            "content": problem,
        },

        {
            "role": "assistant",
            "content": formatted_solution,
        },

    ]


    conversation = (
        tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )
    )


    # --------------------------------------------------------
    # Tokenize
    # --------------------------------------------------------

    inputs = tokenizer(
        conversation,
        return_tensors="pt",
        truncation=True,
        max_length=4096,
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


    # --------------------------------------------------------
    # Model inference
    # --------------------------------------------------------

    with torch.no_grad():

        if attention_mask is None:

            outputs = model(
                input_ids=input_ids
            )

        else:

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )


    # --------------------------------------------------------
    # Obtain PRM logits
    # --------------------------------------------------------

    if (
        hasattr(outputs, "logits")
        and outputs.logits is not None
    ):

        logits = outputs.logits


    elif isinstance(
        outputs,
        (tuple, list)
    ):

        logits = outputs[0]


    else:

        raise RuntimeError(
            "Could not find logits "
            "in Qwen PRM output."
        )


    # --------------------------------------------------------
    # Confirm expected shape
    # --------------------------------------------------------

    if logits.shape[-1] != 2:

        raise RuntimeError(
            "\nUnexpected Qwen PRM "
            "logit shape.\n"
            f"Shape: {tuple(logits.shape)}\n"
            "Expected final dimension = 2."
        )


    # --------------------------------------------------------
    # Two-class probabilities
    # --------------------------------------------------------

    probabilities = F.softmax(
        logits.float(),
        dim=-1
    )


    # --------------------------------------------------------
    # Find <extra_0> reward positions
    # --------------------------------------------------------

    step_positions = torch.nonzero(
        input_ids[0] == STEP_SEP_ID,
        as_tuple=False,
    ).flatten()


    if len(step_positions) == 0:

        raise RuntimeError(
            "No <extra_0> positions found."
        )


    # --------------------------------------------------------
    # Extract positive-class probability
    # --------------------------------------------------------

    step_scores = []


    for position in step_positions:

        position = int(
            position.item()
        )


        score = float(
            probabilities[
                0,
                position,
                1
            ].item()
        )


        step_scores.append(
            score
        )


    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    del outputs
    del logits
    del probabilities
    del input_ids

    if attention_mask is not None:
        del attention_mask

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


    return step_scores


# ============================================================
# EVALUATION
# ============================================================

print("\n")
print("=" * 70)
print("STARTING QWEN ENGLISH PRM EVALUATION")
print("=" * 70)


results = []


total_expected = (
    len(examples)
    * len(CATEGORIES)
)


evaluation_number = 0


for example in examples:


    print(
        f"\nProblem "
        f"{example['id']}/"
        f"{len(examples)}"
    )


    for category in CATEGORIES:


        evaluation_number += 1


        print(
            f"  [{evaluation_number}/"
            f"{total_expected}] "
            f"{category}"
        )


        problem = (
            example["problem"]
        )


        response = (
            example["responses"]
            [category]
        )


        try:


            scores = score_response(
                problem,
                response
            )


            average_score = (
                sum(scores)
                / len(scores)
            )


            minimum_score = min(
                scores
            )


            maximum_score = max(
                scores
            )


            status = "success"


            print(
                f"      Average: "
                f"{average_score:.4f}"
                f" | Min: "
                f"{minimum_score:.4f}"
                f" | Max: "
                f"{maximum_score:.4f}"
            )


        except Exception as error:


            print(
                "      ERROR:",
                type(error).__name__,
                str(error)
            )


            scores = []

            average_score = None

            minimum_score = None

            maximum_score = None

            status = (
                "ERROR: "
                + type(error).__name__
            )


        results.append({

            "problem_id":
                example["id"],

            "category":
                category,

            "problem":
                problem,

            "response":
                response.strip(),

            "num_steps":
                len(scores),

            "average_score":
                average_score,

            "minimum_score":
                minimum_score,

            "maximum_score":
                maximum_score,

            "step_scores":
                " ".join(
                    f"{x:.4f}"
                    for x in scores
                ),

            "status":
                status,

        })


# ============================================================
# SAVE RESULTS
# ============================================================

print("\n")
print("=" * 70)
print("SAVING RESULTS")
print("=" * 70)


fieldnames = [
    "problem_id",
    "category",
    "problem",
    "response",
    "num_steps",
    "average_score",
    "minimum_score",
    "maximum_score",
    "step_scores",
    "status",
]


with open(
    OUTPUT_FILE,
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
        results
    )


print(
    "\nSaved:"
)

print(
    OUTPUT_FILE
)


# ============================================================
# COMPLETENESS CHECK
# ============================================================

successful_results = [
    row
    for row in results
    if row["status"] == "success"
]


print("\n")
print("=" * 70)
print("DATASET COMPLETENESS CHECK")
print("=" * 70)


print(
    f"\nSuccessful evaluations: "
    f"{len(successful_results)}"
)


print(
    f"Expected evaluations: "
    f"{total_expected}"
)


if len(successful_results) == total_expected:

    print(
        "\nSUCCESS: "
        "All 80 evaluations completed."
    )

else:

    print(
        "\nWARNING: "
        "Some evaluations failed."
    )


# ============================================================
# CATEGORY SUMMARY
# ============================================================

print("\n")
print("=" * 70)
print("FINAL RESULTS")
print("=" * 70)


for category in CATEGORIES:


    category_results = [
        row
        for row in successful_results
        if row["category"] == category
    ]


    if not category_results:

        continue


    average = sum(
        row["average_score"]
        for row in category_results
    ) / len(category_results)


    average_minimum = sum(
        row["minimum_score"]
        for row in category_results
    ) / len(category_results)


    average_maximum = sum(
        row["maximum_score"]
        for row in category_results
    ) / len(category_results)


    print(
        "\n"
        + category.upper()
    )


    print(
        "-" * 40
    )


    print(
        f"Examples       : "
        f"{len(category_results)}"
    )


    print(
        f"Average score  : "
        f"{average:.4f}"
    )


    print(
        f"Average minimum: "
        f"{average_minimum:.4f}"
    )


    print(
        f"Average maximum: "
        f"{average_maximum:.4f}"
    )


# ============================================================
# CORRECT VS INCORRECT
# ============================================================

correct_results = [
    row
    for row in successful_results
    if row["category"] == "correct"
]


incorrect_results = [
    row
    for row in successful_results
    if row["category"] != "correct"
]


if (
    correct_results
    and incorrect_results
):


    correct_average = sum(
        row["average_score"]
        for row in correct_results
    ) / len(correct_results)


    incorrect_average = sum(
        row["average_score"]
        for row in incorrect_results
    ) / len(incorrect_results)


    discrimination_gap = (
        correct_average
        - incorrect_average
    )


    print("\n")
    print("=" * 70)
    print("CORRECT vs INCORRECT")
    print("=" * 70)


    print(
        f"\nCorrect examples average   : "
        f"{correct_average:.4f}"
    )


    print(
        f"Incorrect examples average : "
        f"{incorrect_average:.4f}"
    )


    print(
        f"Discrimination gap         : "
        f"{discrimination_gap:+.4f}"
    )


# ============================================================
# PER-CATEGORY COMPLETENESS
# ============================================================

print("\n")
print("=" * 70)
print("PER-CATEGORY COMPLETENESS")
print("=" * 70)


for category in CATEGORIES:


    count = sum(
        1
        for row in successful_results
        if row["category"] == category
    )


    print(
        f"{category:20s}: "
        f"{count}/20"
    )


# ============================================================
# FINISH
# ============================================================

print("\n")
print("=" * 70)
print("QWEN ENGLISH PRM EVALUATION COMPLETE")
print("=" * 70)


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
    "Compare qwen_arabic_prm_results.csv "
    "against qwen_english_prm_results.csv."
)