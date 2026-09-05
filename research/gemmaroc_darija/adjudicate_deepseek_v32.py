import csv

INPUT = r"research\gemmaroc_darija\deepseek_v32_en_darija_200_results.csv"
OUTPUT = r"research\gemmaroc_darija\deepseek_v32_en_darija_200_adjudicated.csv"
DECISIONS = r"research\gemmaroc_darija\deepseek_v32_review_decisions.csv"

# Conservative adjudication corrections only.
CORRECTIONS = {
    (25, "English"): "$3.50 is equivalent to 350 cents.",
    (141, "English"): "Response correctly derives 0.24 = 24%; automatic extractor captured denominator 25 from 6/25.",
    (141, "Darija"): "0.24 is equivalent to 24%.",
    (169, "Darija"): "22.5 hours is equivalent to 1350 minutes.",
}

rows = []
decision_rows = []

with open(INPUT, "r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)

    for row in reader:
        pid = int(row["problem_id"])
        language = row["language"]

        auto_correct = int(row["is_correct"])

        row["auto_is_correct"] = auto_correct
        row["adjudicated_is_correct"] = auto_correct
        row["adjudication_changed"] = 0
        row["adjudication_reason"] = ""

        key = (pid, language)

        if key in CORRECTIONS:
            row["adjudicated_is_correct"] = 1
            row["adjudication_changed"] = 1
            row["adjudication_reason"] = CORRECTIONS[key]

            decision_rows.append(
                {
                    "problem_id": pid,
                    "language": language,
                    "gold_answer": row["gold_answer"],
                    "extracted_answer": row["extracted_answer"],
                    "auto_is_correct": auto_correct,
                    "adjudicated_is_correct": 1,
                    "reason": CORRECTIONS[key],
                }
            )

        # For downstream compatibility, is_correct becomes final label.
        row["is_correct"] = row["adjudicated_is_correct"]

        rows.append(row)

output_fields = fieldnames + [
    "auto_is_correct",
    "adjudicated_is_correct",
    "adjudication_changed",
    "adjudication_reason",
]

with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=output_fields)
    writer.writeheader()
    writer.writerows(rows)

decision_fields = [
    "problem_id",
    "language",
    "gold_answer",
    "extracted_answer",
    "auto_is_correct",
    "adjudicated_is_correct",
    "reason",
]

with open(DECISIONS, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=decision_fields)
    writer.writeheader()
    writer.writerows(decision_rows)

english = [r for r in rows if r["language"] == "English"]
darija = [r for r in rows if r["language"] == "Darija"]

english_correct = sum(int(r["adjudicated_is_correct"]) for r in english)
darija_correct = sum(int(r["adjudicated_is_correct"]) for r in darija)

changed = sum(int(r["adjudication_changed"]) for r in rows)

print("Changed labels:", changed)
print(f"English: {english_correct}/{len(english)} = {english_correct/len(english):.3%}")
print(f"Darija:  {darija_correct}/{len(darija)} = {darija_correct/len(darija):.3%}")
print(
    "Gap:",
    f"{100 * (english_correct/len(english) - darija_correct/len(darija)):.2f} pp"
)
print()
print("Saved:")
print(OUTPUT)
print(DECISIONS)