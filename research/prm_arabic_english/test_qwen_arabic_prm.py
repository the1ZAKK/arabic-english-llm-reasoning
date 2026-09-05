import csv
import ast
import re
from pathlib import Path

import torch
import torch.nn.functional as F

from transformers import (
    AutoTokenizer,
    AutoModel,
    BitsAndBytesConfig,
)


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_PATH = "Qwen/Qwen2.5-Math-PRM-7B"

# IMPORTANT:
# We reuse the exact same 20 Arabic problems and responses
# from your existing Skywork experiment.
SOURCE_SCRIPT = "test_arabic_prm.py"

OUTPUT_FILE = "qwen_arabic_prm_results.csv"

CATEGORIES = [
    "correct",
    "arithmetic_error",
    "logic_error",
    "completely_wrong",
]


# ============================================================
# LOAD THE EXISTING 20 ARABIC PROBLEMS
# ============================================================

def load_examples_from_script(path):

    source = Path(path).read_text(
        encoding="utf-8"
    )

    # Find:
    # examples = [
    #     ...
    # ]

    start = source.find("examples = [")

    if start == -1:
        raise RuntimeError(
            "Could not find 'examples = [' in "
            + path
        )

    # Find the end of the examples list.
    # In your existing file it ends immediately before
    # the LOAD TOKENIZER section.

    end_marker = "\n\n\n# ============================================================\n# LOAD TOKENIZER"

    end = source.find(
        end_marker,
        start
    )

    if end == -1:

        # More flexible fallback
        end = source.find(
            "# ============================================================\n# LOAD TOKENIZER",
            start
        )

    if end == -1:
        raise RuntimeError(
            "Could not determine the end of the examples list."
        )

    examples_text = source[
        start + len("examples = "):end
    ].strip()

    examples = ast.literal_eval(
        examples_text
    )

    return examples


print("=" * 70)
print("QWEN QWEN2.5-MATH-PRM-7B")
print("ARABIC LARGE-SCALE PRM EVALUATION")
print("=" * 70)


print("\nLoading SAME dataset from:")
print(SOURCE_SCRIPT)

examples = load_examples_from_script(
    SOURCE_SCRIPT
)


# ============================================================
# DATASET VALIDATION
# ============================================================

if len(examples) != 20:

    raise RuntimeError(
        f"Expected 20 problems, found {len(examples)}"
    )


for example in examples:

    if set(example["responses"].keys()) != set(CATEGORIES):

        raise RuntimeError(
            f"Problem {example['id']} does not contain "
            "the expected four categories."
        )


print("\nDataset validation successful.")

print(
    f"Problems: {len(examples)}"
)

print(
    f"Categories per problem: {len(CATEGORIES)}"
)

print(
    f"Expected evaluations: "
    f"{len(examples) * len(CATEGORIES)}"
)


# ============================================================
# GPU CHECK
# ============================================================

print("\nChecking GPU...")

if not torch.cuda.is_available():

    raise RuntimeError(
        "CUDA is not available. "
        "This Qwen 7B experiment requires a GPU."
    )


gpu_name = torch.cuda.get_device_name(0)

vram_gb = (
    torch.cuda.get_device_properties(0).total_memory
    / 1024**3
)


print("GPU:", gpu_name)

print(
    "VRAM GB:",
    round(vram_gb, 2)
)


# ============================================================
# LOAD TOKENIZER
# ============================================================

print("\nLoading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True,
)

print("Tokenizer loaded.")


# ============================================================
# CHECK <extra_0>
# ============================================================

extra_token = "<extra_0>"

extra_ids = tokenizer.encode(
    extra_token,
    add_special_tokens=False
)

if len(extra_ids) != 1:

    raise RuntimeError(
        "<extra_0> is not represented as exactly one token."
    )


STEP_SEP_ID = extra_ids[0]

print(
    "<extra_0> token ID:",
    STEP_SEP_ID
)


# ============================================================
# LOAD QWEN PRM
# ============================================================

print("\nLoading Qwen PRM model...")

print(
    "Using 4-bit NF4 quantization "
    "for the 6 GB RTX 2060."
)


bnb_config = BitsAndBytesConfig(

    load_in_4bit=True,

    bnb_4bit_quant_type="nf4",

    bnb_4bit_compute_dtype=torch.float16,

    bnb_4bit_use_double_quant=True,
)


model = AutoModel.from_pretrained(

    MODEL_PATH,

    trust_remote_code=True,

    device_map="auto",

    quantization_config=bnb_config,
)


model.eval()


print("Model loaded successfully.")

print(
    "Model input device:",
    next(model.parameters()).device
)


# ============================================================
# QWEN PRM SCORING FUNCTION
# ============================================================

def score_response(problem, response):

    """
    Score one reasoning response using Qwen2.5-Math-PRM-7B.

    Qwen PRM expects:
        reasoning step 1
        <extra_0>
        reasoning step 2
        <extra_0>
        ...

    The model produces two-class logits at every token.
    At each <extra_0> token we take:

        softmax(logits)[positive class]

    as the step reward.
    """

    # --------------------------------------------------------
    # Split response into reasoning steps
    # --------------------------------------------------------

    response = response.replace(
        "\r\n",
        "\n"
    ).strip()

    # Your existing responses use separate lines for steps.
    # Treat each non-empty line as one step.

    raw_lines = response.split("\n")

    steps = [
        line.strip()
        for line in raw_lines
        if line.strip()
    ]

    if len(steps) == 0:

        raise ValueError(
            "Response contains no reasoning steps."
        )


    # --------------------------------------------------------
    # Add <extra_0> AFTER EVERY STEP
    # --------------------------------------------------------

    formatted_solution = ""

    for step in steps:

        formatted_solution += (
            step
            + "<extra_0>"
        )


    # --------------------------------------------------------
    # Qwen PRM conversation format
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


    # --------------------------------------------------------
    # Apply Qwen chat template
    # --------------------------------------------------------

    conversation_str = tokenizer.apply_chat_template(

        messages,

        tokenize=False,

        add_generation_prompt=False,
    )


    # --------------------------------------------------------
    # Tokenize
    # --------------------------------------------------------

    inputs = tokenizer(

        conversation_str,

        return_tensors="pt",

        truncation=True,

        max_length=4096,
    )


    # --------------------------------------------------------
    # Move to model device
    # --------------------------------------------------------

    model_device = next(
        model.parameters()
    ).device


    input_ids = inputs["input_ids"].to(
        model_device
    )


    attention_mask = inputs.get(
        "attention_mask"
    )


    if attention_mask is not None:

        attention_mask = attention_mask.to(
            model_device
        )


    # --------------------------------------------------------
    # Forward pass
    # --------------------------------------------------------

    with torch.no_grad():

        if attention_mask is not None:

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )

        else:

            outputs = model(
                input_ids=input_ids
            )


    # --------------------------------------------------------
    # Get logits
    # --------------------------------------------------------

    # Qwen2ForProcessRewardModel returns logits
    # with shape:
    #
    # [batch, sequence_length, 2]

    if hasattr(outputs, "logits"):

        logits = outputs.logits

    elif isinstance(outputs, tuple):

        logits = outputs[0]

    else:

        raise RuntimeError(
            "Could not find logits in model output."
        )


    # --------------------------------------------------------
    # Find <extra_0> positions
    # --------------------------------------------------------

    token_mask = (
        input_ids == STEP_SEP_ID
    )


    # --------------------------------------------------------
    # Calculate probabilities
    # --------------------------------------------------------

    probabilities = F.softmax(
        logits.float(),
        dim=-1
    )


    # --------------------------------------------------------
    # Extract positive-class probability
    # at each <extra_0>
    # --------------------------------------------------------

    step_scores = []

    positions = torch.nonzero(
        token_mask[0],
        as_tuple=False
    ).flatten()


    for position in positions:

        position = int(position.item())

        positive_probability = float(
            probabilities[
                0,
                position,
                1
            ].item()
        )

        step_scores.append(
            positive_probability
        )


    if len(step_scores) == 0:

        raise RuntimeError(
            "No <extra_0> reward positions found."
        )


    return step_scores


# ============================================================
# EVALUATION
# ============================================================

print("\n")
print("=" * 70)
print("STARTING QWEN ARABIC PRM EVALUATION")
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


        problem = example["problem"]

        response = example[
            "responses"
        ][category]


        try:

            scores = score_response(
                problem,
                response
            )


            average_score = (
                sum(scores)
                / len(scores)
            )


            minimum_score = min(scores)

            maximum_score = max(scores)


            print(
                f"      Average: "
                f"{average_score:.4f}"
                f" | Min: "
                f"{minimum_score:.4f}"
                f" | Max: "
                f"{maximum_score:.4f}"
            )


            status = "success"


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
# SAVE CSV
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

) as file:

    writer = csv.DictWriter(

        file,

        fieldnames=fieldnames

    )

    writer.writeheader()

    writer.writerows(results)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n")
print("=" * 70)
print("FINAL RESULTS")
print("=" * 70)


successful_results = [

    r

    for r in results

    if r["status"] == "success"

]


print(
    f"\nSuccessful evaluations: "
    f"{len(successful_results)}"
)

print(
    f"Expected evaluations: "
    f"{total_expected}"
)


for category in CATEGORIES:

    category_results = [

        r

        for r in successful_results

        if r["category"] == category

    ]


    if not category_results:

        continue


    average = sum(

        r["average_score"]

        for r in category_results

    ) / len(category_results)


    average_min = sum(

        r["minimum_score"]

        for r in category_results

    ) / len(category_results)


    average_max = sum(

        r["maximum_score"]

        for r in category_results

    ) / len(category_results)


    print("\n" + category.upper())

    print("-" * 40)

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
        f"{average_min:.4f}"
    )

    print(
        f"Average maximum: "
        f"{average_max:.4f}"
    )


# ============================================================
# CORRECT VS INCORRECT
# ============================================================

correct_results = [

    r

    for r in successful_results

    if r["category"] == "correct"

]


incorrect_results = [

    r

    for r in successful_results

    if r["category"] != "correct"

]


if correct_results and incorrect_results:

    correct_average = sum(

        r["average_score"]

        for r in correct_results

    ) / len(correct_results)


    incorrect_average = sum(

        r["average_score"]

        for r in incorrect_results

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
# FINISH
# ============================================================

print("\n")
print("=" * 70)
print("QWEN ARABIC PRM EVALUATION COMPLETE")
print("=" * 70)


print(
    f"\nResults saved to:"
)

print(
    OUTPUT_FILE
)


print("\n")
print("=" * 70)
print("IMPORTANT")
print("=" * 70)

print(
    "\nThis experiment uses the same 20 Arabic "
    "problems and the same four response categories "
    "as the Skywork experiment."
)

print(
    "\nThe Qwen PRM score is the probability of "
    "the positive/correct class at each <extra_0> "
    "step marker."
)

print(
    "\nQwen's official model documentation describes "
    "this step-marker probability as the reward value."
)