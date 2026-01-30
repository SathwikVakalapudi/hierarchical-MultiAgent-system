# planner/agent.py
# Final Production-Ready PlannerAgent – December 2025
# Best-Effort, Fast & Resilient Design
# Always delegates to specialist agents immediately with current context (even if empty)

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

from groq import Groq
from core.message import Message
from core.protocols import CONTEXT_FOR_PLANNING, PLAN


class PlannerAgent:
    """
    Mid-Level Orchestrator – Optimized for Speed and Reliability
    - Extracts calendar and email tasks from user query
    - Immediately delegates to specialist agents
    - Uses available observations (falls back to empty lists if none)
    - No forced fetching → no delays, no unnecessary API calls
    """

    def __init__(self, llm_client: Groq):
        self.llm = llm_client
        self.model = "llama-3.3-70b-versatile"

        # Shared preferences passed to agents
        self.timezone = "Asia/Kolkata"
        self.default_event_duration_minutes = 60
        self.working_hours = {"start": "06:00", "end": "23:59"}

    def handle(self, message: Message) -> Message:
        if message.type != CONTEXT_FOR_PLANNING:
            raise ValueError("PlannerAgent only accepts CONTEXT_FOR_PLANNING messages")

        payload = message.payload or {}
        user_query = payload.get("user_query", "").strip()
        observations = payload.get("observations", {})

        if not user_query:
            return Message(PLAN, {"tool_calls": [], "summary": "No query provided."})

        print(f"\n[PlannerAgent] Processing: {user_query}")
        context_status = list(observations.keys()) if observations else "none"
        print(f"[PlannerAgent] Available context: {context_status}")

        plan = self._generate_plan(user_query, observations)

        print("\n[PlannerAgent] FINAL PLAN:")
        print(json.dumps(plan, indent=2, ensure_ascii=False))

        return Message(PLAN, plan)

    def _generate_plan(self, user_query: str, observations: Dict[str, Any]) -> Dict[str, Any]:
        extracted = self._extract_tasks(user_query)

        calendar_tasks: List[str] = extracted.get("calendar_tasks", [])
        email_tasks: List[str] = extracted.get("email_tasks", [])
        scope_days: List[str] = extracted.get("scope_days", [])

        tool_calls: List[Dict[str, Any]] = []
        summary_parts: List[str] = []

        # === Calendar Tasks ===
        if calendar_tasks:
            input_data = {
                "user_query": user_query,
                "calendar_tasks": calendar_tasks,
                "existing_events": observations.get("calendar_events", []),  # empty if missing
                "scope_days": scope_days,
                "preferences": {
                    "timezone": self.timezone,
                    "default_event_duration_minutes": self.default_event_duration_minutes,
                    "working_hours": self.working_hours
                }
            }
            tool_calls.append({
                "name": "run_calendar_agent",
                "arguments": {"input_data": input_data}
            })
            context_note = "with full context" if observations.get("calendar_events") else "with limited/no context"
            summary_parts.append(f"Delegating calendar tasks to CalendarAgent ({context_note}).")

        # === Email Tasks ===
        if email_tasks:
            input_data = {
                "user_query": user_query,
                "email_tasks": email_tasks,
                "observations": observations  # may include gmail_threads or not
            }
            tool_calls.append({
                "name": "run_email_agent",
                "arguments": {"input_data": input_data}
            })
            context_note = "with full context" if observations.get("gmail_threads") else "with limited/no context"
            summary_parts.append(f"Delegating email tasks to EmailAgent ({context_note}).")

        summary = " | ".join(summary_parts) if summary_parts else "No tasks identified."

        return {
            "tool_calls": tool_calls,
            "summary": summary
        }

    def _extract_tasks(self, user_query: str) -> Dict[str, Any]:
        today = datetime.now().strftime("%Y-%m-%d")
        next_7_days = [(datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(8)]

        prompt = f"""
You are an expert task extractor for a personal assistant with calendar and email access.

User request: "{user_query}"

Extract:
- calendar_tasks: list of calendar actions (e.g., "add gym tomorrow at 6pm", "cancel dentist")
- email_tasks: list of email actions (e.g., "send hello to mom@gmail.com", "reply to John's email")
- scope_days: relevant YYYY-MM-DD dates (use today={today}, default to next 7 days if unclear)

Output ONLY valid JSON:
{{
  "calendar_tasks": [],
  "email_tasks": [],
  "scope_days": []
}}
""".strip()

        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content.strip()
            result = json.loads(raw)

            return {
                "calendar_tasks": result.get("calendar_tasks", []),
                "email_tasks": result.get("email_tasks", []),
                "scope_days": result.get("scope_days", [])
            }
        except Exception as e:
            print(f"[PlannerAgent] Task extraction failed: {e}")
            return {
                "calendar_tasks": [],
                "email_tasks": [],
                "scope_days": []
            }