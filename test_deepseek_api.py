import os
from openai import OpenAI

api_key = os.environ["DEEPSEEK_API_KEY"]

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {
            "role": "user",
            "content": "A shop has 12 boxes. Each box contains 8 pencils. How many pencils are there in total? Think step by step and end with: FINAL ANSWER: <number>"
        }
    ],
    temperature=0
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