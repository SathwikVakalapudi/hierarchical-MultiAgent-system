from core.message import Message
from core.protocols import FINAL_RESULT
from openai import OpenAI

api_key = "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"
"""
supervisor/executors/respond_only.py
Respond-Only Executor – FINAL PRODUCTION VERSION (January 2026)

Handles:
- General questions about the assistant's capabilities
- Explanations of how the system works
- Casual chit-chat
- Questions about email/calendar best practices
- Anything that doesn't require reading or modifying Gmail/Calendar

Uses direct LLM response with a strong system prompt for consistency and branding.
"""

from datetime import datetime
from typing import Dict, Any

from groq import Groq
from core.message import Message
from core.protocols import PLAN, EXECUTION_RESULT


class RespondOnlyExecutor:
    """
    Direct LLM response path – safe, fast, no tool access.
    Perfect for meta-questions, explanations, and general conversation.
    """

    def __init__(self, llm_client: Groq):
        self.llm = llm_client
        self.model = "llama-3.3-70b-versatile"

    def handle(self, message: Message) -> Message:
        print("\n" + "="*80)
        print("RESPOND-ONLY PHASE: Direct LLM Response")
        print("="*80 + "\n")

        if message.type != PLAN:
            raise ValueError(f"RespondOnlyExecutor expects PLAN message, got {message.type}")

        payload = message.payload or {}
        user_query = payload.get("user_query", "").strip()

        if not user_query:
            response_text = "I'm here! How can I help you today?"
        else:
            print(f"User Query: {user_query}")
            response_text = self._generate_response(user_query)

        print(f"\nAssistant Response:\n{response_text}\n")
        print("="*80)
        print("RESPOND-ONLY PHASE COMPLETE")
        print("="*80 + "\n")

        return Message(
            type=EXECUTION_RESULT,
            payload={
                "executions": [],
                "summary": "Direct response generated",
                "response_text": response_text,
                "completed_at": datetime.now().isoformat()
            }
        )

    def _generate_response(self, user_query: str) -> str:
        system_prompt = """
You are a friendly, professional, and highly capable personal AI assistant with secure access to Gmail and Google Calendar.

Key facts about you:
- You can read emails and calendar events ONLY when necessary and explicitly requested.
- You can create, update, or delete events and send emails — but ALWAYS check context first for safety.
- You never act without perceiving relevant information when modifications are involved.
- You are built with multiple safety layers: Main Planner → Perception → Planning → Execution.
- You are helpful, concise, and respectful of privacy.

Tone:
- Warm, confident, and clear
- Professional but approachable
- Use light humor when appropriate
- Always confirm actions involving changes

Common topics you can explain:
- How you safely handle calendar/email actions
- What you can do (schedule meetings, send emails, check availability, summarize inbox, etc.)
- Privacy and security practices
- General productivity tips for email and calendar

Respond naturally and conversationally. Use markdown lightly for clarity (e.g., **bold**, lists).

DO NOT offer to perform actions unless the user clearly asks — just explain capabilities.
"""

        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt.strip()},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.7,
                max_tokens=800,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"[RespondOnly] LLM call failed: {e}")
            return (
                "I'm having a little trouble thinking right now. "
                "But I'm still here — could you please try again in a moment?"
            )