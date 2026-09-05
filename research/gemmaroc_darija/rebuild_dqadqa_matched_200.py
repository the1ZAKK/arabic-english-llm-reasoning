import json
import random
import re
from decimal import Decimal, InvalidOperation

from datasets import load_dataset


SEED = 42
SAMPLE_SIZE = 200

OUTPUT_CLEAN = "research/gemmaroc_darija/dqadqa_gsm8k_clean_pairs.jsonl"
OUTPUT_SAMPLE = "research/gemmaroc_darija/dqadqa_gsm8k_matched_200.jsonl"


def normalize_number(value):
    """
    Convert answer-like text to a Decimal for reliable numeric comparison.
    """
    if value is None:
        return None

    text = str(value).strip()

    # Remove commas and common surrounding text/symbols
    text = text.replace(",", "")
    text = text.replace("$", "")
    text = text.replace("£", "")
    text = text.replace("€", "")

    # Prefer a number following GSM8K's #### marker
    if "####" in text:
        text = text.split("####")[-1].strip()

    matches = re.findall(r"-?\d+(?:\.\d+)?", text)

    if not matches:
        return None

    # The final numeric value is normally the answer
    number = matches[-1]

    try:
        return Decimal(number)
    except InvalidOperation:
        return None


print("Loading DqaDqa...")
dqadqa = load_dataset(
    "abdeljalilELmajjodi/DqaDqa",
    split="train"
)

print("Loading GSM8K...")
gsm8k = load_dataset(
    "openai/gsm8k",
    "main",
    split="train"
)

print()
print("DqaDqa rows:", len(dqadqa))
print("GSM8K train rows:", len(gsm8k))

clean_pairs = []
mismatches = []
unmapped = []

for row_position, row in enumerate(dqadqa):
    raw_id = row.get("id")

    try:
        gsm_index = int(raw_id)
    except (TypeError, ValueError):
        unmapped.append({
            "row_position": row_position,
            "id": raw_id,
            "reason": "non-integer id"
        })
        continue

    if gsm_index < 0 or gsm_index >= len(gsm8k):
        unmapped.append({
            "row_position": row_position,
            "id": raw_id,
            "reason": "id outside GSM8K train range"
        })
        continue

    gsm_row = gsm8k[gsm_index]

    darija_answer = normalize_number(row.get("answer"))
    english_answer = normalize_number(gsm_row.get("answer"))

    if darija_answer is None or english_answer is None:
        mismatches.append({
            "id": raw_id,
            "darija_answer": row.get("answer"),
            "gsm8k_answer": gsm_row.get("answer"),
            "reason": "could not parse numeric answer"
        })
        continue

    if darija_answer != english_answer:
        mismatches.append({
            "id": raw_id,
            "darija_answer": str(darija_answer),
            "gsm8k_answer": str(english_answer),
            "reason": "numeric answers differ"
        })
        continue

    clean_pairs.append({
        "id": gsm_index,
        "question_en": gsm_row["question"],
        "question_darija": row["question_darija"],
        "reasoning_darija": row.get("reasoning_darija"),
        "answer": str(darija_answer),
        "gsm8k_answer_raw": gsm_row["answer"],
    })


print()
print("Clean matched pairs:", len(clean_pairs))
print("Excluded/mismatched:", len(mismatches))
print("Unmapped:", len(unmapped))

EXPECTED_CLEAN = 7423

if len(clean_pairs) != EXPECTED_CLEAN:
    raise RuntimeError(
        f"STOP: expected {EXPECTED_CLEAN} clean pairs, "
        f"but reconstructed {len(clean_pairs)}. "
        "Do not sample until the mapping is verified."
    )

with open(OUTPUT_CLEAN, "w", encoding="utf-8") as f:
    for item in clean_pairs:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

rng = random.Random(SEED)
sample = rng.sample(clean_pairs, SAMPLE_SIZE)

for problem_id, item in enumerate(sample, start=1):
    item["problem_id"] = problem_id

with open(OUTPUT_SAMPLE, "w", encoding="utf-8") as f:
    for item in sample:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print()
print("SUCCESS")
print("Saved clean pool:", OUTPUT_CLEAN)
print("Saved 200-pair sample:", OUTPUT_SAMPLE)
print("Seed:", SEED)
print("Sample size:", len(sample))

print()
print("First 10 sampled GSM8K IDs:")
print([x["id"] for x in sample[:10]])