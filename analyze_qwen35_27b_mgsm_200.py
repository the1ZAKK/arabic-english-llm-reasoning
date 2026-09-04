import pandas as pd
import numpy as np
from pathlib import Path
from math import comb

INPUT_FILE = Path("qwen35_27b_mgsm_200_results.csv")

ADJUDICATED_FILE = Path("qwen35_27b_mgsm_200_adjudicated.csv")
REVIEW_DECISIONS_FILE = Path("qwen35_27b_mgsm_200_review_decisions.csv")
PAIRED_FILE = Path("qwen35_27b_mgsm_200_paired_results.csv")
SUMMARY_FILE = Path("qwen35_27b_mgsm_200_statistical_summary.csv")
ROBUSTNESS_FILE = Path("qwen35_27b_mgsm_200_robustness_summary.csv")

# ------------------------------------------------------------------
# Manual adjudication of the 17 flagged rows.
#
# Rule:
# Correct only when the model clearly derives/reaches the gold answer
# as its solution. Parser/truncation artifacts can be overridden when
# the reasoning clearly establishes the correct answer.
# ------------------------------------------------------------------

MANUAL_DECISIONS = {
    (4, "english"): True,
    (4, "arabic"): True,
    (29, "english"): True,
    (43, "english"): False,
    (56, "english"): True,
    (57, "english"): True,
    (61, "english"): True,
    (77, "arabic"): True,
    (85, "english"): True,
    (85, "arabic"): True,
    (88, "english"): True,
    (88, "arabic"): True,
    (107, "english"): True,
    (108, "english"): True,
    (165, "english"): True,
    (176, "arabic"): True,
    (177, "english"): True,
}

MANUAL_NOTES = {
    (4, "english"): "Reasoning clearly derives 180 - 135 = 45 before truncation.",
    (4, "arabic"): "Reasoning clearly derives the gold answer 45 before truncation.",
    (29, "english"): "Reasoning clearly reaches the gold answer 25000.",
    (43, "english"): (
        "Model interprets a 10% speed increase literally and obtains about "
        "36.36 seconds rather than benchmark gold 36; retain as incorrect "
        "for primary benchmark scoring. This item is excluded in strict QC."
    ),
    (56, "english"): "Reasoning clearly reaches the gold answer 70.",
    (57, "english"): "Reasoning clearly reaches the gold answer 400.",
    (61, "english"): "Reasoning derives Steve=36, Tim=40, hence waiting time 4.",
    (77, "arabic"): "Reasoning clearly reaches the gold answer 5.",
    (85, "english"): "Reasoning clearly derives required sixth score 98.",
    (85, "arabic"): "Reasoning clearly derives required sixth score 98.",
    (88, "english"): "Reasoning derives and verifies the gold answer 8 gallons.",
    (88, "arabic"): "Reasoning clearly reaches the gold answer 8.",
    (107, "english"): "Reasoning clearly reaches the gold answer 18.",
    (108, "english"): "Reasoning clearly reaches the gold answer 60.",
    (165, "english"): (
        "Visible answer field is empty, but API reasoning_content computes "
        "60 cookies, $6 cost, and $4 change."
    ),
    (176, "arabic"): "Reasoning works through the ages and reaches 23.",
    (177, "english"): "Reasoning clearly reaches the gold answer 25.",
}

# Existing benchmark QC exclusions established before this model analysis.
SEMANTIC_MISMATCH = {51, 100, 189, 197}
AMBIGUOUS_TRANSLATION = {55, 166, 171, 175, 192}
AMBIGUOUS_SOURCE = {43, 86, 122, 150, 163}

STRICT_QC_EXCLUSIONS = (
    SEMANTIC_MISMATCH
    | AMBIGUOUS_TRANSLATION
    | AMBIGUOUS_SOURCE
)

EXPECTED_STRICT_QC_EXCLUSIONS = {
    43, 51, 55, 86, 100, 122, 150,
    163, 166, 171, 175, 189, 192, 197
}

assert STRICT_QC_EXCLUSIONS == EXPECTED_STRICT_QC_EXCLUSIONS


def exact_mcnemar_p(b, c):
    """
    Exact two-sided McNemar/binomial test.
    b = English correct, Arabic wrong
    c = Arabic correct, English wrong
    """
    n = b + c

    if n == 0:
        return 1.0

    k = min(b, c)

    lower_tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)

    return min(1.0, 2.0 * lower_tail)


def paired_bootstrap_ci(paired_df, n_boot=100000, seed=42):
    """
    Bootstrap the paired English-minus-Arabic accuracy difference.
    """
    en = paired_df["english_correct"].to_numpy(dtype=float)
    ar = paired_df["arabic_correct"].to_numpy(dtype=float)

    differences = en - ar

    rng = np.random.default_rng(seed)

    # Chunking avoids allocating an unnecessarily large matrix.
    boot_means = np.empty(n_boot, dtype=float)

    chunk_size = 5000
    position = 0

    while position < n_boot:
        current = min(chunk_size, n_boot - position)

        indices = rng.integers(
            0,
            len(differences),
            size=(current, len(differences))
        )

        boot_means[position:position + current] = (
            differences[indices].mean(axis=1)
        )

        position += current

    low, high = np.percentile(boot_means, [2.5, 97.5])

    return float(low), float(high)


def build_paired(df):
    en = (
        df[df["language"] == "english"]
        .set_index("problem_id")["final_correct"]
        .astype(int)
    )

    ar = (
        df[df["language"] == "arabic"]
        .set_index("problem_id")["final_correct"]
        .astype(int)
    )

    common_ids = sorted(set(en.index) & set(ar.index))

    paired = pd.DataFrame({
        "problem_id": common_ids,
        "english_correct": [int(en.loc[i]) for i in common_ids],
        "arabic_correct": [int(ar.loc[i]) for i in common_ids],
    })

    paired["difference"] = (
        paired["english_correct"] - paired["arabic_correct"]
    )

    return paired


def analyze_subset(df, subset_name):
    paired = build_paired(df)

    n = len(paired)

    en_correct = int(paired["english_correct"].sum())
    ar_correct = int(paired["arabic_correct"].sum())

    en_acc = en_correct / n
    ar_acc = ar_correct / n
    gap = en_acc - ar_acc

    both_correct = int(
        (
            (paired["english_correct"] == 1)
            & (paired["arabic_correct"] == 1)
        ).sum()
    )

    both_wrong = int(
        (
            (paired["english_correct"] == 0)
            & (paired["arabic_correct"] == 0)
        ).sum()
    )

    english_only = int(
        (
            (paired["english_correct"] == 1)
            & (paired["arabic_correct"] == 0)
        ).sum()
    )

    arabic_only = int(
        (
            (paired["english_correct"] == 0)
            & (paired["arabic_correct"] == 1)
        ).sum()
    )

    p_value = exact_mcnemar_p(english_only, arabic_only)

    ci_low, ci_high = paired_bootstrap_ci(paired)

    return {
        "subset": subset_name,
        "n_problems": n,
        "arabic_correct": ar_correct,
        "arabic_accuracy": ar_acc,
        "english_correct": en_correct,
        "english_accuracy": en_acc,
        "english_minus_arabic_gap": gap,
        "gap_percentage_points": gap * 100,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "english_only": english_only,
        "arabic_only": arabic_only,
        "discordant_pairs": english_only + arabic_only,
        "mcnemar_exact_two_sided_p": p_value,
        "bootstrap_95_ci_low": ci_low,
        "bootstrap_95_ci_high": ci_high,
    }


# ------------------------------------------------------------------
# Load and validate
# ------------------------------------------------------------------

df = pd.read_csv(INPUT_FILE)

print("=" * 72)
print("QWEN3.5-27B MGSM-200 FINAL ANALYSIS")
print("=" * 72)

print(f"Rows loaded: {len(df)}")

if len(df) != 400:
    raise ValueError(f"Expected 400 rows, found {len(df)}")

if "status" in df.columns:
    print("\nStatus:")
    print(df["status"].value_counts(dropna=False))

    bad_status = df[df["status"] != "success"]

    if len(bad_status) > 0:
        print("\nERROR: Not all API evaluations succeeded.")
        print(
            bad_status[
                ["problem_id", "language", "status", "error"]
            ].to_string(index=False)
        )
        raise RuntimeError(
            "Resolve failed API rows before final statistical analysis."
        )

if df.duplicated(["problem_id", "language"]).any():
    duplicates = df[
        df.duplicated(["problem_id", "language"], keep=False)
    ].sort_values(["problem_id", "language"])

    print("\nDuplicate problem/language rows:")
    print(
        duplicates[
            ["problem_id", "language", "status"]
        ].to_string(index=False)
    )

    raise RuntimeError("Duplicate problem/language rows detected.")

expected_ids = set(range(1, 201))
actual_ids = set(df["problem_id"].astype(int))

if actual_ids != expected_ids:
    raise RuntimeError(
        f"Problem IDs are not exactly 1..200. "
        f"Missing={sorted(expected_ids - actual_ids)}, "
        f"Unexpected={sorted(actual_ids - expected_ids)}"
    )

language_counts = df["language"].value_counts()

print("\nLanguage counts:")
print(language_counts)

if language_counts.get("english", 0) != 200:
    raise RuntimeError("Expected exactly 200 English rows.")

if language_counts.get("arabic", 0) != 200:
    raise RuntimeError("Expected exactly 200 Arabic rows.")


# ------------------------------------------------------------------
# Automatic score -> final adjudicated score
# ------------------------------------------------------------------

df["automatic_correct"] = (
    pd.to_numeric(df["is_correct"], errors="coerce")
    .fillna(0)
    .astype(int)
)

df["final_correct"] = df["automatic_correct"].copy()
df["manual_adjudicated"] = 0
df["manual_note"] = ""

review_records = []

for (problem_id, language), decision in MANUAL_DECISIONS.items():
    mask = (
        (df["problem_id"].astype(int) == problem_id)
        & (df["language"] == language)
    )

    matches = int(mask.sum())

    if matches != 1:
        raise RuntimeError(
            f"Expected exactly one row for "
            f"P{problem_id} {language}, found {matches}"
        )

    automatic = int(df.loc[mask, "automatic_correct"].iloc[0])

    df.loc[mask, "final_correct"] = int(decision)
    df.loc[mask, "manual_adjudicated"] = 1
    df.loc[mask, "manual_note"] = MANUAL_NOTES[(problem_id, language)]

    review_records.append({
        "problem_id": problem_id,
        "language": language,
        "automatic_correct": automatic,
        "manual_correct": int(decision),
        "score_changed": int(automatic != int(decision)),
        "note": MANUAL_NOTES[(problem_id, language)],
    })


review_df = pd.DataFrame(review_records).sort_values(
    ["problem_id", "language"]
)

df = df.sort_values(["problem_id", "language"]).reset_index(drop=True)

df.to_csv(ADJUDICATED_FILE, index=False)
review_df.to_csv(REVIEW_DECISIONS_FILE, index=False)


# ------------------------------------------------------------------
# Primary ALL_200 analysis
# ------------------------------------------------------------------

paired_all = build_paired(df)

if len(paired_all) != 200:
    raise RuntimeError(
        f"Expected 200 paired problems, found {len(paired_all)}"
    )

paired_all.to_csv(PAIRED_FILE, index=False)

all_result = analyze_subset(df, "ALL_200")

summary_df = pd.DataFrame([all_result])
summary_df.to_csv(SUMMARY_FILE, index=False)


# ------------------------------------------------------------------
# Robustness analysis
# ------------------------------------------------------------------

def exclude_ids(frame, ids):
    return frame[~frame["problem_id"].isin(ids)].copy()


robustness_results = []

robustness_results.append(
    analyze_subset(df, "ALL_200")
)

definite_matched_df = exclude_ids(
    df,
    SEMANTIC_MISMATCH
)

robustness_results.append(
    analyze_subset(
        definite_matched_df,
        "DEFINITE_MATCHED_196"
    )
)

translation_clean_df = exclude_ids(
    df,
    SEMANTIC_MISMATCH | AMBIGUOUS_TRANSLATION
)

robustness_results.append(
    analyze_subset(
        translation_clean_df,
        "TRANSLATION_CLEAN_191"
    )
)

strict_qc_df = exclude_ids(
    df,
    STRICT_QC_EXCLUSIONS
)

robustness_results.append(
    analyze_subset(
        strict_qc_df,
        "STRICT_QC_186"
    )
)

robustness_df = pd.DataFrame(robustness_results)
robustness_df.to_csv(ROBUSTNESS_FILE, index=False)


# ------------------------------------------------------------------
# Reporting
# ------------------------------------------------------------------

changed = review_df[review_df["score_changed"] == 1]

print("\n" + "=" * 72)
print("MANUAL ADJUDICATION")
print("=" * 72)

print(f"Manually reviewed rows: {len(review_df)}")
print(f"Manual correct: {int(review_df['manual_correct'].sum())}")
print(
    f"Manual incorrect: "
    f"{len(review_df) - int(review_df['manual_correct'].sum())}"
)
print(f"Automatic scores changed: {len(changed)}")

if len(changed):
    print("\nRows whose score changed:")
    print(
        changed[
            [
                "problem_id",
                "language",
                "automatic_correct",
                "manual_correct"
            ]
        ].to_string(index=False)
    )


print("\n" + "=" * 72)
print("FINAL ALL-200 RESULT")
print("=" * 72)

r = all_result

print(
    f"Arabic:  {r['arabic_correct']}/{r['n_problems']} "
    f"= {r['arabic_accuracy']:.4f} "
    f"({r['arabic_accuracy'] * 100:.2f}%)"
)

print(
    f"English: {r['english_correct']}/{r['n_problems']} "
    f"= {r['english_accuracy']:.4f} "
    f"({r['english_accuracy'] * 100:.2f}%)"
)

print(
    f"English - Arabic gap: "
    f"{r['english_minus_arabic_gap']:+.4f} "
    f"({r['gap_percentage_points']:+.2f} pp)"
)

print("\nPaired outcomes:")
print(f"  Both correct:  {r['both_correct']}")
print(f"  Both wrong:    {r['both_wrong']}")
print(f"  English only:  {r['english_only']}")
print(f"  Arabic only:   {r['arabic_only']}")
print(f"  Discordant:    {r['discordant_pairs']}")

print(
    f"\nExact two-sided McNemar p: "
    f"{r['mcnemar_exact_two_sided_p']:.12g}"
)

print(
    f"Paired bootstrap 95% CI for English-Arabic gap: "
    f"[{r['bootstrap_95_ci_low']:.4f}, "
    f"{r['bootstrap_95_ci_high']:.4f}]"
)


print("\n" + "=" * 72)
print("ROBUSTNESS")
print("=" * 72)

for _, row in robustness_df.iterrows():
    print(
        f"{row['subset']}: "
        f"N={int(row['n_problems'])}, "
        f"AR={row['arabic_accuracy'] * 100:.2f}%, "
        f"EN={row['english_accuracy'] * 100:.2f}%, "
        f"gap={row['gap_percentage_points']:+.2f} pp, "
        f"95% CI=["
        f"{row['bootstrap_95_ci_low'] * 100:.2f}, "
        f"{row['bootstrap_95_ci_high'] * 100:.2f}] pp, "
        f"McNemar p={row['mcnemar_exact_two_sided_p']:.6g}"
    )


print("\n" + "=" * 72)
print("OUTPUT FILES")
print("=" * 72)

for path in [
    ADJUDICATED_FILE,
    REVIEW_DECISIONS_FILE,
    PAIRED_FILE,
    SUMMARY_FILE,
    ROBUSTNESS_FILE,
]:
    print(path)

print("\nAnalysis complete.")