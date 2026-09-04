import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["NOVITA_API_KEY"],
    base_url="https://api.novita.ai/openai"
)

response = client.chat.completions.create(
    model="qwen/qwen3.5-27b",
    messages=[
        {
            "role": "user",
            "content": (
                "A shop has 12 boxes. Each box contains 8 pencils. "
                "How many pencils are there in total? "
                "Think step by step and end with: FINAL ANSWER: <number>"
            )
        }
    ],
    temperature=0,
    max_tokens=512
)

print("MODEL:", response.model)
print()
print("RESPONSE:")
print(response.choices[0].message.content)

if response.usage:
    print()
    print("TOKEN USAGE:")
    print("Input tokens:", response.usage.prompt_tokens)
    print("Output tokens:", response.usage.completion_tokens)
    print("Total tokens:", response.usage.total_tokens)