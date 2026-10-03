import torch
import torch.nn as nn

from transformers import AutoTokenizer, BitsAndBytesConfig
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
)

from model_utils.prm_model import PRM_MODEL
from model_utils.io_utils import (
    prepare_input,
    prepare_batch_input_for_model,
)


MODEL_PATH = "Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B"


print("=" * 70)
print("ARABICPRM FIRST QLORA TRAINING SMOKE TEST")
print("=" * 70)


# ============================================================
# 1. TOKENIZER
# ============================================================

print("\nLoading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True,
)

if tokenizer.pad_token_id is None:
    tokenizer.pad_token = tokenizer.eos_token


# ============================================================
# 2. 4-BIT QUANTIZATION
# ============================================================

quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16,
)


# ============================================================
# 3. LOAD ORIGINAL SKYWORK PRM
# ============================================================

print("Loading Skywork PRM in 4-bit...")

model = PRM_MODEL.from_pretrained(
    MODEL_PATH,
    quantization_config=quant_config,
    device_map={"": 0},
    dtype=torch.float16,
)


# ============================================================
# 4. PREPARE QLORA
# ============================================================

print("Preparing model for QLoRA...")

model.pretrained_model = prepare_model_for_kbit_training(
    model.pretrained_model,
    use_gradient_checkpointing=True,
)

model.pretrained_model.config.use_cache = False


lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=[
        "q_proj",
        "v_proj",
    ],
)


model.pretrained_model = get_peft_model(
    model.pretrained_model,
    lora_config,
)

model.is_peft_model = True

# Keep the PRM value head explicitly on the GPU
model.v_head = model.v_head.to("cuda:0")


# Keep the original PRM value head trainable
for param in model.v_head.parameters():
    param.requires_grad = True


model.train()


# ============================================================
# 5. TINY ARABIC SMOKE-TEST DATA
# ============================================================

#
# IMPORTANT:
#
# This is NOT the final thesis training dataset.
#
# It contains only two tiny examples to prove that:
#
# Arabic text
#      ↓
# tokenization
#      ↓
# reward positions
#      ↓
# BCE loss
#      ↓
# backpropagation
#      ↓
# LoRA + v_head parameter update
#
# works end-to-end.
#


examples = [

    {
        "problem": "احسب 7 + 5.",
        "response": (
            "نحسب 7 + 5 = 12.\n"
            "إذن الإجابة هي 12."
        ),

        # Both reasoning steps are valid
        "labels": [
            1.0,
            1.0,
        ],
    },

    {
        "problem": "احسب 7 + 5.",
        "response": (
            "نحسب 7 + 5 = 13.\n"
            "إذن الإجابة هي 13."
        ),

        # Error begins immediately
        "labels": [
            0.0,
            0.0,
        ],
    },

]


# ============================================================
# 6. PREPARE INPUT
# ============================================================

all_input_ids = []
all_reward_flags = []
all_labels = []


for example_id, example in enumerate(examples):

    input_ids, steps, reward_flags = prepare_input(
        example["problem"],
        example["response"],
        tokenizer=tokenizer,
        step_token="\n",
    )

    labels = example["labels"]

    print(f"\nExample {example_id + 1}")

    print("Problem:")
    print(example["problem"])

    print("\nSteps:")

    for i, step in enumerate(steps):

        print(
            f"  Step {i + 1}: "
            f"label={labels[i]:.0f} | "
            f"{step.strip()}"
        )

    assert len(steps) == len(labels), (
        f"Step/label mismatch: "
        f"{len(steps)} steps but "
        f"{len(labels)} labels."
    )

    assert sum(reward_flags) == len(labels), (
        "Reward flag count does not match label count."
    )

    all_input_ids.append(input_ids)
    all_reward_flags.append(reward_flags)

    all_labels.extend(labels)


# ============================================================
# 7. BATCH
# ============================================================

input_ids, attention_mask, reward_flags = (
    prepare_batch_input_for_model(
        all_input_ids,
        all_reward_flags,
        tokenizer.pad_token_id,
    )
)


device = torch.device("cuda")


input_ids = input_ids.to(device)

attention_mask = attention_mask.to(device)

reward_flags = reward_flags.to(device)


labels = torch.tensor(
    all_labels,
    dtype=torch.float32,
    device=device,
)


print("\nBatch shape:")
print("input_ids:", input_ids.shape)

print(
    "Number of supervised steps:",
    int(reward_flags.sum().item())
)

print(
    "Labels:",
    labels.tolist()
)


# ============================================================
# 8. OPTIMIZER
# ============================================================

optimizer = torch.optim.AdamW(
    [
        p
        for p in model.parameters()
        if p.requires_grad
    ],
    lr=1e-4,
)


loss_function = nn.BCEWithLogitsLoss()


# ============================================================
# 9. SAVE PARAMETERS BEFORE UPDATE
# ============================================================

first_lora_name = None
first_lora_parameter = None


for name, parameter in model.named_parameters():

    if (
        "lora_B" in name
    	and parameter.requires_grad
    ):

        first_lora_name = name

        first_lora_parameter = parameter

        break


if first_lora_parameter is None:

    raise RuntimeError(
        "Could not find trainable LoRA parameter."
    )


lora_before = (
    first_lora_parameter
    .detach()
    .clone()
)


v_head_before = (
    model.v_head.summary.weight
    .detach()
    .clone()
)


# ============================================================
# 10. FORWARD PASS
# ============================================================

print("\nRunning forward pass...")


optimizer.zero_grad()


_, _, reward_logits = model(
    input_ids=input_ids,
    attention_mask=attention_mask,
    return_probs=False,
)


print(
    "Reward tensor shape:",
    reward_logits.shape
)


# ============================================================
# 11. SELECT ONLY STEP-END POSITIONS
# ============================================================

print("reward_logits device:", reward_logits.device)
print("reward_flags device :", reward_flags.device)
print("v_head device       :", model.v_head.summary.weight.device)

step_mask = reward_flags.bool().to(
    reward_logits.device
)

labels = labels.to(
    reward_logits.device
)

step_logits = reward_logits[
    step_mask
]


print(
    "Selected step logits:",
    step_logits.detach().cpu().tolist()
)


assert step_logits.numel() == labels.numel(), (
    f"Found {step_logits.numel()} "
    f"reward positions but "
    f"{labels.numel()} labels."
)


# ============================================================
# 12. LOSS
# ============================================================

loss = loss_function(
    step_logits.float(),
    labels,
)


print(
    f"\nLoss before update: "
    f"{loss.item():.6f}"
)


# ============================================================
# 13. BACKPROPAGATION
# ============================================================

print("Running backward pass...")


loss.backward()


lora_grad = (
    first_lora_parameter.grad
)


v_head_grad = (
    model.v_head.summary.weight.grad
)


print("\nGradient check:")


if lora_grad is None:

    print("LoRA gradient: NONE")

else:

    print(
        "LoRA gradient norm:",
        float(
            lora_grad.float().norm().item()
        )
    )


if v_head_grad is None:

    print("v_head gradient: NONE")

else:

    print(
        "v_head gradient norm:",
        float(
            v_head_grad.float().norm().item()
        )
    )


# ============================================================
# 14. OPTIMIZER STEP
# ============================================================

print("\nApplying optimizer step...")


optimizer.step()


# ============================================================
# 15. VERIFY PARAMETERS ACTUALLY CHANGED
# ============================================================

lora_change = (
    first_lora_parameter.detach()
    - lora_before
).abs().max().item()


v_head_change = (
    model.v_head.summary.weight.detach()
    - v_head_before
).abs().max().item()


print("\nParameter update verification:")

print(
    "LoRA parameter:",
    first_lora_name,
)

print(
    f"Maximum LoRA weight change: "
    f"{lora_change:.10f}"
)

print(
    f"Maximum v_head weight change: "
    f"{v_head_change:.10f}"
)


# ============================================================
# 16. GPU MEMORY
# ============================================================

allocated = (
    torch.cuda.memory_allocated()
    / 1024**3
)

reserved = (
    torch.cuda.memory_reserved()
    / 1024**3
)

peak = (
    torch.cuda.max_memory_allocated()
    / 1024**3
)


print("\nGPU memory:")

print(
    f"Allocated : {allocated:.2f} GB"
)

print(
    f"Reserved  : {reserved:.2f} GB"
)

print(
    f"Peak       : {peak:.2f} GB"
)


# ============================================================
# 17. RESULT
# ============================================================

print("\n" + "=" * 70)


if (
    lora_grad is not None
    and v_head_grad is not None
    and lora_change > 0
    and v_head_change > 0
):

    print(
        "SUCCESS: ArabicPRM training "
        "pipeline works end-to-end."
    )

else:

    print(
        "WARNING: Training pipeline "
        "needs further debugging."
    )


print("=" * 70)