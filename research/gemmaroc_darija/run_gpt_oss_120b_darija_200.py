import csv
import json
import os
import re
import time
from pathlib import Path

from openai import OpenAI


MODEL = "openai/gpt-oss-120b"
BASE_URL = "https://api.novita.ai/openai"

DATASET_PATH = Path(
    r"research\gemmaroc_darija\dqadqa_gsm8k_matched_200.jsonl"
)

OUTPUT_PATH = Path(
    r"research\gemmaroc_darija\gpt_oss_120b_en_darija_200_results.csv"
)

TEMPERATURE = 0


FIELDNAMES = [
    "problem_id",
    "source_id",
    "language",
    "gold_answer",
    "extracted_answer",
    "is_correct",
    "extraction_method",
    "question",
    "generated_response",
    "finish_reason",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "status",
    "error",
]


def load_dataset():
    rows = []

    with DATASET_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))

    return rows


def build_prompt(question):
    return (
        "Solve the following math problem carefully. "
        "Show your reasoning, then give the final numeric answer in the format:\n"
        "FINAL ANSWER: <number>\n\n"
        f"Problem:\n{question}"
    )


def normalize_number(text):
    if text is None:
        return None

    text = str(text).strip()
    text = text.replace(",", "")

    try:
        value = float(text)

        if value.is_integer():
            return str(int(value))

        return str(value)

    except Exception:
        return text


def extract_final_answer(response_text):
    if not response_text:
        return None, "none"

    patterns = [
        r"FINAL ANSWER\s*:\s*\$?\s*(-?\d[\d,]*(?:\.\d+)?)",
        r"Final Answer\s*:\s*\$?\s*(-?\d[\d,]*(?:\.\d+)?)",
        r"final answer\s*:\s*\$?\s*(-?\d[\d,]*(?:\.\d+)?)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, response_text, flags=re.IGNORECASE)

        if matches:
            return normalize_number(matches[-1]), "explicit_final"

    numbers = re.findall(
        r"-?\d[\d,]*(?:\.\d+)?",
        response_text
    )

    if numbers:
        return normalize_number(numbers[-1]), "last_number"

    return None, "none"


def answers_match(predicted, gold):
    if predicted is None:
        return False

    try:
        return float(predicted) == float(gold)
    except Exception:
        return str(predicted).strip() == str(gold).strip()


def load_completed_keys():
    completed = set()

    if not OUTPUT_PATH.exists():
        return completed

    with OUTPUT_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:
            if row.get("status") == "success":
                completed.add(
                    (
                        int(row["problem_id"]),
                        row["language"],
                    )
                )

    return completed


def ensure_output_file():
    if OUTPUT_PATH.exists():
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=FIELDNAMES
        )

        writer.writeheader()


def append_result(row):
    with OUTPUT_PATH.open(
        "a",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=FIELDNAMES
        )

        writer.writerow(row)


def make_request(client, prompt):
    return client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=TEMPERATURE,
    )


def main():
    if "NOVITA_API_KEY" not in os.environ:
        raise RuntimeError(
            "NOVITA_API_KEY is not configured."
        )

    client = OpenAI(
        api_key=os.environ["NOVITA_API_KEY"],
        base_url=BASE_URL,
    )

    dataset = load_dataset()

    if len(dataset) != 200:
        raise RuntimeError(
            f"Expected 200 problems, found {len(dataset)}."
        )

    ensure_output_file()
    completed = load_completed_keys()

    print("Model:", MODEL)
    print("Problems:", len(dataset))
    print("Expected total generations:", len(dataset) * 2)
    print("Already completed:", len(completed))
    print()

    request_counter = 0

    for item in dataset:
        problem_id = int(item["problem_id"])
        source_id = item["id"]
        gold_answer = item["answer"]

        if problem_id % 2 == 1:
            language_order = [
                ("english", item["question_en"]),
                ("darija", item["question_darija"]),
            ]
        else:
            language_order = [
                ("darija", item["question_darija"]),
                ("english", item["question_en"]),
            ]

        for language, question in language_order:
            key = (problem_id, language)

            if key in completed:
                print(
                    f"SKIP P{problem_id:03d} {language}"
                )
                continue

            request_counter += 1

            print(
                f"RUN  P{problem_id:03d} "
                f"{language:<7} "
                f"source={source_id}"
            )

            row = {
                "problem_id": problem_id,
                "source_id": source_id,
                "language": language,
                "gold_answer": gold_answer,
                "extracted_answer": "",
                "is_correct": "",
                "extraction_method": "",
                "question": question,
                "generated_response": "",
                "finish_reason": "",
                "prompt_tokens": "",
                "completion_tokens": "",
                "total_tokens": "",
                "status": "error",
                "error": "",
            }

            try:
                prompt = build_prompt(question)

                response = make_request(
                    client,
                    prompt
                )

                choice = response.choices[0]

                generated_text = (
                    choice.message.content or ""
                )

                extracted_answer, extraction_method = (
                    extract_final_answer(
                        generated_text
                    )
                )

                correct = answers_match(
                    extracted_answer,
                    gold_answer
                )

                usage = getattr(
                    response,
                    "usage",
                    None
                )

                prompt_tokens = (
                    getattr(
                        usage,
                        "prompt_tokens",
                        ""
                    )
                    if usage
                    else ""
                )

                completion_tokens = (
                    getattr(
                        usage,
                        "completion_tokens",
                        ""
                    )
                    if usage
                    else ""
                )

                total_tokens = (
                    getattr(
                        usage,
                        "total_tokens",
                        ""
                    )
                    if usage
                    else ""
                )

                row.update(
                    {
                        "extracted_answer": (
                            extracted_answer
                            if extracted_answer is not None
                            else ""
                        ),
                        "is_correct": (
                            1 if correct else 0
                        ),
                        "extraction_method": extraction_method,
                        "generated_response": generated_text,
                        "finish_reason": (
                            getattr(
                                choice,
                                "finish_reason",
                                ""
                            )
                            or ""
                        ),
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                        "status": "success",
                        "error": "",
                    }
                )

                print(
                    f"     answer={extracted_answer} "
                    f"gold={gold_answer} "
                    f"correct={correct}"
                )

            except Exception as e:
                row["error"] = repr(e)

                print(
                    "     ERROR:",
                    repr(e)
                )

            append_result(row)

            time.sleep(0.25)

    print()
    print("DONE")
    print("Results saved to:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()