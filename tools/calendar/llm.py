import time
from datetime import datetime, timedelta
from openai import OpenAI
api_key = "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"
client = OpenAI(api_key=api_key)

def rewrite_query(user_query: str, history: list[str] = None, date: str = None) -> str:
    if not history:
        return user_query  # ✅ fallback to original input

    if len(history) > 5:
        history = history[-5:]

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""
    You are an expert calendar assistant. Rewrite the user's query to explicitly include the date.
    User Query: "{user_query}"
    Current Date: "{date}"
    History: {history}
    Rewritten Query:
    """
    print(f"[DEBUG] Rewrite Prompt: {prompt}")

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": "Rewrite queries to include explicit date context."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_output_tokens=150,
    )

    rewritten_query = response.output_text
    print(f"[DEBUG] Rewritten User Message: {rewritten_query}")
    return rewritten_query
