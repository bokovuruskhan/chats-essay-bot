from config import openai


def get_essay(prompt, dialog):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user",
             "content": f"{prompt}:\n{dialog}"},
        ]
    )
    return response.choices[0].message.content
