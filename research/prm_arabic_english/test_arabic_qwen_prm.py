import ast
import csv
import gc
import os

import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_PATH = "Qwen/Qwen2.5-Math-PRM-7B"

# Existing Skywork dataset file.
# We extract ONLY the examples variable from this file.
DATASET_FILE = "test_arabic_prm.py"

OUTPUT_FILE = "arabic_qwen_prm_results.csv"

CATEGORIES = [
    "correct",
    "arithmetic_error",
    "logic_error",
    "completely_wrong",
]

# Qwen PRM expects <extra_0> between reasoning steps.
STEP_TOKEN = "<extra_0>"

# Official Qwen prompt format.
SYSTEM_PROMPT = (
    "Please reason step by step, and put your final answer within \\boxed{}."
)


# ============================================================
# LOAD THE EXACT SAME DATASET
# ============================================================

def load_examples_from_existing_file(filename):
    """
    Extract the `examples = [...]` variable from the existing
    test_arabic_prm.py WITHOUT executing that file.

    This guarantees that the Qwen experiment uses the same
    20 problems and the same four response categories.
    """

    if not os.path.exists(filename):
        raise FileNotFoundError(
            f"Could not find dataset file: {filename}"
        )

    with open(filename, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in tree.body:

        if isinstance(node, ast.Assign):

            for target in node.targets:

                if (
                    isinstance(target, ast.Name)
                    and target.id == "examples"
                ):
                    return ast.literal_eval(node.value)

    raise ValueError(
        "Could not find `examples = [...]` in "
        + filename
    )


print("=" * 70)
print("QWEN ARABIC PRM LARGE-SCALE EVALUATION")
print("=" * 70)

print("\nLoading exact dataset from:")
print(DATASET_FILE)

examples = load_examples_from_existing_file(DATASET_FILE)


# ============================================================
# DATASET VALIDATION
# ============================================================

print("\nValidating dataset...")

if len(examples) != 20:
    raise ValueError(
        f"Expected exactly 20 problems, "
        f"but found {len(examples)}."
    )

expected_ids = list(range(1, 21))
actual_ids = [int(x["id"]) for x in examples]

if actual_ids != expected_ids:
    raise ValueError(
        f"Problem IDs are incorrect.\n"
        f"Expected: {expected_ids}\n"
        f"Found:    {actual_ids}"
    )

for example in examples:

    if "problem" not in example:
        raise ValueError(
            f"Problem {example['id']} has no problem text."
        )

    if "responses" not in example:
        raise ValueError(
            f"Problem {example['id']} has no responses."
        )

    missing = [
        category
        for category in CATEGORIES
        if category not in example["responses"]
    ]

    if missing:
        raise ValueError(
            f"Problem {example['id']} is missing categories: "
            f"{missing}"
        )

print("Dataset validation successful.")
print(f"Problems: {len(examples)}")
print(f"Categories per problem: {len(CATEGORIES)}")
print(
    f"Expected evaluations: "
    f"{len(examples) * len(CATEGORIES)}"
)


# ============================================================
# DEVICE / MEMORY INFORMATION
# ============================================================

print("\n" + "=" * 70)
print("DEVICE INFORMATION")
print("=" * 70)

if torch.cuda.is_available():

    print("CUDA available: YES")
    print(
        "GPU:",
        torch.cuda.get_device_name(0)
    )

    gpu_memory = torch.cuda.get_device_properties(
        0
    ).total_memory / (1024 ** 3)

    print(
        f"GPU VRAM: {gpu_memory:.2f} GB"
    )

else:

    print("CUDA available: NO")
    print(
        "WARNING: Qwen2.5-Math-PRM-7B is approximately "
        "15.3 GB of weights."
    )
    print(
        "Your 16 GB system RAM is likely insufficient "
        "for comfortable CPU loading."
    )


# ============================================================
# LOAD TOKENIZER
# ============================================================

print("\n" + "=" * 70)
print("LOADING QWEN TOKENIZER")
print("=" * 70)

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True
)

print("Tokenizer loaded successfully.")


# ============================================================
# LOAD QWEN PRM
# ============================================================

print("\n" + "=" * 70)
print("LOADING QWEN PRM MODEL")
print("=" * 70)

print("Model:", MODEL_PATH)
print("Using device_map='auto'.")

# Qwen's official example uses AutoModel, not
# AutoModelForCausalLM, because this is a PRM.
#
# float16 is used on CUDA when possible.
# Qwen's official example uses bfloat16.

if torch.cuda.is_available():

    model = AutoModel.from_pretrained(
        MODEL_PATH,
        trust_remote_code=True,
        device_map="auto",
        torch_dtype=torch.bfloat16,
    ).eval()

else:

    # CPU fallback.
    # This may fail due to insufficient RAM.
    model = AutoModel.from_pretrained(
        MODEL_PATH,
        trust_remote_code=True,
        device_map="auto",
        torch_dtype=torch.float32,
    ).eval()


print("Model loaded successfully.")


# ============================================================
# DETERMINE MODEL DEVICE
# ============================================================

try:
    model_device = next(model.parameters()).device
except StopIteration:
    model_device = torch.device(
        "cuda" if torch.cuda.is_available()
        else "cpu"
    )

print("Model input device:", model_device)


# ============================================================
# QWEN STEP REWARD FUNCTION
# ============================================================

def make_step_rewards(logits, token_masks):

    """
    Qwen's PRM output contains two classes:

        class 0 = negative
        class 1 = positive

    We extract the probability of class 1 at every
    <extra_0> token.
    """

    probabilities = F.softmax(
        logits,
        dim=-1
    )

    probabilities = (
        probabilities
        * token_masks.unsqueeze(-1)
    )

    all_scores = []

    for i in range(probabilities.size(0)):

        sample = probabilities[i]

        positive_probs = (
            sample[sample != 0]
            .view(-1, 2)[:, 1]
        )

        scores = positive_probs.cpu().tolist()

        all_scores.append(scores)

    return all_scores


# ============================================================
# TOKEN ID FOR <extra_0>
# ============================================================

step_token_ids = tokenizer.encode(
    STEP_TOKEN,
    add_special_tokens=False
)

if len(step_token_ids) != 1:

    raise ValueError(
        f"Expected {STEP_TOKEN} to be one token, "
        f"but tokenizer returned: {step_token_ids}"
    )

step_sep_id = step_token_ids[0]

print(
    f"{STEP_TOKEN} token ID:",
    step_sep_id
)


# ============================================================
# EVALUATION
# ============================================================

print("\n" + "=" * 70)
print("STARTING QWEN ARABIC PRM EVALUATION")
print("=" * 70)

results = []

total_evaluations = (
    len(examples) * len(CATEGORIES)
)

evaluation_number = 0


for example in examples:

    problem_id = example["id"]
    problem = example["problem"]

    print(
        f"\nProblem {problem_id}/"
        f"{len(examples)}"
    )

    for category in CATEGORIES:

        evaluation_number += 1

        response = example["responses"][category]

        print(
            f"  [{evaluation_number}/"
            f"{total_evaluations}] "
            f"{category}"
        )

        # ----------------------------------------------------
        # Convert response into Qwen PRM step format
        # ----------------------------------------------------
        #
        # The existing dataset uses newline-separated
        # reasoning steps.
        #
        # We use non-empty lines as steps and insert
        # <extra_0> after each step.
        # ----------------------------------------------------

        raw_lines = [
            line.strip()
            for line in response.strip().splitlines()
            if line.strip()
        ]

        if len(raw_lines) == 0:
            raise ValueError(
                f"Empty response for problem "
                f"{problem_id}, category {category}"
            )

        formatted_response = (
            STEP_TOKEN.join(raw_lines)
            + STEP_TOKEN
        )

        # ----------------------------------------------------
        # Build Qwen chat template
        # ----------------------------------------------------

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": problem,
            },
            {
                "role": "assistant",
                "content": formatted_response,
            },
        ]

        conversation = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )

        # ----------------------------------------------------
        # Tokenize
        # ----------------------------------------------------

        input_ids = tokenizer.encode(
            conversation,
            return_tensors="pt",
        )

        # Move to the model's input device.
        input_ids = input_ids.to(model_device)

        # ----------------------------------------------------
        # Forward pass
        # ----------------------------------------------------

        with torch.no_grad():

            outputs = model(
                input_ids=input_ids
            )

        # ----------------------------------------------------
        # Locate <extra_0> tokens
        # ----------------------------------------------------

        token_masks = (
            input_ids == step_sep_id
        )

        number_of_markers = int(
            token_masks.sum().item()
        )

        if number_of_markers == 0:

            raise RuntimeError(
                f"No {STEP_TOKEN} tokens found for "
                f"problem {problem_id}, "
                f"category {category}."
            )

        # ----------------------------------------------------
        # Extract step rewards
        # ----------------------------------------------------

        step_rewards = make_step_rewards(
            outputs[0],
            token_masks
        )[0]

        scores = [
            float(x)
            for x in step_rewards
        ]

        if len(scores) == 0:

            raise RuntimeError(
                f"No reward scores returned for "
                f"problem {problem_id}, "
                f"category {category}."
            )

        # ----------------------------------------------------
        # Statistics
        # ----------------------------------------------------

        avg_score = sum(scores) / len(scores)

        min_score = min(scores)

        max_score = max(scores)

        print(
            f"      Average: {avg_score:.4f} | "
            f"Min: {min_score:.4f} | "
            f"Max: {max_score:.4f}"
        )

        # ----------------------------------------------------
        # Save result
        # ----------------------------------------------------

        results.append({

            "problem_id": problem_id,

            "category": category,

            "problem": problem,

            "response": response.strip(),

            "num_steps": len(scores),

            "average_score": avg_score,

            "minimum_score": min_score,

            "maximum_score": max_score,

            "step_scores": " ".join(
                f"{x:.4f}"
                for x in scores
            ),
        })

        # ----------------------------------------------------
        # Memory cleanup
        # ----------------------------------------------------

        del input_ids
        del outputs
        del token_masks

        gc.collect()

        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# ============================================================
# VERIFY COMPLETENESS
# ============================================================

print("\n" + "=" * 70)
print("VERIFYING RESULTS")
print("=" * 70)

expected = len(examples) * len(CATEGORIES)
successful = len(results)

print(
    f"Successful evaluations: "
    f"{successful}"
)

print(
    f"Expected evaluations: "
    f"{expected}"
)

if successful != expected:

    raise RuntimeError(
        f"Expected {expected} results but got "
        f"{successful}."
    )

print("SUCCESS: All evaluations completed.")


# ============================================================
# SAVE CSV
# ============================================================

print("\n" + "=" * 70)
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
]

with open(
    OUTPUT_FILE,
    "w",
    newline="",
    encoding="utf-8-sig",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames
    )

    writer.writeheader()

    writer.writerows(results)

print(
    f"Results saved to:\n"
    f"{OUTPUT_FILE}"
)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("QWEN ARABIC PRM FINAL RESULTS")
print("=" * 70)

for category in CATEGORIES:

    category_scores = [
        row["average_score"]
        for row in results
        if row["category"] == category
    ]

    category_mins = [
        row["minimum_score"]
        for row in results
        if row["category"] == category
    ]

    category_maxs = [
        row["maximum_score"]
        for row in results
        if row["category"] == category
    ]

    print("\n" + category.upper())
    print("-" * 40)

    print(
        f"Examples       : "
        f"{len(category_scores)}"
    )

    print(
        f"Average score  : "
        f"{sum(category_scores) / len(category_scores):.4f}"
    )

    print(
        f"Average minimum: "
        f"{sum(category_mins) / len(category_mins):.4f}"
    )

    print(
        f"Average maximum: "
        f"{sum(category_maxs) / len(category_maxs):.4f}"
    )


# ============================================================
# CORRECT VS INCORRECT
# ============================================================

correct_scores = [
    row["average_score"]
    for row in results
    if row["category"] == "correct"
]

incorrect_scores = [
    row["average_score"]
    for row in results
    if row["category"] != "correct"
]

correct_mean = (
    sum(correct_scores)
    / len(correct_scores)
)

incorrect_mean = (
    sum(incorrect_scores)
    / len(incorrect_scores)
)

gap = correct_mean - incorrect_mean


print("\n" + "=" * 70)
print("CORRECT VS INCORRECT")
print("=" * 70)

print(
    f"\nCorrect examples average   : "
    f"{correct_mean:.4f}"
)

print(
    f"Incorrect examples average : "
    f"{incorrect_mean:.4f}"
)

print(
    f"Difference                  : "
    f"{gap:+.4f}"
)


print("\n" + "=" * 70)
print("QWEN ARABIC PRM EVALUATION COMPLETE")
print("=" * 70)

print("\nResults saved to:")
print(OUTPUT_FILE)

print("\nNext step:")
print(
    "Build/run the equivalent Qwen English "
    "evaluation using the same 20 problems."
)