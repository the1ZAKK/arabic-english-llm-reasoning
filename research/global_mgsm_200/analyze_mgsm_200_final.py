import numpy as np
import pandas as pd
from scipy import stats


# ============================================================
# CONFIG
# ============================================================

GEMMA_FILES = [
    "gemma_mgsm_100_adjudicated.csv",
    "gemma_mgsm_101_200_adjudicated.csv",
]

QWEN_FILES = [
    "qwen_mgsm_100_adjudicated.csv",
    "qwen_mgsm_101_200_adjudicated.csv",
]


BOOTSTRAP_SAMPLES = 10000
RANDOMIZATION_SAMPLES = 100000
SEED = 42


# ============================================================
# OUTPUT FILES
# ============================================================

GEMMA_COMBINED_FILE = (
    "gemma_mgsm_200_adjudicated.csv"
)

QWEN_COMBINED_FILE = (
    "qwen_mgsm_200_adjudicated.csv"
)

GEMMA_PAIRED_FILE = (
    "gemma_mgsm_200_paired_results.csv"
)

QWEN_PAIRED_FILE = (
    "qwen_mgsm_200_paired_results.csv"
)

MODEL_SUMMARY_FILE = (
    "mgsm_200_model_summary.csv"
)

CROSS_PROBLEM_FILE = (
    "mgsm_200_cross_model_problem_analysis.csv"
)

CROSS_SUMMARY_FILE = (
    "mgsm_200_cross_model_summary.csv"
)


# ============================================================
# HELPERS
# ============================================================

def find_final_score_column(df):

    candidates = [
        "manual_is_correct",
        "adjudicated_is_correct",
        "final_is_correct",
        "is_correct",
    ]

    for column in candidates:

        if column in df.columns:

            return column

    raise RuntimeError(
        "Could not find a final correctness column. "
        f"Columns found: {list(df.columns)}"
    )


def normalize_language(series):

    return (
        series
        .astype(str)
        .str.strip()
        .str.lower()
    )


# ============================================================
# LOAD ONE MODEL'S TWO HALVES
# ============================================================

def load_model(
    files,
    model_label,
):

    frames = []

    print("\n" + "=" * 80)
    print(f"LOADING {model_label}")
    print("=" * 80)

    for filename in files:

        df = pd.read_csv(
            filename,
            encoding="utf-8-sig",
        )

        print(
            f"\n{filename}: "
            f"{len(df)} rows"
        )

        if len(df) != 200:

            raise RuntimeError(
                f"{filename}: expected 200 rows "
                f"(100 problems x 2 languages), "
                f"found {len(df)}."
            )

        df["problem_id"] = pd.to_numeric(
            df["problem_id"],
            errors="raise",
        ).astype(int)

        df["language"] = normalize_language(
            df["language"]
        )

        score_column = find_final_score_column(
            df
        )

        print(
            "Final score column:",
            score_column
        )

        df["final_is_correct"] = pd.to_numeric(
            df[score_column],
            errors="raise",
        ).astype(int)

        invalid_scores = df[
            ~df[
                "final_is_correct"
            ].isin(
                [0, 1]
            )
        ]

        if len(invalid_scores):

            raise RuntimeError(
                f"{filename}: invalid correctness values."
            )

        df[
            "combined_source_file"
        ] = filename

        frames.append(
            df
        )

    combined = pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )

    # --------------------------------------------------------
    # 400 rows:
    # 200 problems x 2 languages
    # --------------------------------------------------------

    if len(combined) != 400:

        raise RuntimeError(
            f"{model_label}: expected 400 total rows, "
            f"found {len(combined)}."
        )

    if set(
        combined[
            "language"
        ].unique()
    ) != {
        "arabic",
        "english",
    }:

        raise RuntimeError(
            f"{model_label}: unexpected language values."
        )

    arabic_count = int(
        (
            combined[
                "language"
            ]
            ==
            "arabic"
        ).sum()
    )

    english_count = int(
        (
            combined[
                "language"
            ]
            ==
            "english"
        ).sum()
    )

    if arabic_count != 200:

        raise RuntimeError(
            f"{model_label}: expected 200 Arabic rows, "
            f"found {arabic_count}."
        )

    if english_count != 200:

        raise RuntimeError(
            f"{model_label}: expected 200 English rows, "
            f"found {english_count}."
        )

    actual_ids = sorted(
        combined[
            "problem_id"
        ].unique()
    )

    expected_ids = list(
        range(
            1,
            201,
        )
    )

    if actual_ids != expected_ids:

        raise RuntimeError(
            f"{model_label}: problem IDs are not "
            "exactly 1-200."
        )

    duplicates = int(
        combined.duplicated(
            subset=[
                "problem_id",
                "language",
            ]
        ).sum()
    )

    if duplicates:

        raise RuntimeError(
            f"{model_label}: found "
            f"{duplicates} duplicate pairs."
        )

    print(
        "\nCombined rows:",
        len(combined)
    )

    print(
        "Unique problems:",
        combined[
            "problem_id"
        ].nunique()
    )

    print(
        "Arabic rows:",
        arabic_count
    )

    print(
        "English rows:",
        english_count
    )

    print(
        "Duplicate problem/language pairs:",
        duplicates
    )

    return combined


# ============================================================
# PAIRED ANALYSIS
# ============================================================

def analyze_model(
    df,
    model_name,
):

    arabic = (

        df[
            df[
                "language"
            ]
            ==
            "arabic"
        ][
            [
                "problem_id",
                "final_is_correct",
            ]
        ]

        .rename(
            columns={
                "final_is_correct":
                    "arabic_correct"
            }
        )
    )

    english = (

        df[
            df[
                "language"
            ]
            ==
            "english"
        ][
            [
                "problem_id",
                "final_is_correct",
            ]
        ]

        .rename(
            columns={
                "final_is_correct":
                    "english_correct"
            }
        )
    )

    paired = pd.merge(
        arabic,
        english,
        on="problem_id",
        validate="one_to_one",
    )

    paired = paired.sort_values(
        "problem_id"
    ).reset_index(
        drop=True
    )

    if len(paired) != 200:

        raise RuntimeError(
            f"{model_name}: expected "
            f"200 paired problems."
        )

    # --------------------------------------------------------
    # SCORES
    # --------------------------------------------------------

    arabic_correct = int(
        paired[
            "arabic_correct"
        ].sum()
    )

    english_correct = int(
        paired[
            "english_correct"
        ].sum()
    )

    arabic_accuracy = (
        arabic_correct
        /
        200
    )

    english_accuracy = (
        english_correct
        /
        200
    )

    paired[
        "english_minus_arabic"
    ] = (
        paired[
            "english_correct"
        ]
        -
        paired[
            "arabic_correct"
        ]
    )

    gap = float(
        paired[
            "english_minus_arabic"
        ].mean()
    )

    # --------------------------------------------------------
    # PAIR COUNTS
    # --------------------------------------------------------

    both_correct = int(
        (
            (
                paired[
                    "arabic_correct"
                ]
                ==
                1
            )
            &
            (
                paired[
                    "english_correct"
                ]
                ==
                1
            )
        ).sum()
    )

    both_wrong = int(
        (
            (
                paired[
                    "arabic_correct"
                ]
                ==
                0
            )
            &
            (
                paired[
                    "english_correct"
                ]
                ==
                0
            )
        ).sum()
    )

    english_only = int(
        (
            (
                paired[
                    "arabic_correct"
                ]
                ==
                0
            )
            &
            (
                paired[
                    "english_correct"
                ]
                ==
                1
            )
        ).sum()
    )

    arabic_only = int(
        (
            (
                paired[
                    "arabic_correct"
                ]
                ==
                1
            )
            &
            (
                paired[
                    "english_correct"
                ]
                ==
                0
            )
        ).sum()
    )

    discordant = (
        english_only
        +
        arabic_only
    )

    # --------------------------------------------------------
    # EXACT MCNEMAR
    # --------------------------------------------------------

    if discordant:

        mcnemar_p = stats.binomtest(
            min(
                english_only,
                arabic_only,
            ),
            n=discordant,
            p=0.5,
            alternative="two-sided",
        ).pvalue

    else:

        mcnemar_p = 1.0

    # --------------------------------------------------------
    # PAIRED BOOTSTRAP
    # --------------------------------------------------------

    differences = paired[
        "english_minus_arabic"
    ].to_numpy(
        dtype=float
    )

    rng = np.random.default_rng(
        SEED
    )

    bootstrap = np.empty(
        BOOTSTRAP_SAMPLES
    )

    for i in range(
        BOOTSTRAP_SAMPLES
    ):

        sample = rng.choice(
            differences,
            size=len(
                differences
            ),
            replace=True,
        )

        bootstrap[
            i
        ] = sample.mean()

    ci_low = float(
        np.percentile(
            bootstrap,
            2.5,
        )
    )

    ci_high = float(
        np.percentile(
            bootstrap,
            97.5,
        )
    )

    # --------------------------------------------------------
    # PRINT
    # --------------------------------------------------------

    print("\n" + "=" * 80)
    print(f"{model_name} - FINAL 200 RESULTS")
    print("=" * 80)

    print(
        f"\nArabic : "
        f"{arabic_correct}/200 "
        f"= {arabic_accuracy:.4f}"
    )

    print(
        f"English: "
        f"{english_correct}/200 "
        f"= {english_accuracy:.4f}"
    )

    print(
        f"\nEnglish - Arabic gap: "
        f"{gap:+.4f}"
    )

    print(
        f"Percentage-point gap: "
        f"{gap * 100:+.1f}"
    )

    print("\nPaired outcomes:")

    print(
        "Both correct:",
        both_correct
    )

    print(
        "Both wrong:",
        both_wrong
    )

    print(
        "English-only correct:",
        english_only
    )

    print(
        "Arabic-only correct:",
        arabic_only
    )

    print(
        "\nDiscordant pairs:",
        discordant
    )

    print(
        "Exact McNemar p:",
        f"{mcnemar_p:.16g}"
    )

    print(
        "Paired bootstrap 95% CI:",
        f"[{ci_low:.4f}, {ci_high:.4f}]"
    )

    # --------------------------------------------------------
    # HALF-BY-HALF REPLICATION CHECK
    # --------------------------------------------------------

    print("\nHalf-by-half check:")

    for label, low, high in [
        (
            "Problems 1-100",
            1,
            100,
        ),
        (
            "Problems 101-200",
            101,
            200,
        ),
    ]:

        half = paired[
            (
                paired[
                    "problem_id"
                ]
                >=
                low
            )
            &
            (
                paired[
                    "problem_id"
                ]
                <=
                high
            )
        ]

        ar = int(
            half[
                "arabic_correct"
            ].sum()
        )

        en = int(
            half[
                "english_correct"
            ].sum()
        )

        half_gap = (
            en / 100
            -
            ar / 100
        )

        print(
            f"  {label}: "
            f"Arabic {ar}/100, "
            f"English {en}/100, "
            f"gap {half_gap * 100:+.1f} pp"
        )

    summary = {
        "model":
            model_name,

        "n_pairs":
            200,

        "arabic_correct":
            arabic_correct,

        "arabic_accuracy":
            arabic_accuracy,

        "english_correct":
            english_correct,

        "english_accuracy":
            english_accuracy,

        "english_minus_arabic":
            gap,

        "both_correct":
            both_correct,

        "both_wrong":
            both_wrong,

        "english_only_correct":
            english_only,

        "arabic_only_correct":
            arabic_only,

        "discordant_pairs":
            discordant,

        "mcnemar_exact_p":
            mcnemar_p,

        "bootstrap_ci_low":
            ci_low,

        "bootstrap_ci_high":
            ci_high,
    }

    return (
        paired,
        summary,
    )


# ============================================================
# LOAD BOTH MODELS
# ============================================================

gemma = load_model(
    GEMMA_FILES,
    "GEMMA",
)

qwen = load_model(
    QWEN_FILES,
    "QWEN",
)


# ============================================================
# SAVE COMBINED ADJUDICATED FILES
# ============================================================

gemma.to_csv(
    GEMMA_COMBINED_FILE,
    index=False,
    encoding="utf-8-sig",
)

qwen.to_csv(
    QWEN_COMBINED_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# ANALYZE MODELS
# ============================================================

gemma_paired, gemma_summary = analyze_model(
    gemma,
    "Gemma-3-1B-IT",
)

qwen_paired, qwen_summary = analyze_model(
    qwen,
    "Qwen2.5-Math-1.5B-Instruct",
)


# ============================================================
# SAVE PAIRED MODEL FILES
# ============================================================

gemma_paired.to_csv(
    GEMMA_PAIRED_FILE,
    index=False,
    encoding="utf-8-sig",
)

qwen_paired.to_csv(
    QWEN_PAIRED_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# MODEL SUMMARY
# ============================================================

model_summary = pd.DataFrame(
    [
        gemma_summary,
        qwen_summary,
    ]
)

model_summary.to_csv(
    MODEL_SUMMARY_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# CROSS-MODEL ANALYSIS
#
# Compare each model's English-Arabic difference on the SAME
# problem.
# ============================================================

cross = pd.merge(

    gemma_paired[
        [
            "problem_id",
            "arabic_correct",
            "english_correct",
            "english_minus_arabic",
        ]
    ].rename(
        columns={
            "arabic_correct":
                "gemma_arabic_correct",

            "english_correct":
                "gemma_english_correct",

            "english_minus_arabic":
                "gemma_language_gap",
        }
    ),

    qwen_paired[
        [
            "problem_id",
            "arabic_correct",
            "english_correct",
            "english_minus_arabic",
        ]
    ].rename(
        columns={
            "arabic_correct":
                "qwen_arabic_correct",

            "english_correct":
                "qwen_english_correct",

            "english_minus_arabic":
                "qwen_language_gap",
        }
    ),

    on="problem_id",
    validate="one_to_one",
)


if len(cross) != 200:

    raise RuntimeError(
        "Expected 200 cross-model matched problems."
    )


cross[
    "qwen_minus_gemma_gap"
] = (
    cross[
        "qwen_language_gap"
    ]
    -
    cross[
        "gemma_language_gap"
    ]
)


observed_cross_difference = float(
    cross[
        "qwen_minus_gemma_gap"
    ].mean()
)


# ============================================================
# CROSS-MODEL PAIRED BOOTSTRAP
# ============================================================

cross_values = cross[
    "qwen_minus_gemma_gap"
].to_numpy(
    dtype=float
)


rng = np.random.default_rng(
    SEED
)


cross_bootstrap = np.empty(
    BOOTSTRAP_SAMPLES
)


for i in range(
    BOOTSTRAP_SAMPLES
):

    sample = rng.choice(
        cross_values,
        size=len(
            cross_values
        ),
        replace=True,
    )

    cross_bootstrap[
        i
    ] = sample.mean()


cross_ci_low = float(
    np.percentile(
        cross_bootstrap,
        2.5,
    )
)


cross_ci_high = float(
    np.percentile(
        cross_bootstrap,
        97.5,
    )
)


# ============================================================
# PAIRED RANDOMIZATION TEST
#
# Null hypothesis:
# The model-specific language-gap difference is centered at 0.
#
# Randomly flip the sign of each problem-level difference.
# ============================================================

rng = np.random.default_rng(
    SEED
)


extreme = 0

completed = 0

batch_size = 5000


while completed < RANDOMIZATION_SAMPLES:

    current_batch = min(
        batch_size,
        RANDOMIZATION_SAMPLES
        -
        completed,
    )

    signs = rng.choice(
        [-1.0, 1.0],
        size=(
            current_batch,
            len(
                cross_values
            ),
        ),
    )

    randomized_means = (
        signs
        *
        cross_values
    ).mean(
        axis=1
    )

    extreme += int(
        (
            np.abs(
                randomized_means
            )
            >=
            abs(
                observed_cross_difference
            )
        ).sum()
    )

    completed += current_batch


randomization_p = (
    extreme
    +
    1
) / (
    RANDOMIZATION_SAMPLES
    +
    1
)


# ============================================================
# CROSS-MODEL LANGUAGE-SPECIFIC OUTCOMES
# ============================================================

arabic_both_correct = int(
    (
        (
            cross[
                "gemma_arabic_correct"
            ]
            ==
            1
        )
        &
        (
            cross[
                "qwen_arabic_correct"
            ]
            ==
            1
        )
    ).sum()
)


arabic_gemma_only = int(
    (
        (
            cross[
                "gemma_arabic_correct"
            ]
            ==
            1
        )
        &
        (
            cross[
                "qwen_arabic_correct"
            ]
            ==
            0
        )
    ).sum()
)


arabic_qwen_only = int(
    (
        (
            cross[
                "gemma_arabic_correct"
            ]
            ==
            0
        )
        &
        (
            cross[
                "qwen_arabic_correct"
            ]
            ==
            1
        )
    ).sum()
)


arabic_neither = int(
    (
        (
            cross[
                "gemma_arabic_correct"
            ]
            ==
            0
        )
        &
        (
            cross[
                "qwen_arabic_correct"
            ]
            ==
            0
        )
    ).sum()
)


english_both_correct = int(
    (
        (
            cross[
                "gemma_english_correct"
            ]
            ==
            1
        )
        &
        (
            cross[
                "qwen_english_correct"
            ]
            ==
            1
        )
    ).sum()
)


english_gemma_only = int(
    (
        (
            cross[
                "gemma_english_correct"
            ]
            ==
            1
        )
        &
        (
            cross[
                "qwen_english_correct"
            ]
            ==
            0
        )
    ).sum()
)


english_qwen_only = int(
    (
        (
            cross[
                "gemma_english_correct"
            ]
            ==
            0
        )
        &
        (
            cross[
                "qwen_english_correct"
            ]
            ==
            1
        )
    ).sum()
)


english_neither = int(
    (
        (
            cross[
                "gemma_english_correct"
            ]
            ==
            0
        )
        &
        (
            cross[
                "qwen_english_correct"
            ]
            ==
            0
        )
    ).sum()
)


# ============================================================
# PRINT CROSS-MODEL RESULTS
# ============================================================

print("\n" + "=" * 80)
print("CROSS-MODEL LANGUAGE-GAP COMPARISON")
print("=" * 80)


print(
    "\nGemma language gap:",
    f"{gemma_summary['english_minus_arabic']:+.4f}"
)


print(
    "Qwen language gap :",
    f"{qwen_summary['english_minus_arabic']:+.4f}"
)


print(
    "\nQwen gap - Gemma gap:",
    f"{observed_cross_difference:+.4f}"
)


print(
    "Percentage-point difference:",
    f"{observed_cross_difference * 100:+.1f}"
)


print(
    "Paired bootstrap 95% CI:",
    f"[{cross_ci_low:.4f}, {cross_ci_high:.4f}]"
)


print(
    "Paired randomization p:",
    f"{randomization_p:.8f}"
)


if randomization_p < 0.0001:

    print(
        "Report-ready randomization result: p < 0.0001"
    )


# ============================================================
# PRINT CROSS-MODEL LANGUAGE TABLES
# ============================================================

print("\n" + "=" * 80)
print("ARABIC CROSS-MODEL OUTCOMES")
print("=" * 80)


print(
    "\nBoth correct:",
    arabic_both_correct
)

print(
    "Gemma only:",
    arabic_gemma_only
)

print(
    "Qwen only:",
    arabic_qwen_only
)

print(
    "Neither:",
    arabic_neither
)


print("\n" + "=" * 80)
print("ENGLISH CROSS-MODEL OUTCOMES")
print("=" * 80)


print(
    "\nBoth correct:",
    english_both_correct
)

print(
    "Gemma only:",
    english_gemma_only
)

print(
    "Qwen only:",
    english_qwen_only
)

print(
    "Neither:",
    english_neither
)


# ============================================================
# SAVE CROSS-MODEL PROBLEM DATA
# ============================================================

cross.to_csv(
    CROSS_PROBLEM_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# SAVE CROSS-MODEL SUMMARY
# ============================================================

cross_summary = pd.DataFrame(
    [
        {
            "n_pairs":
                200,

            "gemma_language_gap":
                gemma_summary[
                    "english_minus_arabic"
                ],

            "qwen_language_gap":
                qwen_summary[
                    "english_minus_arabic"
                ],

            "qwen_minus_gemma_gap":
                observed_cross_difference,

            "bootstrap_ci_low":
                cross_ci_low,

            "bootstrap_ci_high":
                cross_ci_high,

            "randomization_samples":
                RANDOMIZATION_SAMPLES,

            "randomization_p":
                randomization_p,

            "arabic_both_correct":
                arabic_both_correct,

            "arabic_gemma_only":
                arabic_gemma_only,

            "arabic_qwen_only":
                arabic_qwen_only,

            "arabic_neither":
                arabic_neither,

            "english_both_correct":
                english_both_correct,

            "english_gemma_only":
                english_gemma_only,

            "english_qwen_only":
                english_qwen_only,

            "english_neither":
                english_neither,
        }
    ]
)


cross_summary.to_csv(
    CROSS_SUMMARY_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# FILES CREATED
# ============================================================

print("\n" + "=" * 80)
print("FILES CREATED")
print("=" * 80)


for filename in [
    GEMMA_COMBINED_FILE,
    QWEN_COMBINED_FILE,
    GEMMA_PAIRED_FILE,
    QWEN_PAIRED_FILE,
    MODEL_SUMMARY_FILE,
    CROSS_PROBLEM_FILE,
    CROSS_SUMMARY_FILE,
]:

    print(
        filename
    )


print("\n" + "=" * 80)
print("ALL-200 ANALYSIS COMPLETE")
print("=" * 80)