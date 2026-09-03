import pandas as pd
import numpy as np
from scipy import stats


GEMMA_FILE = "gemma_mgsm_100_adjudicated.csv"
QWEN_FILE = "qwen_mgsm_100_adjudicated.csv"

AUDIT_INPUT = r"data\processed\global_mgsm_ar_en_100_review.csv"
AUDIT_OUTPUT = r"data\processed\global_mgsm_ar_en_100_audited.csv"

SUMMARY_OUTPUT = "mgsm_100_robustness_summary.csv"

BOOTSTRAP_SAMPLES = 20000
RANDOMIZATION_SAMPLES = 100000
SEED = 42


# ============================================================
# BENCHMARK AUDIT
# ============================================================

audit = pd.read_csv(
    AUDIT_INPUT,
    encoding="utf-8-sig",
)

audit["audit_status"] = "OK"
audit["audit_note"] = ""


AUDIT_NOTES = {

    43: (
        "AMBIGUOUS_SOURCE",
        "Both languages say Gerald's speed improved by 10%. "
        "A literal 10% speed increase gives approximately "
        "36.36 seconds, while gold=36 assumes a 10% reduction "
        "in running time."
    ),

    51: (
        "SEMANTIC_MISMATCH",
        "English implies each pair of shoes costs $60. "
        "Arabic states that each shoe costs $60. "
        "Gold=360 follows the English interpretation."
    ),

    55: (
        "AMBIGUOUS_TRANSLATION",
        "English explicitly specifies 2 subs. "
        "Arabic omits the numeral 2 before the sandwich phrase, "
        "although a later dual pronoun suggests two items. "
        "Gold=29 requires two subs."
    ),

    86: (
        "AMBIGUOUS_SOURCE",
        "Both languages state that Michael rides at least "
        "5 times per week. The total is therefore not uniquely "
        "determined. Gold=860 assumes exactly 5 rides per week."
    ),

    100: (
        "SEMANTIC_MISMATCH",
        "English says the total is split three ways with "
        "Isabelle's two parents. Arabic says the total is split "
        "between her parents. Gold=32 follows the English "
        "three-way split; literal Arabic gives 48."
    ),
}


MINOR_NOTES = {

    1: (
        "MINOR_WORDING",
        "Arabic uses a generic word meaning pieces rather than bolts; "
        "the numerical relationship is preserved."
    ),

    6: (
        "MINOR_WORDING",
        "The Arabic coaching rate is less explicit about 'per hour', "
        "but the parallel hourly context preserves the intended problem."
    ),

    65: (
        "MINOR_WORDING",
        "Bond paper is rendered inaccurately as wrapping paper, "
        "but the $20 quantity and mathematical structure are unchanged."
    ),

    69: (
        "MINOR_WORDING",
        "Minor gender/wording differences do not alter the quantities "
        "or mathematical task."
    ),

    70: (
        "MINOR_WORDING",
        "Flan is rendered as a generic Spanish pie, but the egg "
        "requirements and mathematical task are unchanged."
    ),
}


for problem_id, (status, note) in {
    **AUDIT_NOTES,
    **MINOR_NOTES,
}.items():

    mask = (
        audit["id"] == problem_id
    )

    audit.loc[
        mask,
        "audit_status"
    ] = status

    audit.loc[
        mask,
        "audit_note"
    ] = note


audit.to_csv(
    AUDIT_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)


print("=" * 80)
print("BENCHMARK AUDIT")
print("=" * 80)

print(
    "\nAudit status counts:"
)

print(
    audit["audit_status"].value_counts()
)

print(
    "\nAudited file:",
    AUDIT_OUTPUT,
)


# ============================================================
# ANALYSIS SCENARIOS
# ============================================================

SCENARIOS = {

    # Original standardized benchmark.
    "ALL_100":
        set(),

    # Remove only definite Arabic-English semantic mismatches.
    "DEFINITE_MATCHED_98":
        {51, 100},

    # Also remove malformed/ambiguous Arabic translation.
    "TRANSLATION_CLEAN_97":
        {51, 55, 100},

    # Most conservative quality-control analysis.
    "STRICT_QC_95":
        {43, 51, 55, 86, 100},
}


# ============================================================
# LOAD MODEL RESULTS
# ============================================================

gemma = pd.read_csv(
    GEMMA_FILE,
    encoding="utf-8-sig",
)

qwen = pd.read_csv(
    QWEN_FILE,
    encoding="utf-8-sig",
)


def normalize(df):

    df = df.copy()

    df["problem_id"] = pd.to_numeric(
        df["problem_id"],
        errors="raise",
    ).astype(int)

    df["language"] = (
        df["language"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["manual_is_correct"] = pd.to_numeric(
        df["manual_is_correct"],
        errors="raise",
    ).astype(int)

    return df


gemma = normalize(gemma)
qwen = normalize(qwen)


# ============================================================
# BUILD PAIRED DATA
# ============================================================

def build_model_pairs(
    df,
    prefix,
):

    ar = (
        df[
            df["language"] == "arabic"
        ][
            [
                "problem_id",
                "manual_is_correct",
            ]
        ]
        .rename(
            columns={
                "manual_is_correct":
                    f"{prefix}_arabic"
            }
        )
    )

    en = (
        df[
            df["language"] == "english"
        ][
            [
                "problem_id",
                "manual_is_correct",
            ]
        ]
        .rename(
            columns={
                "manual_is_correct":
                    f"{prefix}_english"
            }
        )
    )

    result = pd.merge(
        ar,
        en,
        on="problem_id",
        validate="one_to_one",
    )

    result[
        f"{prefix}_gap"
    ] = (
        result[f"{prefix}_english"]
        -
        result[f"{prefix}_arabic"]
    )

    return result


gemma_pairs = build_model_pairs(
    gemma,
    "gemma",
)

qwen_pairs = build_model_pairs(
    qwen,
    "qwen",
)


combined = pd.merge(
    gemma_pairs,
    qwen_pairs,
    on="problem_id",
    validate="one_to_one",
)


if len(combined) != 100:

    raise RuntimeError(
        f"Expected 100 matched problems; found {len(combined)}."
    )


# ============================================================
# STATISTICS
# ============================================================

rng = np.random.default_rng(
    SEED
)


def analyze_model(
    data,
    prefix,
):

    n = len(data)

    ar_correct = int(
        data[
            f"{prefix}_arabic"
        ].sum()
    )

    en_correct = int(
        data[
            f"{prefix}_english"
        ].sum()
    )

    ar_accuracy = (
        ar_correct / n
    )

    en_accuracy = (
        en_correct / n
    )

    differences = (
        data[f"{prefix}_gap"]
        .to_numpy(dtype=float)
    )

    gap = float(
        differences.mean()
    )


    both_correct = int(
        (
            (data[f"{prefix}_arabic"] == 1)
            &
            (data[f"{prefix}_english"] == 1)
        ).sum()
    )

    both_wrong = int(
        (
            (data[f"{prefix}_arabic"] == 0)
            &
            (data[f"{prefix}_english"] == 0)
        ).sum()
    )

    english_only = int(
        (
            (data[f"{prefix}_arabic"] == 0)
            &
            (data[f"{prefix}_english"] == 1)
        ).sum()
    )

    arabic_only = int(
        (
            (data[f"{prefix}_arabic"] == 1)
            &
            (data[f"{prefix}_english"] == 0)
        ).sum()
    )

    discordant = (
        english_only
        +
        arabic_only
    )


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

        bootstrap[i] = (
            sample.mean()
        )


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

        "n":
            n,

        "arabic_correct":
            ar_correct,

        "arabic_accuracy":
            ar_accuracy,

        "english_correct":
            en_correct,

        "english_accuracy":
            en_accuracy,

        "gap":
            gap,

        "both_correct":
            both_correct,

        "both_wrong":
            both_wrong,

        "english_only":
            english_only,

        "arabic_only":
            arabic_only,

        "mcnemar_p":
            mcnemar_p,

        "ci_low":
            ci_low,

        "ci_high":
            ci_high,
    }


# ============================================================
# RUN ALL SENSITIVITY ANALYSES
# ============================================================

summary_rows = []


for scenario, excluded_ids in SCENARIOS.items():

    data = combined[
        ~combined[
            "problem_id"
        ].isin(
            excluded_ids
        )
    ].copy()


    print("\n")
    print("=" * 80)
    print(scenario)
    print("=" * 80)

    print(
        "\nExcluded IDs:",
        sorted(excluded_ids)
        if excluded_ids
        else "None"
    )

    print(
        "Number of matched problems:",
        len(data)
    )


    gemma_result = analyze_model(
        data,
        "gemma",
    )

    qwen_result = analyze_model(
        data,
        "qwen",
    )


    for model_name, result in [
        ("Gemma-3-1B-IT", gemma_result),
        ("Qwen2.5-Math-1.5B-Instruct", qwen_result),
    ]:

        print(
            f"\n{model_name}"
        )

        print(
            f"Arabic : "
            f"{result['arabic_correct']}/{result['n']} "
            f"= {result['arabic_accuracy']:.4f}"
        )

        print(
            f"English: "
            f"{result['english_correct']}/{result['n']} "
            f"= {result['english_accuracy']:.4f}"
        )

        print(
            f"Gap: "
            f"{result['gap']:+.4f}"
        )

        print(
            f"95% CI: "
            f"[{result['ci_low']:.4f}, "
            f"{result['ci_high']:.4f}]"
        )

        print(
            f"McNemar p: "
            f"{result['mcnemar_p']:.16g}"
        )


        summary_rows.append({

            "scenario":
                scenario,

            "excluded_ids":
                ",".join(
                    str(x)
                    for x in sorted(
                        excluded_ids
                    )
                ),

            "model":
                model_name,

            **result,
        })


    # ========================================================
    # CROSS-MODEL DIFFERENCE IN LANGUAGE GAP
    # ========================================================

    per_problem_cross_difference = (
        data["qwen_gap"]
        -
        data["gemma_gap"]
    ).to_numpy(
        dtype=float
    )


    observed_cross_gap = float(
        per_problem_cross_difference.mean()
    )


    cross_bootstrap = np.empty(
        BOOTSTRAP_SAMPLES
    )


    for i in range(
        BOOTSTRAP_SAMPLES
    ):

        sample = rng.choice(
            per_problem_cross_difference,
            size=len(
                per_problem_cross_difference
            ),
            replace=True,
        )

        cross_bootstrap[i] = (
            sample.mean()
        )


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


    observed_abs = abs(
        observed_cross_gap
    )


    extreme = 0


    for _ in range(
        RANDOMIZATION_SAMPLES
    ):

        signs = rng.choice(
            [-1, 1],
            size=len(
                per_problem_cross_difference
            ),
        )

        permuted = abs(
            np.mean(
                per_problem_cross_difference
                * signs
            )
        )

        if permuted >= observed_abs:

            extreme += 1


    randomization_p = (
        extreme + 1
    ) / (
        RANDOMIZATION_SAMPLES + 1
    )


    print(
        "\nCross-model:"
    )

    print(
        "Qwen gap - Gemma gap:",
        f"{observed_cross_gap:+.4f}"
    )

    print(
        "95% paired bootstrap CI:",
        f"[{cross_ci_low:.4f}, "
        f"{cross_ci_high:.4f}]"
    )

    print(
        "Randomization p:",
        f"{randomization_p:.8f}"
    )


    summary_rows.append({

        "scenario":
            scenario,

        "excluded_ids":
            ",".join(
                str(x)
                for x in sorted(
                    excluded_ids
                )
            ),

        "model":
            "Qwen-minus-Gemma language-gap difference",

        "n":
            len(data),

        "arabic_correct":
            np.nan,

        "arabic_accuracy":
            np.nan,

        "english_correct":
            np.nan,

        "english_accuracy":
            np.nan,

        "gap":
            observed_cross_gap,

        "both_correct":
            np.nan,

        "both_wrong":
            np.nan,

        "english_only":
            np.nan,

        "arabic_only":
            np.nan,

        "mcnemar_p":
            randomization_p,

        "ci_low":
            cross_ci_low,

        "ci_high":
            cross_ci_high,
    })


# ============================================================
# SAVE
# ============================================================

summary = pd.DataFrame(
    summary_rows
)


summary.to_csv(
    SUMMARY_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)


print("\n")
print("=" * 80)
print("FILES CREATED")
print("=" * 80)

print(
    "\n",
    AUDIT_OUTPUT
)

print(
    " ",
    SUMMARY_OUTPUT
)