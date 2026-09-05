import json
import os

from openai import OpenAI


MODEL = "openai/gpt-oss-120b"
BASE_URL = "https://api.novita.ai/openai"

DATASET_PATH = r"research\gemmaroc_darija\dqadqa_gsm8k_matched_200.jsonl"


def load_problem_1():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        first = json.loads(next(f))
    return first


def build_prompt(question):
    return (
        "Solve the following math problem carefully. "
        "Show your reasoning, then give the final numeric answer in the format:\n"
        "FINAL ANSWER: <number>\n\n"
        f"Problem:\n{question}"
    )


client = OpenAI(
    api_key=os.environ["NOVITA_API_KEY"],
    base_url=BASE_URL,
)

item = load_problem_1()

tests = [
    ("english", item["question_en"]),
    ("darija", item["question_darija"]),
]

for language, question in tests:
    print("=" * 80)
    print("LANGUAGE:", language)
    print("SOURCE ID:", item["id"])
    print("GOLD ANSWER:", item["answer"])
    print()
    print("QUESTION:")
    print(question)
    print()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": build_prompt(question),
            }
        ],
        temperature=0,
    )

    text = response.choices[0].message.content

    print("MODEL RESPONSE:")
    print(text)
    print()