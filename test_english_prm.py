import csv
import gc
import torch

from transformers import AutoTokenizer

from model_utils.prm_model import PRM_MODEL
from model_utils.io_utils import (
    prepare_input,
    prepare_batch_input_for_model,
    derive_step_rewards,
)


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_PATH = "Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B"
OUTPUT_FILE = "english_prm_results.csv"

STEP_TOKEN = "\n"

CATEGORIES = [
    "correct",
    "arithmetic_error",
    "logic_error",
    "completely_wrong",
]


# ============================================================
# ENGLISH DATASET
#
# This is the English translation of the SAME 20 problems
# used in test_arabic_prm.py.
#
# Each problem has exactly four versions:
#   1. correct
#   2. arithmetic_error
#   3. logic_error
#   4. completely_wrong
#
# The numerical values and error types are kept identical
# to the Arabic experiment.
# ============================================================

examples = [

    # --------------------------------------------------------
    # PROBLEM 1
    # --------------------------------------------------------

    {
        "id": 1,
        "problem": (
            "Ahmed has 20 apples. He gives 7 apples to his friend, "
            "then buys 5 more apples. How many apples does he have now?"
        ),
        "responses": {

            "correct": """
Ahmed starts with 20 apples.
He gives 7 apples to his friend, so:
20 - 7 = 13 apples.
Then he buys 5 more apples:
13 + 5 = 18 apples.
Therefore, Ahmed has 18 apples.
""",

            "arithmetic_error": """
Ahmed starts with 20 apples.
He gives 7 apples to his friend:
20 - 7 = 13 apples.
Then he buys 5 more apples:
13 + 5 = 19 apples.
Therefore, Ahmed has 19 apples.
""",

            "logic_error": """
Ahmed starts with 20 apples.
He gives 7 apples to his friend, so:
20 + 7 = 27 apples.
Then he buys 5 more apples:
27 + 5 = 32 apples.
Therefore, Ahmed has 32 apples.
""",

            "completely_wrong": """
Ahmed has 20 apples.
He gives 7 apples and then buys 5 apples.
We calculate:
20 - 7 - 5 = 8.
Therefore, he has 8 apples.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 2
    # --------------------------------------------------------

    {
        "id": 2,
        "problem": (
            "Sara has 15 books. She gives 4 books to her sister "
            "and then buys 6 new books. How many books does she have now?"
        ),
        "responses": {

            "correct": """
Sara has 15 books.
She gives 4 books to her sister:
15 - 4 = 11 books.
Then she buys 6 books:
11 + 6 = 17 books.
Therefore, she has 17 books.
""",

            "arithmetic_error": """
Sara has 15 books.
She gives 4 books:
15 - 4 = 11 books.
Then she buys 6 books:
11 + 6 = 16 books.
Therefore, she has 16 books.
""",

            "logic_error": """
Sara has 15 books.
She gives 4 books to her sister, so:
15 + 4 = 19 books.
Then she buys 6 books:
19 + 6 = 25 books.
Therefore, she has 25 books.
""",

            "completely_wrong": """
Sara has 15 books.
She gives 4 books and then buys 6 books.
We calculate:
15 - 4 - 6 = 5.
Therefore, she has 5 books.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 3
    # --------------------------------------------------------

    {
        "id": 3,
        "problem": (
            "Mohammed buys 8 pens, and he already has 12 pens at home. "
            "He gives 5 pens to his friend. How many pens does he have left?"
        ),
        "responses": {

            "correct": """
Mohammed has 12 pens.
He buys 8 more pens:
12 + 8 = 20 pens.
Then he gives 5 pens to his friend:
20 - 5 = 15 pens.
Therefore, he has 15 pens left.
""",

            "arithmetic_error": """
Mohammed has 12 pens.
He buys 8 pens:
12 + 8 = 20 pens.
Then he gives 5 pens:
20 - 5 = 16 pens.
Therefore, he has 16 pens left.
""",

            "logic_error": """
Mohammed has 12 pens.
He buys 8 pens.
Instead of adding the pens, we calculate:
12 - 8 = 4 pens.
Then he gives 5 pens:
4 - 5 = -1 pen.
Therefore, he has one pen left.
""",

            "completely_wrong": """
Mohammed has 12 pens and buys 8 pens.
Then he gives 5 pens.
We calculate:
12 + 8 + 5 = 25.
Therefore, he has 25 pens.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 4
    # --------------------------------------------------------

    {
        "id": 4,
        "problem": (
            "Layla has 30 pieces of candy. She gives 12 pieces "
            "to her friends. How many pieces are left?"
        ),
        "responses": {

            "correct": """
Layla has 30 pieces of candy.
She gives 12 pieces to her friends:
30 - 12 = 18.
Therefore, she has 18 pieces left.
""",

            "arithmetic_error": """
Layla has 30 pieces of candy.
She gives 12 pieces:
30 - 12 = 20.
Therefore, she has 20 pieces left.
""",

            "logic_error": """
Layla has 30 pieces of candy.
She gives 12 pieces to her friends, so:
30 + 12 = 42.
Therefore, she has 42 pieces left.
""",

            "completely_wrong": """
Layla has 30 pieces of candy.
She gives 12 pieces.
We calculate:
30 - 12 - 12 = 6.
Therefore, she has 6 pieces left.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 5
    # --------------------------------------------------------

    {
        "id": 5,
        "problem": (
            "Khalid has 5 boxes, with 6 balls in each box. "
            "How many balls does he have?"
        ),
        "responses": {

            "correct": """
Khalid has 5 boxes.
There are 6 balls in each box.
We calculate:
5 × 6 = 30.
Therefore, he has 30 balls.
""",

            "arithmetic_error": """
Khalid has 5 boxes.
There are 6 balls in each box.
We calculate:
5 × 6 = 35.
Therefore, he has 35 balls.
""",

            "logic_error": """
Khalid has 5 boxes.
There are 6 balls in each box.
We calculate:
5 + 6 = 11.
Therefore, he has 11 balls.
""",

            "completely_wrong": """
Khalid has 5 boxes, and each box contains 6 balls.
We calculate:
5 × 6 = 25.
Therefore, he has 25 balls.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 6
    # --------------------------------------------------------

    {
        "id": 6,
        "problem": (
            "A teacher distributes 24 pens equally among 6 students. "
            "How many pens does each student receive?"
        ),
        "responses": {

            "correct": """
The teacher has 24 pens.
The pens are distributed equally among 6 students:
24 ÷ 6 = 4.
Therefore, each student receives 4 pens.
""",

            "arithmetic_error": """
The teacher has 24 pens.
The pens are distributed among 6 students:
24 ÷ 6 = 5.
Therefore, each student receives 5 pens.
""",

            "logic_error": """
The teacher has 24 pens and 6 students.
We calculate:
24 - 6 = 18.
Therefore, each student receives 18 pens.
""",

            "completely_wrong": """
The teacher has 24 pens and 6 students.
We calculate:
24 + 6 = 30.
Therefore, each student receives 30 pens.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 7
    # --------------------------------------------------------

    {
        "id": 7,
        "problem": (
            "A pen costs 10 riyals. Ali buys 3 pens. "
            "How much does he pay?"
        ),
        "responses": {

            "correct": """
The price of one pen is 10 riyals.
Ali buys 3 pens.
We calculate:
10 × 3 = 30.
Therefore, he pays 30 riyals.
""",

            "arithmetic_error": """
The price of one pen is 10 riyals.
Ali buys 3 pens.
We calculate:
10 × 3 = 25.
Therefore, he pays 25 riyals.
""",

            "logic_error": """
The price of one pen is 10 riyals.
Ali buys 3 pens.
We calculate:
10 + 3 = 13.
Therefore, he pays 13 riyals.
""",

            "completely_wrong": """
The price of one pen is 10 riyals.
Ali buys 3 pens.
We calculate:
10 - 3 = 7.
Therefore, he pays 7 riyals.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 8
    # --------------------------------------------------------

    {
        "id": 8,
        "problem": (
            "Mary has 40 riyals. She spends 15 riyals and then "
            "receives 10 riyals. How much does she have now?"
        ),
        "responses": {

            "correct": """
Mary has 40 riyals.
She spends 15 riyals:
40 - 15 = 25.
Then she receives 10 riyals:
25 + 10 = 35.
Therefore, she has 35 riyals.
""",

            "arithmetic_error": """
Mary has 40 riyals.
She spends 15 riyals:
40 - 15 = 25.
Then she receives 10 riyals:
25 + 10 = 30.
Therefore, she has 30 riyals.
""",

            "logic_error": """
Mary has 40 riyals.
She spends 15 riyals:
40 + 15 = 55.
Then she receives 10 riyals:
55 + 10 = 65.
Therefore, she has 65 riyals.
""",

            "completely_wrong": """
Mary has 40 riyals.
She spends 15 riyals and receives 10 riyals.
We calculate:
40 - 15 - 10 = 15.
Therefore, she has 15 riyals.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 9
    # --------------------------------------------------------

    {
        "id": 9,
        "problem": (
            "Ahmed reads 7 pages every day for 5 days. "
            "How many pages does he read?"
        ),
        "responses": {

            "correct": """
Ahmed reads 7 pages every day.
The number of days is 5.
We calculate:
7 × 5 = 35.
Therefore, he reads 35 pages.
""",

            "arithmetic_error": """
Ahmed reads 7 pages every day for 5 days.
We calculate:
7 × 5 = 30.
Therefore, he reads 30 pages.
""",

            "logic_error": """
Ahmed reads 7 pages every day for 5 days.
We calculate:
7 + 5 = 12.
Therefore, he reads 12 pages.
""",

            "completely_wrong": """
Ahmed reads 7 pages every day for 5 days.
We calculate:
7 × 5 = 25.
Therefore, he reads 25 pages.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 10
    # --------------------------------------------------------

    {
        "id": 10,
        "problem": (
            "A store has 50 bottles of water. It sells 18 bottles. "
            "How many bottles are left?"
        ),
        "responses": {

            "correct": """
The store has 50 bottles.
It sells 18 bottles:
50 - 18 = 32.
Therefore, 32 bottles are left.
""",

            "arithmetic_error": """
The store has 50 bottles.
It sells 18 bottles:
50 - 18 = 35.
Therefore, 35 bottles are left.
""",

            "logic_error": """
The store has 50 bottles.
It sells 18 bottles, so:
50 + 18 = 68.
Therefore, 68 bottles are left.
""",

            "completely_wrong": """
The store has 50 bottles.
It sells 18 bottles.
We calculate:
50 - 18 - 18 = 14.
Therefore, 14 bottles are left.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 11
    # --------------------------------------------------------

    {
        "id": 11,
        "problem": (
            "Yusuf has 9 toy cars and buys 4 more cars. "
            "How many cars does he have?"
        ),
        "responses": {

            "correct": """
Yusuf has 9 toy cars.
He buys 4 more cars:
9 + 4 = 13.
Therefore, he has 13 cars.
""",

            "arithmetic_error": """
Yusuf has 9 toy cars.
He buys 4 cars:
9 + 4 = 14.
Therefore, he has 14 cars.
""",

            "logic_error": """
Yusuf has 9 toy cars.
He buys 4 more cars.
We calculate:
9 - 4 = 5.
Therefore, he has 5 cars.
""",

            "completely_wrong": """
Yusuf has 9 toy cars.
He buys 4 cars.
We calculate:
9 × 4 = 36.
Therefore, he has 36 cars.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 12
    # --------------------------------------------------------

    {
        "id": 12,
        "problem": (
            "There are 6 rows of trees on a farm, with 8 trees "
            "in each row. How many trees are there on the farm?"
        ),
        "responses": {

            "correct": """
There are 6 rows of trees.
There are 8 trees in each row.
We calculate:
6 × 8 = 48.
Therefore, there are 48 trees.
""",

            "arithmetic_error": """
There are 6 rows.
There are 8 trees in each row.
We calculate:
6 × 8 = 42.
Therefore, there are 42 trees.
""",

            "logic_error": """
There are 6 rows.
There are 8 trees in each row.
We calculate:
6 + 8 = 14.
Therefore, there are 14 trees.
""",

            "completely_wrong": """
There are 6 rows with 8 trees in each row.
We calculate:
8 - 6 = 2.
Therefore, there are only 2 trees.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 13
    # --------------------------------------------------------

    {
        "id": 13,
        "problem": (
            "Salim has 100 riyals. He buys a toy for 35 riyals. "
            "How many riyals does he have left?"
        ),
        "responses": {

            "correct": """
Salim has 100 riyals.
He buys a toy for 35 riyals.
We calculate:
100 - 35 = 65.
Therefore, he has 65 riyals left.
""",

            "arithmetic_error": """
Salim has 100 riyals.
He buys a toy for 35 riyals.
We calculate:
100 - 35 = 75.
Therefore, he has 75 riyals left.
""",

            "logic_error": """
Salim has 100 riyals.
He buys a toy for 35 riyals.
We calculate:
100 + 35 = 135.
Therefore, he has 135 riyals left.
""",

            "completely_wrong": """
Salim has 100 riyals.
He buys a toy for 35 riyals.
We calculate:
100 - 35 - 35 = 30.
Therefore, he has 30 riyals left.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 14
    # --------------------------------------------------------

    {
        "id": 14,
        "problem": (
            "A car travels 60 kilometers in two hours at the same speed. "
            "How many kilometers does it travel per hour?"
        ),
        "responses": {

            "correct": """
The car travels 60 kilometers in two hours.
We divide the distance by the time:
60 ÷ 2 = 30.
Therefore, its speed is 30 kilometers per hour.
""",

            "arithmetic_error": """
The car travels 60 kilometers in two hours.
We calculate:
60 ÷ 2 = 40.
Therefore, its speed is 40 kilometers per hour.
""",

            "logic_error": """
The car travels 60 kilometers in two hours.
We calculate:
60 × 2 = 120.
Therefore, its speed is 120 kilometers per hour.
""",

            "completely_wrong": """
The car travels 60 kilometers in two hours.
We calculate:
60 - 2 = 58.
Therefore, its speed is 58 kilometers per hour.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 15
    # --------------------------------------------------------

    {
        "id": 15,
        "problem": (
            "Ahmed has 3 bags, with 10 oranges in each bag. "
            "He gives 5 oranges to his brother. How many oranges are left?"
        ),
        "responses": {

            "correct": """
Ahmed has 3 bags.
There are 10 oranges in each bag:
3 × 10 = 30 oranges.
He gives 5 oranges to his brother:
30 - 5 = 25.
Therefore, 25 oranges are left.
""",

            "arithmetic_error": """
Ahmed has 3 bags.
There are 10 oranges in each bag:
3 × 10 = 30.
He gives 5 oranges:
30 - 5 = 20.
Therefore, 20 oranges are left.
""",

            "logic_error": """
Ahmed has 3 bags.
There are 10 oranges in each bag:
3 + 10 = 13.
Then he gives 5 oranges:
13 - 5 = 8.
Therefore, 8 oranges are left.
""",

            "completely_wrong": """
Ahmed has 3 bags with 10 oranges in each bag.
Then he gives 5 oranges.
We calculate:
3 × 10 + 5 = 35.
Therefore, 35 oranges are left.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 16
    # --------------------------------------------------------

    {
        "id": 16,
        "problem": (
            "A school has 80 students. 20 new students join the school. "
            "How many students are there now?"
        ),
        "responses": {

            "correct": """
The school has 80 students.
20 new students join:
80 + 20 = 100.
Therefore, there are 100 students.
""",

            "arithmetic_error": """
The school has 80 students.
20 students join:
80 + 20 = 90.
Therefore, there are 90 students.
""",

            "logic_error": """
The school has 80 students.
20 new students join the school.
We calculate:
80 - 20 = 60.
Therefore, there are 60 students.
""",

            "completely_wrong": """
The school has 80 students.
20 students join.
We calculate:
80 × 20 = 1600.
Therefore, there are 1600 students.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 17
    # --------------------------------------------------------

    {
        "id": 17,
        "problem": (
            "Fatima has 45 flowers and divides them equally among "
            "5 vases. How many flowers are in each vase?"
        ),
        "responses": {

            "correct": """
Fatima has 45 flowers.
She divides them equally among 5 vases:
45 ÷ 5 = 9.
Therefore, there are 9 flowers in each vase.
""",

            "arithmetic_error": """
Fatima has 45 flowers.
She divides them among 5 vases:
45 ÷ 5 = 8.
Therefore, there are 8 flowers in each vase.
""",

            "logic_error": """
Fatima has 45 flowers and 5 vases.
We calculate:
45 - 5 = 40.
Therefore, there are 40 flowers in each vase.
""",

            "completely_wrong": """
Fatima has 45 flowers and 5 vases.
We calculate:
45 + 5 = 50.
Therefore, there are 50 flowers in each vase.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 18
    # --------------------------------------------------------

    {
        "id": 18,
        "problem": (
            "Khalid buys 4 notebooks. Each notebook costs 7 riyals. "
            "How much does he pay?"
        ),
        "responses": {

            "correct": """
Khalid buys 4 notebooks.
Each notebook costs 7 riyals.
We calculate:
4 × 7 = 28.
Therefore, he pays 28 riyals.
""",

            "arithmetic_error": """
Khalid buys 4 notebooks.
Each notebook costs 7 riyals.
We calculate:
4 × 7 = 24.
Therefore, he pays 24 riyals.
""",

            "logic_error": """
Khalid buys 4 notebooks.
Each notebook costs 7 riyals.
We calculate:
4 + 7 = 11.
Therefore, he pays 11 riyals.
""",

            "completely_wrong": """
Khalid buys 4 notebooks.
Each notebook costs 7 riyals.
We calculate:
7 - 4 = 3.
Therefore, he pays 3 riyals.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 19
    # --------------------------------------------------------

    {
        "id": 19,
        "problem": (
            "Noura has 25 balloons. 9 balloons burst. "
            "How many balloons are left?"
        ),
        "responses": {

            "correct": """
Noura has 25 balloons.
9 balloons burst:
25 - 9 = 16.
Therefore, 16 balloons are left.
""",

            "arithmetic_error": """
Noura has 25 balloons.
9 balloons burst:
25 - 9 = 15.
Therefore, 15 balloons are left.
""",

            "logic_error": """
Noura has 25 balloons.
9 balloons burst:
25 + 9 = 34.
Therefore, 34 balloons are left.
""",

            "completely_wrong": """
Noura has 25 balloons.
9 balloons burst.
We calculate:
25 - 9 - 9 = 7.
Therefore, 7 balloons are left.
"""
        }
    },


    # --------------------------------------------------------
    # PROBLEM 20
    # --------------------------------------------------------

    {
        "id": 20,
        "problem": (
            "A store has 7 boxes, with 12 bottles in each box. "
            "How many bottles does the store have?"
        ),
        "responses": {

            "correct": """
The store has 7 boxes.
There are 12 bottles in each box.
We calculate:
7 × 12 = 84.
Therefore, the store has 84 bottles.
""",

            "arithmetic_error": """
The store has 7 boxes.
There are 12 bottles in each box.
We calculate:
7 × 12 = 80.
Therefore, the store has 80 bottles.
""",

            "logic_error": """
The store has 7 boxes.
There are 12 bottles in each box.
We calculate:
7 + 12 = 19.
Therefore, the store has 19 bottles.
""",

            "completely_wrong": """
The store has 7 boxes.
There are 12 bottles in each box.
We calculate:
12 - 7 = 5.
Therefore, the store has 5 bottles.
"""
        }
    },
]


# ============================================================
# DATASET VALIDATION
# ============================================================

print("=" * 70)
print("ENGLISH PRM LARGE-SCALE EVALUATION")
print("=" * 70)

print()
print("Validating dataset...")

if len(examples) != 20:
    raise ValueError(
        f"Expected 20 problems, but found {len(examples)}"
    )

for example in examples:

    if set(example["responses"].keys()) != set(CATEGORIES):
        raise ValueError(
            f"Problem {example['id']} does not contain "
            f"all four required categories."
        )

print("Dataset validation successful.")
print("Problems:", len(examples))
print("Categories per problem:", len(CATEGORIES))
print("Expected evaluations:", len(examples) * len(CATEGORIES))


# ============================================================
# LOAD TOKENIZER
# ============================================================

print()
print("Loading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True,
)

print("Tokenizer loaded.")


# ============================================================
# MEMORY CLEANUP BEFORE MODEL LOADING
# ============================================================

gc.collect()

if torch.cuda.is_available():
    torch.cuda.empty_cache()


# ============================================================
# LOAD MODEL
# ============================================================

print()
print("Loading PRM model...")
print("Using device_map='auto'.")

model = PRM_MODEL.from_pretrained(
    MODEL_PATH,
    device_map="auto",
).eval()

print("Model loaded successfully.")

try:
    model_device = (
        model.pretrained_model
        .model
        .embed_tokens
        .weight
        .device
    )
except Exception:
    model_device = next(model.parameters()).device

print("Model input device:", model_device)


# ============================================================
# EVALUATION
# ============================================================

results = []

total_evaluations = len(examples) * len(CATEGORIES)

current_evaluation = 0

print()
print("=" * 70)
print("STARTING ENGLISH PRM EVALUATION")
print("=" * 70)


for example in examples:

    print()
    print(
        f"Problem {example['id']}/{len(examples)}"
    )

    for category in CATEGORIES:

        current_evaluation += 1

        print(
            f"  [{current_evaluation}/{total_evaluations}] "
            f"{category}"
        )

        problem = example["problem"]
        response = example["responses"][category]

        try:

            # ------------------------------------------------
            # Prepare input
            # ------------------------------------------------

            processed = prepare_input(
                problem,
                response,
                tokenizer=tokenizer,
                step_token=STEP_TOKEN,
            )

            input_ids, steps, reward_flags = processed

            # ------------------------------------------------
            # Prepare batch
            # ------------------------------------------------

            input_ids, attention_mask, reward_flags = (
                prepare_batch_input_for_model(
                    [input_ids],
                    [reward_flags],
                    tokenizer.pad_token_id,
                )
            )

            # ------------------------------------------------
            # Move input tensors to model input device
            # ------------------------------------------------

            input_ids = input_ids.to(model_device)
            attention_mask = attention_mask.to(model_device)

            # ------------------------------------------------
            # PRM inference
            # ------------------------------------------------

            with torch.no_grad():

                _, _, rewards = model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    return_probs=True,
                )

            # ------------------------------------------------
            # Extract step-level rewards
            # ------------------------------------------------

            step_rewards = derive_step_rewards(
                rewards,
                reward_flags,
            )[0]

            scores = [
                float(x)
                for x in step_rewards
            ]

            if len(scores) == 0:
                raise ValueError(
                    "No step-level scores were produced."
                )

            # ------------------------------------------------
            # Calculate statistics
            # ------------------------------------------------

            average_score = sum(scores) / len(scores)
            minimum_score = min(scores)
            maximum_score = max(scores)

            # ------------------------------------------------
            # Save result
            # ------------------------------------------------

            results.append(
                {
                    "problem_id": example["id"],
                    "category": category,
                    "problem": problem,
                    "response": response.strip(),
                    "num_steps": len(scores),
                    "average_score": average_score,
                    "minimum_score": minimum_score,
                    "maximum_score": maximum_score,
                    "step_scores": " ".join(
                        f"{x:.4f}" for x in scores
                    ),
                }
            )

            print(
                f"      Average: {average_score:.4f} | "
                f"Min: {minimum_score:.4f} | "
                f"Max: {maximum_score:.4f}"
            )

            # ------------------------------------------------
            # Memory cleanup
            # ------------------------------------------------

            del processed
            del input_ids
            del attention_mask
            del rewards

            gc.collect()

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        except Exception as e:

            print()
            print(
                f"      ERROR in problem {example['id']} "
                f"({category})"
            )
            print(f"      {type(e).__name__}: {e}")
            print()

            # Continue with the next evaluation
            continue


# ============================================================
# SAVE RESULTS
# ============================================================

print()
print("=" * 70)
print("SAVING RESULTS")
print("=" * 70)

if len(results) == 0:
    raise RuntimeError(
        "No successful evaluations were produced."
    )

fieldnames = [
    "problem_id",
    "category",
    "problem",
    "response",
    "num_steps",
    "average_score",
    "minimum_score",
    "maximum_score",
    "step_scores",
]

with open(
    OUTPUT_FILE,
    "w",
    newline="",
    encoding="utf-8-sig",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames,
    )

    writer.writeheader()
    writer.writerows(results)


# ============================================================
# FINAL RESULTS
# ============================================================

print()
print("=" * 70)
print("FINAL RESULTS")
print("=" * 70)

print()
print("Successful evaluations:", len(results))
print("Expected evaluations:", total_evaluations)


for category in CATEGORIES:

    category_results = [
        r
        for r in results
        if r["category"] == category
    ]

    if not category_results:
        continue

    average_score = sum(
        r["average_score"]
        for r in category_results
    ) / len(category_results)

    average_minimum = sum(
        r["minimum_score"]
        for r in category_results
    ) / len(category_results)

    average_maximum = sum(
        r["maximum_score"]
        for r in category_results
    ) / len(category_results)

    print()
    print(category.upper())
    print("-" * 40)
    print(
        f"Examples       : {len(category_results)}"
    )
    print(
        f"Average score  : {average_score:.4f}"
    )
    print(
        f"Average minimum: {average_minimum:.4f}"
    )
    print(
        f"Average maximum: {average_maximum:.4f}"
    )


# ============================================================
# CORRECT VS INCORRECT
# ============================================================

correct_results = [
    r
    for r in results
    if r["category"] == "correct"
]

incorrect_results = [
    r
    for r in results
    if r["category"] != "correct"
]

if correct_results and incorrect_results:

    correct_average = sum(
        r["average_score"]
        for r in correct_results
    ) / len(correct_results)

    incorrect_average = sum(
        r["average_score"]
        for r in incorrect_results
    ) / len(incorrect_results)

    difference = (
        correct_average - incorrect_average
    )

    print()
    print("=" * 70)
    print("CORRECT VS INCORRECT")
    print("=" * 70)

    print()
    print(
        f"Correct examples average   : "
        f"{correct_average:.4f}"
    )

    print(
        f"Incorrect examples average : "
        f"{incorrect_average:.4f}"
    )

    print(
        f"Difference                  : "
        f"{difference:+.4f}"
    )


# ============================================================
# CHECK FOR COMPLETE DATASET
# ============================================================

print()
print("=" * 70)
print("DATASET COMPLETENESS CHECK")
print("=" * 70)

expected = {
    (example["id"], category)
    for example in examples
    for category in CATEGORIES
}

actual = {
    (r["problem_id"], r["category"])
    for r in results
}

missing = expected - actual

if missing:

    print()
    print(
        f"WARNING: {len(missing)} evaluations are missing."
    )

    for problem_id, category in sorted(missing):
        print(
            f"  Missing: Problem {problem_id} - {category}"
        )

else:

    print()
    print("SUCCESS: All 80 evaluations completed.")


# ============================================================
# COMPLETE
# ============================================================

print()
print("=" * 70)
print("ENGLISH PRM EVALUATION COMPLETE")
print("=" * 70)

print()
print("Results saved to:")
print(OUTPUT_FILE)

print()
print("Next step:")
print("Run compare_arabic_english.py")