import csv
import math
import random
from collections import defaultdict

INPUT = r"research\gemmaroc_darija\deepseek_v32_en_darija_200_adjudicated.csv"
SUMMARY = r"research\gemmaroc_darija\deepseek_v32_statistical_summary.csv"

STRICT_EXCLUSIONS = {21, 26, 128, 185}
BOOTSTRAP_SAMPLES = 100_000
SEED = 42


def load_pairs():
    by_problem = defaultdict(dict)

    with open(INPUT, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            pid = int(row["problem_id"])
            language = row["language"]
            correct = int(row["adjudicated_is_correct"])

            by_problem[pid][language] = correct

    pairs = []

    for pid in sorted(by_problem):
        langs = by_problem[pid]

        if "English" not in langs or "Darija" not in langs:
            raise RuntimeError(f"Missing language for problem {pid}")

        pairs.append(
            {
                "problem_id": pid,
                "English": langs["English"],
                "Darija": langs["Darija"],
            }
        )

    return pairs


def exact_mcnemar_p(b, c):
    n = b + c

    if n == 0:
        return 1.0

    k = min(b, c)

    tail = 0.0

    for i in range(k + 1):
        tail += math.comb(n, i) * (0.5 ** n)

    p = min(1.0, 2.0 * tail)
    return p


def percentile(sorted_values, q):
    if not sorted_values:
        raise ValueError("Empty values")

    pos = (len(sorted_values) - 1) * q
    lower = int(math.floor(pos))
    upper = int(math.ceil(pos))

    if lower == upper:
        return sorted_values[lower]

    frac = pos - lower

    return (
        sorted_values[lower] * (1 - frac)
        + sorted_values[upper] * frac
    )


def paired_bootstrap_gap_ci(pairs, samples=BOOTSTRAP_SAMPLES, seed=SEED):
    rng = random.Random(seed)
    n = len(pairs)

    differences = [
        p["English"] - p["Darija"]
        for p in pairs
    ]

    boot = []

    for _ in range(samples):
        total = 0

        for _ in range(n):
            total += differences[rng.randrange(n)]

        gap_pp = 100.0 * total / n
        boot.append(gap_pp)

    boot.sort()

    low = percentile(boot, 0.025)
    high = percentile(boot, 0.975)

    return low, high


def analyze_subset(name, pairs):
    n = len(pairs)

    english_correct = sum(p["English"] for p in pairs)
    darija_correct = sum(p["Darija"] for p in pairs)

    both_correct = sum(
        1
        for p in pairs
        if p["English"] == 1 and p["Darija"] == 1
    )

    both_wrong = sum(
        1
        for p in pairs
        if p["English"] == 0 and p["Darija"] == 0
    )

    english_only = sum(
        1
        for p in pairs
        if p["English"] == 1 and p["Darija"] == 0
    )

    darija_only = sum(
        1
        for p in pairs
        if p["English"] == 0 and p["Darija"] == 1
    )

    discordant = english_only + darija_only

    english_acc = english_correct / n
    darija_acc = darija_correct / n
    gap_pp = 100.0 * (english_acc - darija_acc)

    p_value = exact_mcnemar_p(
        english_only,
        darija_only,
    )

    ci_low, ci_high = paired_bootstrap_gap_ci(pairs)

    result = {
        "subset": name,
        "n": n,
        "english_correct": english_correct,
        "english_accuracy": english_acc,
        "darija_correct": darija_correct,
        "darija_accuracy": darija_acc,
        "gap_pp": gap_pp,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "english_only": english_only,
        "darija_only": darija_only,
        "discordant": discordant,
        "mcnemar_p": p_value,
        "bootstrap_ci_low_pp": ci_low,
        "bootstrap_ci_high_pp": ci_high,
    }

    return result


def print_result(r):
    print()
    print("=" * 72)
    print(r["subset"])
    print("=" * 72)

    print("N:", r["n"])

    print(
        f"English: {r['english_correct']}/{r['n']} "
        f"= {100*r['english_accuracy']:.3f}%"
    )

    print(
        f"Darija:  {r['darija_correct']}/{r['n']} "
        f"= {100*r['darija_accuracy']:.3f}%"
    )

    print(f"Gap: {r['gap_pp']:.2f} pp")

    print()
    print("Paired outcomes:")
    print("Both correct:", r["both_correct"])
    print("Both wrong:", r["both_wrong"])
    print("English only:", r["english_only"])
    print("Darija only:", r["darija_only"])
    print("Discordant:", r["discordant"])

    print()
    print(f"Exact McNemar p: {r['mcnemar_p']:.10f}")

    print(
        "Paired bootstrap 95% CI:",
        f"[{r['bootstrap_ci_low_pp']:.2f}, "
        f"{r['bootstrap_ci_high_pp']:.2f}] pp"
    )


def save_summary(results):
    fields = [
        "subset",
        "n",
        "english_correct",
        "english_accuracy",
        "darija_correct",
        "darija_accuracy",
        "gap_pp",
        "both_correct",
        "both_wrong",
        "english_only",
        "darija_only",
        "discordant",
        "mcnemar_p",
        "bootstrap_ci_low_pp",
        "bootstrap_ci_high_pp",
    ]

    with open(
        SUMMARY,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)


def main():
    all_pairs = load_pairs()

    if len(all_pairs) != 200:
        raise RuntimeError(
            f"Expected 200 matched problems, found {len(all_pairs)}"
        )

    strict_pairs = [
        p
        for p in all_pairs
        if p["problem_id"] not in STRICT_EXCLUSIONS
    ]

    all_result = analyze_subset(
        "ALL_200",
        all_pairs,
    )

    strict_result = analyze_subset(
        "STRICT_QC_196",
        strict_pairs,
    )

    print_result(all_result)
    print_result(strict_result)

    save_summary(
        [
            all_result,
            strict_result,
        ]
    )

    print()
    print("Saved summary:")
    print(SUMMARY)


if __name__ == "__main__":
    main()