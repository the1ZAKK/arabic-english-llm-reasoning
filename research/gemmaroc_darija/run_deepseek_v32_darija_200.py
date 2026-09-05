import csv
import json
import os
import re
import time
from decimal import Decimal, InvalidOperation

from openai import OpenAI

MODEL = "deepseek/deepseek-v3.2"
BASE_URL = "https://api.novita.ai/openai"

DATASET = r"research\gemmaroc_darija\dqadqa_gsm8k_matched_200.jsonl"
OUTPUT = r"research\gemmaroc_darija\deepseek_v32_en_darija_200_results.csv"

client = OpenAI(
    api_key=os.environ["NOVITA_API_KEY"],
    base_url=BASE_URL,
)

FIELDNAMES = [
    "problem_id",
    "source_id",
    "language",
    "model",
    "question",
    "gold_answer",
    "response",
    "extracted_answer",
    "is_correct",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "status",
    "error",
]


def load_dataset():
    rows = []

    with open(DATASET, "r", encoding="utf-8-sig") as f:
        for i, line in enumerate(f, start=1):
            if not line.strip():
                continue

            item = json.loads(line)

            rows.append(
                {
                    "problem_id": i,
                    "source_id": item.get("source_id", ""),
                    "question_en": item["question_en"],
                    "question_darija": item["question_darija"],
                    "answer": item["answer"],
                }
            )

    if len(rows) != 200:
        raise RuntimeError(
            f"Expected exactly 200 matched problems, found {len(rows)}."
        )

    return rows


def normalize_number(value):
    if value is None:
        return None

    s = str(value).strip()
    s = s.replace(",", "")
    s = s.replace("$", "")
    s = s.replace("€", "")
    s = s.replace("£", "")
    s = s.replace("%", "")

    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def extract_final_answer(text):
    if not text:
        return None

    # Prefer the explicitly requested FINAL ANSWER format.
    matches = re.findall(
        r"FINAL\s*ANSWER\s*:\s*"
        r"[-+]?(?:\d[\d,]*\.?\d*|\.\d+)",
        text,
        flags=re.IGNORECASE,
    )

    if matches:
        number_matches = re.findall(
            r"[-+]?(?:\d[\d,]*\.?\d*|\.\d+)",
            matches[-1],
        )
        if number_matches:
            return number_matches[-1].replace(",", "")

    # Fallback: use the last numeric expression in the response.
    numbers = re.findall(
        r"[-+]?(?:\d[\d,]*\.?\d*|\.\d+)",
        text,
    )

    if numbers:
        return numbers[-1].replace(",", "")

    return None


def score_answer(extracted, gold):
    pred = normalize_number(extracted)
    target = normalize_number(gold)

    if pred is None or target is None:
        return False

    return pred == target


def build_prompt(question):
    return (
        "Solve the following math problem carefully. "
        "Show your reasoning, then give the final numeric answer in the format:\n"
        "FINAL ANSWER: <number>\n\n"
        f"{question}"
    )


def load_completed():
    completed = set()

    if not os.path.exists(OUTPUT):
        return completed

    with open(OUTPUT, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row.get("status") == "success":
                try:
                    problem_id = int(row["problem_id"])
                    language = row["language"]
                    completed.add((problem_id, language))
                except Exception:
                    pass

    return completed


def append_result(row):
    file_exists = os.path.exists(OUTPUT)

    with open(OUTPUT, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)

        if not file_exists or os.path.getsize(OUTPUT) == 0:
            writer.writeheader()

        writer.writerow(row)


def generate(problem, language):
    if language == "English":
        question = problem["question_en"]
    else:
        question = problem["question_darija"]

    prompt = build_prompt(question)

    print()
    print("=" * 72)
    print(
        f"Problem {problem['problem_id']}/200 | "
        f"{language} | gold={problem['answer']}"
    )
    print("=" * 72)

    try:
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

        extracted = extract_final_answer(text)
        correct = score_answer(extracted, problem["answer"])

        usage = response.usage

        prompt_tokens = (
            usage.prompt_tokens if usage is not None else ""
        )
        completion_tokens = (
            usage.completion_tokens if usage is not None else ""
        )
        total_tokens = (
            usage.total_tokens if usage is not None else ""
        )

        row = {
            "problem_id": problem["problem_id"],
            "source_id": problem["source_id"],
            "language": language,
            "model": MODEL,
            "question": question,
            "gold_answer": problem["answer"],
            "response": text,
            "extracted_answer": extracted if extracted is not None else "",
            "is_correct": int(correct),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "status": "success",
            "error": "",
        }

        append_result(row)

        print("Extracted:", extracted)
        print("Correct:", correct)
        print(
            "Tokens:",
            f"prompt={prompt_tokens}",
            f"completion={completion_tokens}",
            f"total={total_tokens}",
        )

        return True

    except Exception as exc:
        row = {
            "problem_id": problem["problem_id"],
            "source_id": problem["source_id"],
            "language": language,
            "model": MODEL,
            "question": question,
            "gold_answer": problem["answer"],
            "response": "",
            "extracted_answer": "",
            "is_correct": 0,
            "prompt_tokens": "",
            "completion_tokens": "",
            "total_tokens": "",
            "status": "error",
            "error": repr(exc),
        }

        append_result(row)

        print("ERROR:", repr(exc))

        # Brief delay before continuing to the next request.
        time.sleep(2)

        return False


def main():
    problems = load_dataset()
    completed = load_completed()

    print("MODEL:", MODEL)
    print("DATASET:", DATASET)
    print("OUTPUT:", OUTPUT)
    print("Problems:", len(problems))
    print("Successful pairs already completed:", len(completed))
    print("Maximum generations:", len(problems) * 2)
    print()

    for problem in problems:
        pid = problem["problem_id"]

        # Alternate language order to reduce systematic order effects.
        if pid % 2 == 1:
            order = ["English", "Darija"]
        else:
            order = ["Darija", "English"]

        for language in order:
            key = (pid, language)

            if key in completed:
                print(
                    f"SKIP Problem {pid}/200 | {language} "
                    "(already successful)"
                )
                continue

            success = generate(problem, language)

            if success:
                completed.add(key)

            # Small pause between API requests.
            time.sleep(0.25)

    print()
    print("=" * 72)
    print("RUN FINISHED")
    print("=" * 72)
    print("Successful problem-language pairs:", len(completed))
    print("Expected:", 400)
    print("Results saved to:")
    print(OUTPUT)


if __name__ == "__main__":
    main()