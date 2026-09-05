import numpy as np
import pandas as pd
from scipy import stats


# ============================================================
# CONFIGURATION
# ============================================================

GEMMA_FILE = "gemma_mgsm_200_paired_results.csv"
QWEN_FILE = "qwen_mgsm_200_paired_results.csv"

SUMMARY_FILE = "mgsm_200_robustness_summary.csv"
QC_FILE = "mgsm_200_qc_exclusions.csv"

BOOTSTRAP_SAMPLES = 10000
RANDOMIZATION_SAMPLES = 100000
SEED = 42


# ============================================================
# PRE-GENERATION BENCHMARK QC AUDIT
#
# These exclusions were determined from semantic inspection
# of the bilingual benchmark pairs, not from model outcomes.
# ============================================================

QC_ISSUES = {

    # --------------------------------------------------------
    # Original Problems 1-100
    # --------------------------------------------------------

    43: {
        "category": "AMBIGUOUS_SOURCE",
        "note": (
            "Speed improved by 10% is ambiguous; gold assumes "
            "travel time is reduced by 10%."
        ),
    },

    51: {
        "category": "SEMANTIC_MISMATCH",
        "note": (
            "English states each pair of shoes costs $60; "
            "Arabic states each shoe costs $60."
        ),
    },

    55: {
        "category": "AMBIGUOUS_TRANSLATION",
        "note": (
            "English explicitly specifies two sandwiches/subs; "
            "Arabic wording omits the numeral while retaining "
            "a dual-language cue."
        ),
    },

    86: {
        "category": "AMBIGUOUS_SOURCE",
        "note": (
            "Problem states at least five rides per week, "
            "while the gold answer assumes exactly five."
        ),
    },

    100: {
        "category": "SEMANTIC_MISMATCH",
        "note": (
            "English divides the amount three ways including "
            "Isabel and two parents; Arabic wording indicates "
            "division between the parents."
        ),
    },


    # --------------------------------------------------------
    # Extension Problems 101-200
    # --------------------------------------------------------

    122: {
        "category": "AMBIGUOUS_SOURCE",
        "note": (
            "The expression '2/5 times more' is mathematically "
            "ambiguous; the benchmark gold interprets it as "
            "40 percent more."
        ),
    },

    150: {
        "category": "AMBIGUOUS_SOURCE",
        "note": (
            "Gold answer assumes one month equals exactly "
            "four weeks."
        ),
    },

    163: {
        "category": "AMBIGUOUS_SOURCE",
        "note": (
            "The reference set for 'one quarter the number "
            "of pieces' is not fully explicit."
        ),
    },

    166: {
        "category": "AMBIGUOUS_TRANSLATION",
        "note": (
            "English specifically asks how much farther the "
            "winner ran; Arabic uses a less explicit comparison."
        ),
    },

    171: {
        "category": "AMBIGUOUS_TRANSLATION",
        "note": (
            "Arabic multiplicative-age wording is less precise "
            "than the English 'two times as old' formulation."
        ),
    },

    175: {
        "category": "AMBIGUOUS_TRANSLATION",
        "note": (
            "Arabic multiplicative wording may be interpreted "
            "ambiguously relative to English 'four times as many'."
        ),
    },

    189: {
        "category": "SEMANTIC_MISMATCH",
        "note": (
            "English states cumulative customers by the third "
            "day totaled 500; Arabic can state that the third "
            "day itself had 500 customers."
        ),
    },

    192: {
        "category": "AMBIGUOUS_TRANSLATION",
        "note": (
            "Arabic uses wording equivalent to 'two times more', "
            "which is less precise than English 'twice as many'."
        ),
    },

    197: {
        "category": "SEMANTIC_MISMATCH",
        "note": (
            "English asks for individual reading instances by "
            "two people, whereas Arabic can naturally be read "
            "as the number of distinct books read together."
        ),
    },
}


# ============================================================
# QC SETS
# ============================================================

SEMANTIC_MISMATCH = {
    problem_id
    for problem_id, info in QC_ISSUES.items()
    if info["category"] == "SEMANTIC_MISMATCH"
}


AMBIGUOUS_TRANSLATION = {
    problem_id
    for problem_id, info in QC_ISSUES.items()
    if info["category"] == "AMBIGUOUS_TRANSLATION"
}


AMBIGUOUS_SOURCE = {
    problem_id
    for problem_id, info in QC_ISSUES.items()
    if info["category"] == "AMBIGUOUS_SOURCE"
}


STRICT_EXCLUSIONS = (
    SEMANTIC_MISMATCH
    |
    AMBIGUOUS_TRANSLATION
    |
    AMBIGUOUS_SOURCE
)


SUBSETS = {
    "ALL_200": {
        "exclude": set(),
        "description": (
            "Primary randomized benchmark sample; no QC exclusions."
        ),
    },

    "DEFINITE_MATCHED": {
        "exclude": SEMANTIC_MISMATCH,
        "description": (
            "Excludes definite English-Arabic semantic mismatches."
        ),
    },

    "TRANSLATION_CLEAN": {
        "exclude": (
            SEMANTIC_MISMATCH
            |
            AMBIGUOUS_TRANSLATION
        ),
        "description": (
            "Excludes semantic mismatches and ambiguous translations."
        ),
    },

    "STRICT_QC": {
        "exclude": STRICT_EXCLUSIONS,
        "description": (
            "Excludes semantic mismatches, ambiguous translations, "
            "and ambiguous source problems."
        ),
    },
}


# ============================================================
# LOAD AND VALIDATE PAIRED MODEL FILE
# ============================================================

def load_paired(
    filename,
    model_name,
):

    df = pd.read_csv(
        filename,
        encoding="utf-8-sig",
    )


    print("\n" + "=" * 80)
    print(f"LOADING {model_name}")
    print("=" * 80)


    print(
        "\nFile:",
        filename
    )

    print(
        "Rows:",
        len(df)
    )


    if len(df) != 200:

        raise RuntimeError(
            f"{model_name}: expected 200 paired rows, "
            f"found {len(df)}."
        )


    required = {
        "problem_id",
        "arabic_correct",
        "english_correct",
    }


    missing = (
        required
        -
        set(df.columns)
    )


    if missing:

        raise RuntimeError(
            f"{model_name}: missing columns {missing}"
        )


    df[
        "problem_id"
    ] = pd.to_numeric(
        df[
            "problem_id"
        ],
        errors="raise",
    ).astype(int)


    df[
        "arabic_correct"
    ] = pd.to_numeric(
        df[
            "arabic_correct"
        ],
        errors="raise",
    ).astype(int)


    df[
        "english_correct"
    ] = pd.to_numeric(
        df[
            "english_correct"
        ],
        errors="raise",
    ).astype(int)


    expected_ids = list(
        range(
            1,
            201,
        )
    )


    actual_ids = sorted(
        df[
            "problem_id"
        ].tolist()
    )


    if actual_ids != expected_ids:

        raise RuntimeError(
            f"{model_name}: problem IDs are not exactly 1-200."
        )


    invalid_ar = df[
        ~df[
            "arabic_correct"
        ].isin(
            [0, 1]
        )
    ]


    invalid_en = df[
        ~df[
            "english_correct"
        ].isin(
            [0, 1]
        )
    ]


    if len(
        invalid_ar
    ) or len(
        invalid_en
    ):

        raise RuntimeError(
            f"{model_name}: invalid correctness values."
        )


    df[
        "english_minus_arabic"
    ] = (
        df[
            "english_correct"
        ]
        -
        df[
            "arabic_correct"
        ]
    )


    return df


# ============================================================
# WITHIN-MODEL ANALYSIS
# ============================================================

def analyze_model_subset(
    df,
    model_name,
    subset_name,
):

    n = len(
        df
    )


    if n == 0:

        raise RuntimeError(
            f"{model_name}/{subset_name}: empty subset."
        )


    arabic_correct = int(
        df[
            "arabic_correct"
        ].sum()
    )


    english_correct = int(
        df[
            "english_correct"
        ].sum()
    )


    arabic_accuracy = (
        arabic_correct
        /
        n
    )


    english_accuracy = (
        english_correct
        /
        n
    )


    differences = df[
        "english_minus_arabic"
    ].to_numpy(
        dtype=float
    )


    gap = float(
        differences.mean()
    )


    # --------------------------------------------------------
    # PAIRED OUTCOMES
    # --------------------------------------------------------

    both_correct = int(
        (
            (
                df[
                    "arabic_correct"
                ]
                ==
                1
            )
            &
            (
                df[
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
                df[
                    "arabic_correct"
                ]
                ==
                0
            )
            &
            (
                df[
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
                df[
                    "arabic_correct"
                ]
                ==
                0
            )
            &
            (
                df[
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
                df[
                    "arabic_correct"
                ]
                ==
                1
            )
            &
            (
                df[
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
            size=n,
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


    return {
        "subset":
            subset_name,

        "model":
            model_name,

        "n_pairs":
            n,

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


# ============================================================
# CROSS-MODEL SUBSET ANALYSIS
# ============================================================

def analyze_cross_subset(
    gemma,
    qwen,
    subset_name,
):

    cross = pd.merge(

        gemma[
            [
                "problem_id",
                "english_minus_arabic",
            ]
        ].rename(
            columns={
                "english_minus_arabic":
                    "gemma_gap"
            }
        ),

        qwen[
            [
                "problem_id",
                "english_minus_arabic",
            ]
        ].rename(
            columns={
                "english_minus_arabic":
                    "qwen_gap"
            }
        ),

        on="problem_id",
        validate="one_to_one",
    )


    n = len(
        cross
    )


    cross[
        "qwen_minus_gemma"
    ] = (
        cross[
            "qwen_gap"
        ]
        -
        cross[
            "gemma_gap"
        ]
    )


    values = cross[
        "qwen_minus_gemma"
    ].to_numpy(
        dtype=float
    )


    observed = float(
        values.mean()
    )


    # --------------------------------------------------------
    # BOOTSTRAP
    # --------------------------------------------------------

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
            values,
            size=n,
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
    # PAIRED RANDOMIZATION
    # --------------------------------------------------------

    rng = np.random.default_rng(
        SEED
    )


    extreme = 0
    completed = 0
    batch_size = 5000


    while (
        completed
        <
        RANDOMIZATION_SAMPLES
    ):

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
                n,
            ),
        )


        randomized = (
            signs
            *
            values
        ).mean(
            axis=1
        )


        extreme += int(
            (
                np.abs(
                    randomized
                )
                >=
                abs(
                    observed
                )
            ).sum()
        )


        completed += (
            current_batch
        )


    randomization_p = (
        extreme
        +
        1
    ) / (
        RANDOMIZATION_SAMPLES
        +
        1
    )


    return {
        "subset":
            subset_name,

        "model":
            "CROSS_MODEL",

        "n_pairs":
            n,

        "gemma_language_gap":
            float(
                gemma[
                    "english_minus_arabic"
                ].mean()
            ),

        "qwen_language_gap":
            float(
                qwen[
                    "english_minus_arabic"
                ].mean()
            ),

        "qwen_minus_gemma_gap":
            observed,

        "bootstrap_ci_low":
            ci_low,

        "bootstrap_ci_high":
            ci_high,

        "randomization_samples":
            RANDOMIZATION_SAMPLES,

        "randomization_p":
            randomization_p,
    }


# ============================================================
# LOAD
# ============================================================

gemma = load_paired(
    GEMMA_FILE,
    "Gemma-3-1B-IT",
)


qwen = load_paired(
    QWEN_FILE,
    "Qwen2.5-Math-1.5B-Instruct",
)


# ============================================================
# VERIFY PRIMARY ALL-200 RESULTS
#
# This protects against accidentally analyzing the wrong files.
# ============================================================

if int(
    gemma[
        "arabic_correct"
    ].sum()
) != 44:

    raise RuntimeError(
        "Unexpected Gemma Arabic ALL-200 score."
    )


if int(
    gemma[
        "english_correct"
    ].sum()
) != 121:

    raise RuntimeError(
        "Unexpected Gemma English ALL-200 score."
    )


if int(
    qwen[
        "arabic_correct"
    ].sum()
) != 3:

    raise RuntimeError(
        "Unexpected Qwen Arabic ALL-200 score."
    )


if int(
    qwen[
        "english_correct"
    ].sum()
) != 179:

    raise RuntimeError(
        "Unexpected Qwen English ALL-200 score."
    )


# ============================================================
# QC INVENTORY
# ============================================================

print("\n" + "=" * 80)
print("BENCHMARK QUALITY-CONTROL INVENTORY")
print("=" * 80)


print(
    "\nSemantic mismatches:",
    sorted(
        SEMANTIC_MISMATCH
    )
)


print(
    "Ambiguous translations:",
    sorted(
        AMBIGUOUS_TRANSLATION
    )
)


print(
    "Ambiguous source problems:",
    sorted(
        AMBIGUOUS_SOURCE
    )
)


print(
    "\nTotal strict-QC exclusions:",
    len(
        STRICT_EXCLUSIONS
    )
)


print(
    "Strict-QC retained:",
    200
    -
    len(
        STRICT_EXCLUSIONS
    )
)


# ============================================================
# SAVE QC INVENTORY
# ============================================================

qc_rows = []


for problem_id in sorted(
    QC_ISSUES
):

    qc_rows.append({
        "problem_id":
            problem_id,

        "category":
            QC_ISSUES[
                problem_id
            ][
                "category"
            ],

        "note":
            QC_ISSUES[
                problem_id
            ][
                "note"
            ],
    })


pd.DataFrame(
    qc_rows
).to_csv(
    QC_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# RUN ALL ROBUSTNESS SUBSETS
# ============================================================

all_rows = []


for (
    subset_name,
    subset_info
) in SUBSETS.items():

    excluded = subset_info[
        "exclude"
    ]


    gemma_subset = gemma[
        ~gemma[
            "problem_id"
        ].isin(
            excluded
        )
    ].copy()


    qwen_subset = qwen[
        ~qwen[
            "problem_id"
        ].isin(
            excluded
        )
    ].copy()


    if (
        list(
            gemma_subset[
                "problem_id"
            ]
        )
        !=
        list(
            qwen_subset[
                "problem_id"
            ]
        )
    ):

        raise RuntimeError(
            f"{subset_name}: model problem IDs "
            "are not aligned."
        )


    expected_n = (
        200
        -
        len(
            excluded
        )
    )


    if len(
        gemma_subset
    ) != expected_n:

        raise RuntimeError(
            f"{subset_name}: expected "
            f"{expected_n} problems, found "
            f"{len(gemma_subset)}."
        )


    gemma_result = analyze_model_subset(
        gemma_subset,
        "Gemma-3-1B-IT",
        subset_name,
    )


    qwen_result = analyze_model_subset(
        qwen_subset,
        "Qwen2.5-Math-1.5B-Instruct",
        subset_name,
    )


    cross_result = analyze_cross_subset(
        gemma_subset,
        qwen_subset,
        subset_name,
    )


    all_rows.append(
        gemma_result
    )

    all_rows.append(
        qwen_result
    )

    all_rows.append(
        cross_result
    )


    # --------------------------------------------------------
    # PRINT SUBSET RESULTS
    # --------------------------------------------------------

    print("\n" + "=" * 80)
    print(subset_name)
    print("=" * 80)


    print(
        "\nDescription:"
    )

    print(
        subset_info[
            "description"
        ]
    )


    print(
        "\nExcluded IDs:",
        (
            sorted(
                excluded
            )
            if excluded
            else "None"
        )
    )


    print(
        "\nRetained problems:",
        expected_n
    )


    print(
        "\nGEMMA"
    )

    print(
        f"Arabic : "
        f"{gemma_result['arabic_correct']}"
        f"/{expected_n} "
        f"= "
        f"{gemma_result['arabic_accuracy']:.4f}"
    )

    print(
        f"English: "
        f"{gemma_result['english_correct']}"
        f"/{expected_n} "
        f"= "
        f"{gemma_result['english_accuracy']:.4f}"
    )

    print(
        f"Gap: "
        f"{gemma_result['english_minus_arabic']:+.4f} "
        f"("
        f"{gemma_result['english_minus_arabic'] * 100:+.2f} pp"
        f")"
    )

    print(
        "95% CI:",
        f"["
        f"{gemma_result['bootstrap_ci_low']:.4f}, "
        f"{gemma_result['bootstrap_ci_high']:.4f}"
        f"]"
    )

    print(
        "McNemar p:",
        f"{gemma_result['mcnemar_exact_p']:.16g}"
    )


    print(
        "\nQWEN"
    )

    print(
        f"Arabic : "
        f"{qwen_result['arabic_correct']}"
        f"/{expected_n} "
        f"= "
        f"{qwen_result['arabic_accuracy']:.4f}"
    )

    print(
        f"English: "
        f"{qwen_result['english_correct']}"
        f"/{expected_n} "
        f"= "
        f"{qwen_result['english_accuracy']:.4f}"
    )

    print(
        f"Gap: "
        f"{qwen_result['english_minus_arabic']:+.4f} "
        f"("
        f"{qwen_result['english_minus_arabic'] * 100:+.2f} pp"
        f")"
    )

    print(
        "95% CI:",
        f"["
        f"{qwen_result['bootstrap_ci_low']:.4f}, "
        f"{qwen_result['bootstrap_ci_high']:.4f}"
        f"]"
    )

    print(
        "McNemar p:",
        f"{qwen_result['mcnemar_exact_p']:.16g}"
    )


    print(
        "\nCROSS-MODEL GAP DIFFERENCE"
    )

    print(
        "Gemma gap:",
        f"{cross_result['gemma_language_gap']:+.4f}"
    )

    print(
        "Qwen gap :",
        f"{cross_result['qwen_language_gap']:+.4f}"
    )

    print(
        "Qwen - Gemma:",
        f"{cross_result['qwen_minus_gemma_gap']:+.4f} "
        f"("
        f"{cross_result['qwen_minus_gemma_gap'] * 100:+.2f} pp"
        f")"
    )

    print(
        "95% CI:",
        f"["
        f"{cross_result['bootstrap_ci_low']:.4f}, "
        f"{cross_result['bootstrap_ci_high']:.4f}"
        f"]"
    )

    print(
        "Randomization p:",
        f"{cross_result['randomization_p']:.8f}"
    )


    if (
        cross_result[
            "randomization_p"
        ]
        <
        0.0001
    ):

        print(
            "Report-ready: p < 0.0001"
        )


# ============================================================
# SAVE SUMMARY
# ============================================================

summary = pd.DataFrame(
    all_rows
)


summary.to_csv(
    SUMMARY_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# FINAL CONSISTENCY TABLE
# ============================================================

print("\n" + "=" * 80)
print("ROBUSTNESS OVERVIEW")
print("=" * 80)


for subset_name in SUBSETS:

    rows = summary[
        summary[
            "subset"
        ]
        ==
        subset_name
    ]


    gemma_row = rows[
        rows[
            "model"
        ]
        ==
        "Gemma-3-1B-IT"
    ].iloc[
        0
    ]


    qwen_row = rows[
        rows[
            "model"
        ]
        ==
        "Qwen2.5-Math-1.5B-Instruct"
    ].iloc[
        0
    ]


    cross_row = rows[
        rows[
            "model"
        ]
        ==
        "CROSS_MODEL"
    ].iloc[
        0
    ]


    print(
        f"\n{subset_name}"
    )

    print(
        f"  N = "
        f"{int(gemma_row['n_pairs'])}"
    )

    print(
        f"  Gemma gap = "
        f"{gemma_row['english_minus_arabic'] * 100:+.2f} pp"
    )

    print(
        f"  Qwen gap  = "
        f"{qwen_row['english_minus_arabic'] * 100:+.2f} pp"
    )

    print(
        f"  Qwen-Gemma gap difference = "
        f"{cross_row['qwen_minus_gemma_gap'] * 100:+.2f} pp"
    )


print("\n" + "=" * 80)
print("FILES CREATED")
print("=" * 80)


print(
    "\n",
    SUMMARY_FILE
)

print(
    " ",
    QC_FILE
)


print("\n" + "=" * 80)
print("MGSM-200 ROBUSTNESS ANALYSIS COMPLETE")
print("=" * 80)