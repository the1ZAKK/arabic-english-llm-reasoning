import json
import random
from collections import defaultdict, Counter
from pathlib import Path


SEED = 42
DEV_PAIRS = 10

DATA_DIR = Path(
    "research/prm_arabic_english/data"
)

INPUT_FILE = DATA_DIR / "pilot_all.jsonl"
TRAIN_FILE = DATA_DIR / "pilot_train.jsonl"
DEV_FILE = DATA_DIR / "pilot_dev.jsonl"


random.seed(SEED)


# ============================================================
# LOAD DATA
# ============================================================

records = []

with INPUT_FILE.open(
    "r",
    encoding="utf-8",
) as f:

    for line in f:

        if line.strip():

            records.append(
                json.loads(line)
            )


# ============================================================
# GROUP BY PAIR ID
# ============================================================

pairs = defaultdict(list)

for record in records:

    pairs[
        record["pair_id"]
    ].append(record)


print("=" * 70)
print("ARABICPRM PILOT TRAIN/DEV SPLIT")
print("=" * 70)

print(f"\nTotal records : {len(records)}")
print(f"Total pairs   : {len(pairs)}")


# ============================================================
# VALIDATE PAIRS
# ============================================================

for pair_id, pair_records in pairs.items():

    if len(pair_records) != 2:

        raise ValueError(
            f"{pair_id} has "
            f"{len(pair_records)} records "
            f"instead of 2."
        )

    variants = {
        r["variant"]
        for r in pair_records
    }

    if variants != {
        "correct",
        "incorrect",
    }:

        raise ValueError(
            f"{pair_id} does not contain "
            f"one correct and one incorrect record."
        )


# ============================================================
# GROUP PAIRS BY ERROR CATEGORY
# ============================================================

category_pairs = defaultdict(list)

for pair_id, pair_records in pairs.items():

    wrong_record = next(
        r
        for r in pair_records
        if r["variant"] == "incorrect"
    )

    category = wrong_record["error_type"]

    category_pairs[
        category
    ].append(pair_id)


for category in category_pairs:

    random.shuffle(
        category_pairs[category]
    )


# ============================================================
# STRATIFIED DEV ALLOCATION
# ============================================================

total_pairs = len(pairs)

allocation = {}

remainders = []


for category, pair_ids in category_pairs.items():

    ideal = (
        len(pair_ids)
        * DEV_PAIRS
        / total_pairs
    )

    base = int(ideal)

    allocation[category] = base

    remainders.append(
        (
            ideal - base,
            category,
        )
    )


allocated = sum(
    allocation.values()
)


remaining = (
    DEV_PAIRS
    - allocated
)


remainders.sort(
    key=lambda x: (
        -x[0],
        x[1],
    )
)


for _, category in remainders[:remaining]:

    allocation[category] += 1


# ============================================================
# SELECT DEV PAIRS
# ============================================================

dev_pair_ids = set()


for category in sorted(
    category_pairs
):

    count = allocation[
        category
    ]

    selected = (
        category_pairs[category][
            :count
        ]
    )

    dev_pair_ids.update(
        selected
    )


train_pair_ids = (
    set(pairs.keys())
    - dev_pair_ids
)


# ============================================================
# CREATE SPLITS
# ============================================================

train_records = []
dev_records = []


for record in records:

    if (
        record["pair_id"]
        in dev_pair_ids
    ):

        dev_records.append(
            record
        )

    else:

        train_records.append(
            record
        )


# ============================================================
# SAFETY CHECK: NO LEAKAGE
# ============================================================

train_pairs_check = {
    r["pair_id"]
    for r in train_records
}

dev_pairs_check = {
    r["pair_id"]
    for r in dev_records
}


overlap = (
    train_pairs_check
    & dev_pairs_check
)


if overlap:

    raise RuntimeError(
        f"PAIR LEAKAGE DETECTED: "
        f"{sorted(overlap)}"
    )


# ============================================================
# WRITE FILES
# ============================================================

def write_jsonl(
    path,
    rows,
):

    with path.open(
        "w",
        encoding="utf-8",
    ) as f:

        for row in rows:

            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )


write_jsonl(
    TRAIN_FILE,
    train_records,
)

write_jsonl(
    DEV_FILE,
    dev_records,
)


# ============================================================
# SUMMARY
# ============================================================

print("\nSplit summary")
print("-" * 40)

print(
    f"Train pairs   : "
    f"{len(train_pair_ids)}"
)

print(
    f"Train records : "
    f"{len(train_records)}"
)

print(
    f"Dev pairs     : "
    f"{len(dev_pair_ids)}"
)

print(
    f"Dev records   : "
    f"{len(dev_records)}"
)


print("\nDev error categories")
print("-" * 40)

dev_categories = Counter(
    r["error_type"]
    for r in dev_records
    if r["variant"] == "incorrect"
)

for category, count in sorted(
    dev_categories.items()
):

    print(
        f"{category:<30} "
        f"{count}"
    )


print("\nLeakage check")
print("-" * 40)

print(
    "Train/dev pair overlap:",
    len(overlap)
)


print("\nFiles written:")

print(
    " ",
    TRAIN_FILE,
)

print(
    " ",
    DEV_FILE,
)


print("\n" + "=" * 70)
print(
    "SUCCESS: Leakage-safe "
    "train/dev split created."
)
print("=" * 70)