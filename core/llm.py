from groq import Groq
api_key ="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"
import os
# core/llm.py
from groq import Groq

client = Groq(api_key=api_key)

chat_completion = client.chat.completions.create(
    messages=[
        # Set an optional system message. This sets the behavior of the
        # assistant and can be used to provide specific instructions for
        # how it should behave throughout the conversation.
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        # Set a user message for the assistant to respond to.
        {
            "role": "user",
            "content": "Explain the importance of fast language models",
        }
    ],

    # The language model which will generate the completion.
    model="llama-3.3-70b-versatile"
)

# Print the completion returned by the LLM.
print(chat_completion.choices[0].message.content)