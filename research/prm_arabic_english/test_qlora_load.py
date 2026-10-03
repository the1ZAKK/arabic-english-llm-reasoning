import torch

from transformers import AutoTokenizer, BitsAndBytesConfig
from model_utils.prm_model import PRM_MODEL


MODEL_PATH = "Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B"


print("=" * 70)
print("ARABICPRM QLORA LOAD TEST")
print("=" * 70)

print("\nGPU:")
print(torch.cuda.get_device_name(0))

torch.cuda.empty_cache()
torch.cuda.reset_peak_memory_stats()


quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16,
)


print("\nLoading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True,
)


print("Loading PRM in 4-bit...")

model = PRM_MODEL.from_pretrained(
    MODEL_PATH,
    quantization_config=quant_config,
    device_map={"": 0},
    dtype=torch.float16,
)


print("\nMODEL LOADED SUCCESSFULLY")


allocated = torch.cuda.memory_allocated() / 1024**3
reserved = torch.cuda.memory_reserved() / 1024**3
peak = torch.cuda.max_memory_allocated() / 1024**3


print(f"Allocated VRAM : {allocated:.2f} GB")
print(f"Reserved VRAM  : {reserved:.2f} GB")
print(f"Peak VRAM      : {peak:.2f} GB")


print("\nValue head:")
print(model.v_head)


print("\nBase model:")
print(type(model.pretrained_model))


print("\n4-bit status:")
print(
    "is_loaded_in_4bit:",
    getattr(model.pretrained_model, "is_loaded_in_4bit", False)
)


print("\nTest complete.")