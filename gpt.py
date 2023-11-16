from openai import OpenAI

from config import api_key

client = OpenAI(api_key=api_key)


def get_essay(prompt, dialog):
    response = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "user",
             "content": f"{prompt}:\n{dialog}"}
        ]
    )
    return response.choices[0].message.content