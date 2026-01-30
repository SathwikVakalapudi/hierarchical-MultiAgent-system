from groq import Groq
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
print(f"Loaded GROQ_API_KEY: {api_key}")
if not api_key:
    raise RuntimeError("GROQ_API_KEY not found in environment")

client = Groq(api_key=api_key)