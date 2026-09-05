import csv
import math
import random
from pathlib import Path


INPUT_PATH = Path(
    r"research\gemmaroc_darija\gpt_oss_120b_en_darija_200_adjudicated.csv"
)

STRICT_EXCLUSIONS = {21, 26, 128, 185}

BOOTSTRAP_SAMPLES = 100000
BOOTSTRAP_SEED = 42


def exact_mcnemar(b, c):
    """
    Exact two-sided McNemar test.

    b = English correct, Darija wrong
    c = English wrong, Darija correct
    """
    n = b + c

    if n == 0:
        return 1.0

    k = min(b, c)

    tail = sum(
        math.comb(n, i)
        for i in range(k + 1)
    ) / (2 ** n)

    return min(1.0, 2 * tail)


def percentile(values, p):
    values = sorted(values)

    index = (len(values) - 1) * p
    lower = math.floor(index)
    upper = math.ceil(index)

    if lower == upper:
        return values[lower]

    weight = index - lower

    return (
        values[lower] * (1 - weight)
        + values[upper] * weight
    )


def analyze(pairs, label):
    n = len(pairs)

    english_correct = sum(
        p["english"] for p in pairs
    )

    darija_correct = sum(
        p["darija"] for p in pairs
    )

    both_correct = sum(
        1 for p in pairs
        if p["english"] == 1
        and p["darija"] == 1
    )

    both_wrong = sum(
        1 for p in pairs
        if p["english"] == 0
        and p["darija"] == 0
    )

    english_only = sum(
        1 for p in pairs
        if p["english"] == 1
        and p["darija"] == 0
    )

    darija_only = sum(
        1 for p in pairs
        if p["english"] == 0
        and p["darija"] == 1
    )

    english_accuracy = english_correct / n
    darija_accuracy = darija_correct / n

    gap = english_accuracy - darija_accuracy

    p_value = exact_mcnemar(
        english_only,
        darija_only
    )

    rng = random.Random(BOOTSTRAP_SEED)

    bootstrap_gaps = []

    for _ in range(BOOTSTRAP_SAMPLES):
        sample = [
            pairs[rng.randrange(n)]
            for _ in range(n)
        ]

        en = sum(
            p["english"] for p in sample
        ) / n

        da = sum(
            p["darija"] for p in sample
        ) / n

        bootstrap_gaps.append(en - da)

    ci_low = percentile(
        bootstrap_gaps,
        0.025
    )

    ci_high = percentile(
        bootstrap_gaps,
        0.975
    )

    print("=" * 60)
    print(label)
    print("=" * 60)
    print("N:", n)

    print(
        f"English: {english_correct}/{n} "
        f"= {english_accuracy:.3%}"
    )

    print(
        f"Darija:  {darija_correct}/{n} "
        f"= {darija_accuracy:.3%}"
    )

    print(
        f"Gap: {(gap * 100):.2f} pp"
    )

    print()
    print("Paired outcomes:")
    print("Both correct:", both_correct)
    print("Both wrong:", both_wrong)
    print("English only:", english_only)
    print("Darija only:", darija_only)
    print(
        "Discordant:",
        english_only + darija_only
    )

    print()
    print(
        f"Exact McNemar p = {p_value:.10f}"
    )

    print(
        "Paired bootstrap 95% CI: "
        f"[{ci_low * 100:.2f}, "
        f"{ci_high * 100:.2f}] pp"
    )

    print()


def main():
    with INPUT_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        rows = list(csv.DictReader(f))

    if len(rows) != 400:
        raise RuntimeError(
            f"Expected 400 rows, found {len(rows)}."
        )

    by_problem = {}

    for row in rows:
        problem_id = int(row["problem_id"])
        language = row["language"].lower()

        correct = int(
            row["adjudicated_is_correct"]
        )

        by_problem.setdefault(
            problem_id,
            {}
        )[language] = correct

    pairs = []

    for problem_id in sorted(by_problem):
        item = by_problem[problem_id]

        if "english" not in item:
            raise RuntimeError(
                f"P{problem_id} missing English."
            )

        if "darija" not in item:
            raise RuntimeError(
                f"P{problem_id} missing Darija."
            )

        pairs.append({
            "problem_id": problem_id,
            "english": item["english"],
            "darija": item["darija"],
        })

    if len(pairs) != 200:
        raise RuntimeError(
            f"Expected 200 paired problems, "
            f"found {len(pairs)}."
        )

    analyze(
        pairs,
        "ALL_200"
    )

    strict_pairs = [
        p for p in pairs
        if p["problem_id"]
        not in STRICT_EXCLUSIONS
    ]

    analyze(
        strict_pairs,
        "STRICT_QC_196"
    )


if __name__ == "__main__":
    main()