import csv
from pathlib import Path


INPUT_PATH = Path(
    r"research\gemmaroc_darija\gpt_oss_120b_en_darija_200_results.csv"
)

OUTPUT_PATH = Path(
    r"research\gemmaroc_darija\gpt_oss_120b_en_darija_200_adjudicated.csv"
)

DECISIONS_PATH = Path(
    r"research\gemmaroc_darija\gpt_oss_120b_review_decisions.csv"
)


# Conservative manual corrections only.
# Key = (problem_id, language)
# value = adjudicated correctness
CORRECTIONS = {
    (25, "english"): 1,   # $3.50 == 350 cents
    (141, "english"): 1,  # 0.24 == 24%
    (141, "darija"): 1,   # 0.24 == 24%
}


REASONS = {
    (25, "english"): "Equivalent representation: $3.50 equals 350 cents.",
    (141, "english"): "Equivalent representation: 0.24 equals 24 percent.",
    (141, "darija"): "Equivalent representation: 0.24 equals 24 percent.",
}


def main():
    with INPUT_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames)

    if len(rows) != 400:
        raise RuntimeError(
            f"Expected 400 rows, found {len(rows)}."
        )

    # Add adjudication fields without destroying the original automatic score.
    output_fieldnames = fieldnames + [
        "auto_is_correct",
        "adjudicated_is_correct",
        "adjudication_changed",
        "adjudication_reason",
    ]

    review_rows = []

    changed_count = 0

    for row in rows:
        problem_id = int(row["problem_id"])
        language = row["language"].strip().lower()

        auto_correct = int(row["is_correct"])
        adjudicated_correct = auto_correct

        key = (problem_id, language)

        reason = ""

        if key in CORRECTIONS:
            adjudicated_correct = CORRECTIONS[key]
            reason = REASONS[key]

        changed = int(
            adjudicated_correct != auto_correct
        )

        if changed:
            changed_count += 1

        row["auto_is_correct"] = auto_correct
        row["adjudicated_is_correct"] = adjudicated_correct
        row["adjudication_changed"] = changed
        row["adjudication_reason"] = reason

        # Keep is_correct aligned with the final adjudicated label
        # so downstream analysis scripts can use the same column name.
        row["is_correct"] = adjudicated_correct

        if key in CORRECTIONS:
            review_rows.append({
                "problem_id": problem_id,
                "language": language,
                "gold_answer": row["gold_answer"],
                "extracted_answer": row["extracted_answer"],
                "auto_is_correct": auto_correct,
                "adjudicated_is_correct": adjudicated_correct,
                "reason": reason,
            })

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=output_fieldnames
        )
        writer.writeheader()
        writer.writerows(rows)

    with DECISIONS_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "problem_id",
                "language",
                "gold_answer",
                "extracted_answer",
                "auto_is_correct",
                "adjudicated_is_correct",
                "reason",
            ]
        )
        writer.writeheader()
        writer.writerows(review_rows)

    english = [
        r for r in rows
        if r["language"].lower() == "english"
    ]

    darija = [
        r for r in rows
        if r["language"].lower() == "darija"
    ]

    english_correct = sum(
        int(r["adjudicated_is_correct"])
        for r in english
    )

    darija_correct = sum(
        int(r["adjudicated_is_correct"])
        for r in darija
    )

    print("Adjudication complete")
    print("Changed labels:", changed_count)
    print()
    print(
        f"English: {english_correct}/{len(english)} "
        f"= {english_correct / len(english):.3%}"
    )
    print(
        f"Darija:  {darija_correct}/{len(darija)} "
        f"= {darija_correct / len(darija):.3%}"
    )

    gap = (
        english_correct / len(english)
        - darija_correct / len(darija)
    )

    print(f"Gap: {gap * 100:.2f} percentage points")
    print()
    print("Saved adjudicated results:")
    print(OUTPUT_PATH)
    print()
    print("Saved review decisions:")
    print(DECISIONS_PATH)


if __name__ == "__main__":
    main()