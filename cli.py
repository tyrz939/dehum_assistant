from assistant import chat_with_assistant

history = []

print("💬 Dehumidifier Sizing Assistant (type 'exit' to quit)\n")

while True:
    user_input = input("You: ")
    if user_input.strip().lower() == "exit":
        break

    reply, history = chat_with_assistant(user_input, history)
    print(f"Assistant: {reply}\n")
