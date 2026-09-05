import csv
import math
import random

INPUT_FILE = "gemmaroc_en_darija_200_adjudicated.csv"
STRICT_EXCLUSIONS = {21, 26, 128, 185}

BOOTSTRAP_SAMPLES = 100_000
SEED = 42


def load_results(path):
    results = {}

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            problem_id = int(row["problem_id"])
            language = row["language"].strip().lower()
            correct = int(row["adjudicated_correct"])

            if problem_id not in results:
                results[problem_id] = {}

            results[problem_id][language] = correct

    return results


def exact_mcnemar(english_only, darija_only):
    n = english_only + darija_only

    if n == 0:
        return 1.0

    k = min(english_only, darija_only)

    probability = sum(
        math.comb(n, i) * (0.5 ** n)
        for i in range(k + 1)
    )

    return min(1.0, 2 * probability)


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


def paired_bootstrap(pairs):
    rng = random.Random(SEED)
    n = len(pairs)

    gaps = []

    for _ in range(BOOTSTRAP_SAMPLES):
        difference = 0

        for _ in range(n):
            english, darija = pairs[rng.randrange(n)]
            difference += english - darija

        gaps.append(difference / n)

    return (
        percentile(gaps, 0.025),
        percentile(gaps, 0.975),
    )


def analyze(results, excluded=None):
    excluded = excluded or set()

    pairs = []

    for problem_id in sorted(results):
        if problem_id in excluded:
            continue

        item = results[problem_id]

        if "english" not in item or "darija" not in item:
            raise ValueError(
                f"Problem {problem_id} does not contain both languages."
            )

        pairs.append(
            (item["english"], item["darija"])
        )

    n = len(pairs)

    english_correct = sum(x[0] for x in pairs)
    darija_correct = sum(x[1] for x in pairs)

    both_correct = sum(
        1 for en, da in pairs if en == 1 and da == 1
    )

    both_wrong = sum(
        1 for en, da in pairs if en == 0 and da == 0
    )

    english_only = sum(
        1 for en, da in pairs if en == 1 and da == 0
    )

    darija_only = sum(
        1 for en, da in pairs if en == 0 and da == 1
    )

    english_accuracy = english_correct / n
    darija_accuracy = darija_correct / n
    gap = english_accuracy - darija_accuracy

    p_value = exact_mcnemar(
        english_only,
        darija_only,
    )

    ci_low, ci_high = paired_bootstrap(pairs)

    return {
        "n": n,
        "english_correct": english_correct,
        "darija_correct": darija_correct,
        "english_accuracy": english_accuracy,
        "darija_accuracy": darija_accuracy,
        "gap": gap,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "english_only": english_only,
        "darija_only": darija_only,
        "discordant": english_only + darija_only,
        "mcnemar_p": p_value,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


def print_results(name, r):
    print()
    print("=" * 60)
    print(name)
    print("=" * 60)

    print(f"N: {r['n']}")

    print(
        f"English: {r['english_correct']}/{r['n']} "
        f"= {r['english_accuracy']:.3%}"
    )

    print(
        f"Darija:  {r['darija_correct']}/{r['n']} "
        f"= {r['darija_accuracy']:.3%}"
    )

    print(
        f"English - Darija gap: "
        f"{r['gap'] * 100:.2f} percentage points"
    )

    print()
    print("Paired outcomes:")
    print(f"  Both correct:        {r['both_correct']}")
    print(f"  Both wrong:          {r['both_wrong']}")
    print(f"  English-only:        {r['english_only']}")
    print(f"  Darija-only:         {r['darija_only']}")
    print(f"  Discordant pairs:    {r['discordant']}")

    print()
    print(
        f"Exact McNemar p-value: "
        f"{r['mcnemar_p']:.10f}"
    )

    print(
        "Paired bootstrap 95% CI: "
        f"[{r['ci_low'] * 100:.2f}, "
        f"{r['ci_high'] * 100:.2f}] percentage points"
    )


def main():
    results = load_results(INPUT_FILE)

    all_results = analyze(results)

    strict_results = analyze(
        results,
        excluded=STRICT_EXCLUSIONS,
    )

    print_results("ALL_200", all_results)
    print_results("STRICT_QC_196", strict_results)


if __name__ == "__main__":
    main()