import openai
import os
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_prompt():
    with open("prompt_template.txt", "r") as f:
        return f.read()

def chat_with_assistant(user_input, history=[]):
    system_prompt = load_prompt()
    messages = [{"role": "system", "content": system_prompt}] + history
    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=messages
    )

    reply = response.choices[0].message.content
    history.append({"role": "user", "content": user_input})
    history.append({"role": "assistant", "content": reply})
    return reply, history
