import torch

from transformers import BitsAndBytesConfig
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
)

from model_utils.prm_model import PRM_MODEL


MODEL_PATH = "Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B"


print("=" * 70)
print("ARABICPRM QLORA ATTACH TEST")
print("=" * 70)


quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16,
)


print("\nLoading PRM...")

model = PRM_MODEL.from_pretrained(
    MODEL_PATH,
    quantization_config=quant_config,
    device_map={"": 0},
    dtype=torch.float16,
)


print("Preparing Qwen backbone for QLoRA...")

model.pretrained_model = prepare_model_for_kbit_training(
    model.pretrained_model,
    use_gradient_checkpointing=True,
)


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


print("Attaching LoRA...")

model.pretrained_model = get_peft_model(
    model.pretrained_model,
    lora_config,
)

model.is_peft_model = True


# Make sure the PRM value head is trainable
for param in model.v_head.parameters():
    param.requires_grad = True


print("\nLoRA information:")
model.pretrained_model.print_trainable_parameters()


print("\nTrainable parameters in complete PRM:")

trainable = 0
total = 0

for name, param in model.named_parameters():

    total += param.numel()

    if param.requires_grad:

        trainable += param.numel()

        print(
            f"{name:<90} "
            f"{param.numel():>12,}"
        )


print("\n" + "=" * 70)

print(f"Trainable parameters : {trainable:,}")
print(f"Total parameters     : {total:,}")

print(
    f"Trainable percentage : "
    f"{100 * trainable / total:.4f}%"
)


allocated = torch.cuda.memory_allocated() / 1024**3
reserved = torch.cuda.memory_reserved() / 1024**3


print("\nGPU memory:")
print(f"Allocated : {allocated:.2f} GB")
print(f"Reserved  : {reserved:.2f} GB")


print("\nQLoRA attachment test complete.")