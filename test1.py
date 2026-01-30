
# Groq
from groq import Groq
api_key ="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"
"""
supervisor/executors/test_perceive_plan_act.py

Comprehensive REAL-WORLD tests for PerceivePlanActExecutor
Uses actual tools (Calendar + Gmail) – NO MOCKS

Run with:
    python supervisor/executors/test_perceive_plan_act.py
"""

import os
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from groq import Groq
from core.message import Message
from core.protocols import PLAN
from supervisor.executors.perceive_plan_act import PerceivePlanActExecutor

# Load your Groq client
client = Groq(api_key=api_key)
import os
from groq import Groq
from core.message import Message
from core.protocols import USER
from supervisor.agent import SupervisorAgent


supervisor = SupervisorAgent(client)

queries = [
    "What can you do?",
    "What's on my calendar today?",
    "Schedule a team meeting next Tuesday at 11 AM and email the team",
    "Hi! How are you?",
    "Send an email to john@example.com saying hello",
]

for q in queries:
    msg = Message(type=USER, payload={"text": q})
    response = supervisor.handle(msg)
    print("Response:", response.payload.get("response_text", response.payload.get("summary")))
    print("-" * 80)