import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM


MODEL_NAME = "Qwen/Qwen2.5-Math-1.5B-Instruct"
DATA_FILE = r"data\processed\global_mgsm_ar_en_100.jsonl"

# Cases where the previous Arabic generation was especially suspicious
PROBLEM_IDS = [3, 7, 8, 10, 18, 24, 42, 72, 89, 100]

MAX_NEW_TOKENS = 512

OUTPUT_FILE = "qwen_arabic_prompt_audit.txt"


# ============================================================
# LOAD DATA
# ============================================================

problems = []

with open(DATA_FILE, "r", encoding="utf-8") as f:
    for line in f:
        problems.append(json.loads(line))


by_id = {
    int(row["id"]): row
    for row in problems
}


# ============================================================
# LOAD MODEL
# ============================================================

print("Loading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME
)


print("Loading model...")

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    dtype=torch.float16,
    device_map="auto",
)

model.eval()


# ============================================================
# SAME ARABIC INSTRUCTION STYLE USED IN THE MAIN EXPERIMENT
# ============================================================

def make_arabic_message(question):

    content = (
        "حل المسألة التالية بعناية. "
        "فكر خطوة بخطوة، ثم اكتب الإجابة النهائية فقط بالشكل التالي:\n"
        "الإجابة النهائية: <رقم>\n\n"
        f"المسألة:\n{question}"
    )

    return [
        {
            "role": "user",
            "content": content,
        }
    ]


# ============================================================
# AUDIT
# ============================================================

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8",
) as out:

    for problem_id in PROBLEM_IDS:

        row = by_id[problem_id]

        question = row["question_ar"]
        gold = row["gold_answer"]

        messages = make_arabic_message(
            question
        )

        # Render the exact chat-template text
        rendered_prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        # Tokenize it
        inputs = tokenizer(
            rendered_prompt,
            return_tensors="pt",
        )

        # Decode input IDs back into text.
        # This verifies that Arabic survived tokenization.
        decoded_input = tokenizer.decode(
            inputs["input_ids"][0],
            skip_special_tokens=False,
        )

        inputs = {
            key: value.to(model.device)
            for key, value in inputs.items()
        }

        with torch.no_grad():

            generated = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id
                if tokenizer.pad_token_id is not None
                else tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
                use_cache=True,
            )

        input_length = inputs["input_ids"].shape[1]

        completion_ids = generated[
            0,
            input_length:
        ]

        completion = tokenizer.decode(
            completion_ids,
            skip_special_tokens=True,
        )

        separator = "=" * 100

        block = f"""
{separator}
PROBLEM {problem_id}
{separator}

GOLD ANSWER:
{gold}

ORIGINAL ARABIC QUESTION:
{question}

MESSAGES SENT TO CHAT TEMPLATE:
{messages}

RENDERED CHAT PROMPT:
{rendered_prompt}

DECODED INPUT TOKENS:
{decoded_input}

MODEL COMPLETION:
{completion}

"""

        print(block)

        out.write(block)


print("\nAudit complete.")
print("Saved:", OUTPUT_FILE)