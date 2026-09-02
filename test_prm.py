import torch
from transformers import AutoTokenizer
from model_utils.prm_model import PRM_MODEL
from model_utils.io_utils import (
    prepare_input,
    prepare_batch_input_for_model,
    derive_step_rewards,
)

# ============================================================
# CONFIGURATION
# ============================================================

MODEL_PATH = "Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B"

# ============================================================
# ARABIC TEST PROBLEM
# ============================================================

problem = """
لدى أحمد 20 تفاحة. أعطى 7 تفاحات لصديقه، ثم اشترى 5 تفاحات أخرى.
كم تفاحة لديه الآن؟
"""

# ============================================================
# FOUR DIFFERENT RESPONSES
# ============================================================

datas = [

    # --------------------------------------------------------
    # 1. CORRECT REASONING
    # --------------------------------------------------------
    {
        "problem": problem,
        "response": """
في البداية، لدى أحمد 20 تفاحة.

أعطى أحمد 7 تفاحات لصديقه، لذلك نحسب:
20 - 7 = 13 تفاحة.

بعد ذلك، اشترى أحمد 5 تفاحات أخرى، لذلك نحسب:
13 + 5 = 18 تفاحة.

إذن، لدى أحمد الآن 18 تفاحة.
"""
    },

    # --------------------------------------------------------
    # 2. INCORRECT ARITHMETIC
    # --------------------------------------------------------
    {
        "problem": problem,
        "response": """
في البداية، لدى أحمد 20 تفاحة.

أعطى أحمد 7 تفاحات لصديقه:
20 - 7 = 13 تفاحة.

بعد ذلك، اشترى أحمد 5 تفاحات أخرى:
13 + 5 = 19 تفاحة.

إذن، لدى أحمد الآن 19 تفاحة.
"""
    },

    # --------------------------------------------------------
    # 3. WRONG REASONING
    # --------------------------------------------------------
    {
        "problem": problem,
        "response": """
لدى أحمد 20 تفاحة في البداية.

أعطى أحمد 7 تفاحات لصديقه، لذلك أصبح لديه:
20 + 7 = 27 تفاحة.

ثم اشترى 5 تفاحات أخرى:
27 + 5 = 32 تفاحة.

إذن، لدى أحمد الآن 32 تفاحة.
"""
    },

    # --------------------------------------------------------
    # 4. COMPLETELY WRONG ANSWER
    # --------------------------------------------------------
    {
        "problem": problem,
        "response": """
لدى أحمد 20 تفاحة.

أعطى 7 تفاحات ثم اشترى 5 تفاحات، لذلك نطرح العددين:
20 - 7 - 5 = 8 تفاحات.

إذن، لدى أحمد 8 تفاحات.
"""
    },
]

# ============================================================
# LOAD TOKENIZER
# ============================================================

print("Loading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True
)

# ============================================================
# PREPARE INPUTS
# ============================================================

print("Preparing inputs...")

processed_data = [
    prepare_input(
        d["problem"],
        d["response"],
        tokenizer=tokenizer,
        step_token="\n"
    )
    for d in datas
]

input_ids, steps, reward_flags = zip(*processed_data)

# ============================================================
# PREPARE BATCH
# ============================================================

print("Preparing batch...")

input_ids, attention_mask, reward_flags = (
    prepare_batch_input_for_model(
        input_ids,
        reward_flags,
        tokenizer.pad_token_id
    )
)

# Move inputs to GPU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

input_ids = input_ids.to(device)
attention_mask = attention_mask.to(device)

# ============================================================
# LOAD PRM MODEL
# ============================================================

print("Loading PRM model...")

model = PRM_MODEL.from_pretrained(
    MODEL_PATH,
    device_map="auto"
).eval()

# ============================================================
# INFERENCE
# ============================================================

print("Running Arabic PRM evaluation...\n")

with torch.no_grad():

    _, _, rewards = model(
        input_ids=input_ids,
        attention_mask=attention_mask,
        return_probs=True
    )

# ============================================================
# DERIVE STEP REWARDS
# ============================================================

step_rewards = derive_step_rewards(
    rewards,
    reward_flags
)

# ============================================================
# DISPLAY RESULTS
# ============================================================

print("=" * 70)
print("ARABIC PRM — CORRECT vs INCORRECT REASONING")
print("=" * 70)

labels = [
    "CORRECT REASONING",
    "INCORRECT ARITHMETIC",
    "WRONG REASONING",
    "COMPLETELY WRONG"
]

for i, (label, scores) in enumerate(zip(labels, step_rewards)):

    print("\n" + "-" * 70)
    print(f"{i + 1}. {label}")
    print("-" * 70)

    print("Response:")
    print(datas[i]["response"].strip())

    print("\nStep-level PRM scores:")

    for j, score in enumerate(scores):
        print(f"  Step {j + 1}: {score:.4f}")

    avg_score = sum(scores) / len(scores)
    min_score = min(scores)
    max_score = max(scores)

    print(f"\nAverage score : {avg_score:.4f}")
    print(f"Minimum score : {min_score:.4f}")
    print(f"Maximum score : {max_score:.4f}")

print("\n" + "=" * 70)
print("EVALUATION COMPLETE")
print("=" * 70)