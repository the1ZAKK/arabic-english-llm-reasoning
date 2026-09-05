import json
import os
from openai import OpenAI

MODEL = "deepseek/deepseek-v3.2"
BASE_URL = "https://api.novita.ai/openai"
DATASET = r"research\gemmaroc_darija\dqadqa_gsm8k_matched_200.jsonl"

client = OpenAI(
    api_key=os.environ["NOVITA_API_KEY"],
    base_url=BASE_URL,
)

# Load exactly the same first matched English-Darija pair
with open(DATASET, "r", encoding="utf-8-sig") as f:
    first = json.loads(next(f))

english_question = first["question_en"]
darija_question = first["question_darija"]
gold = first["answer"]


def run(language, question):
    prompt = (
        "Solve the following math problem carefully. "
        "Show your reasoning, then give the final numeric answer in the format:\n"
        "FINAL ANSWER: <number>\n\n"
        f"{question}"
    )

    print("\n" + "=" * 70)
    print(language)
    print("=" * 70)
    print("QUESTION:")
    print(question)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0,
        max_tokens=4096,
    )

    text = response.choices[0].message.content or ""

    print("\nRESPONSE:")
    print(text)

    if response.usage:
        print("\nTOKEN USAGE:")
        print("Prompt:", response.usage.prompt_tokens)
        print("Completion:", response.usage.completion_tokens)
        print("Total:", response.usage.total_tokens)

    return text


print("MODEL:", MODEL)
print("GOLD ANSWER:", gold)

run("ENGLISH", english_question)
run("DARIJA", darija_question)

print("\n" + "=" * 70)
print("PILOT COMPLETE")
print("=" * 70)