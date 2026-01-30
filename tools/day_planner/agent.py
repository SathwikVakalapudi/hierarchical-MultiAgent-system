"""
agents/day_planner.py - Intelligent Day Scheduling Agent

Receives tasks + context from PlannerAgent and produces concrete add_event calls.
Handles conflicts, priorities, time slots, and working hours.
"""

import json
from datetime import datetime

from core.message import Message
from core.protocols import PLAN  # ← Critical: returns PLAN, not EXECUTION_RESULT
from .utils import clean_llm_output, validate_day_plan


DAY_PLANNER_SYSTEM_PROMPT = """
You are an Intelligent Day Planning Agent.

CURRENT DATE AND TIME: {current_datetime}

Your job is to schedule the requested tasks on the given day while respecting:
- Existing calendar events (DO NOT overlap or move them)
- Working hours
- Task priorities (high > medium > low)
- Realistic time blocks (e.g., 30–120 min per task)

STRICT RULES:
- Output ONLY valid JSON
- Every scheduled task MUST have:
  - title
  - start_datetime (YYYY-MM-DDTHH:MM)
  - end_datetime (YYYY-MM-DDTHH:MM)
  - priority ("high"|"medium"|"low")
- Use 24-hour format, no seconds
- No overlaps with existing events
- Stay within working_hours.start to working_hours.end
- Do not invent or modify existing events
- If a task cannot fit → put in unscheduled_tasks with clear reason
- Prefer morning for high-priority, afternoon/evening for lower

Output format:
{
  "scheduled_tasks": [
    {
      "title": "string",
      "start_datetime": "YYYY-MM-DDTHH:MM",
      "end_datetime": "YYYY-MM-DDTHH:MM",
      "priority": "high|medium|low"
    }
  ],
  "unscheduled_tasks": [
    {
      "title": "string",
      "reason": "string"
    }
  ]
}
""".strip()


class DayPlannerAgent:
    """
    Intelligent scheduler that turns vague tasks into precise calendar events.
    Called as a tool by PlannerAgent when complex scheduling is needed.
    """

    def __init__(self, llm_client):
        self.llm = llm_client
        self.model = "llama-3.2-90b-vision-preview"  # Best for structured reasoning

    def handle(self, message: Message) -> Message:
        print("\n================ DAY PLANNER AGENT START ================\n")

        payload = message.payload or {}
        required = {"tasks", "existing_events", "day", "working_hours"}
        missing = required - payload.keys()
        if missing:
            return self._error("INVALID_INPUT", f"Missing: {missing}")

        current_datetime = datetime.now().isoformat()

        llm_input = {
            "day": payload["day"],
            "working_hours": payload["working_hours"],
            "existing_events": payload["existing_events"],
            "tasks": payload["tasks"],
            "current_datetime": current_datetime,
        }

        system_prompt = DAY_PLANNER_SYSTEM_PROMPT.format(current_datetime=current_datetime)

        print("Day Planning Input:")
        print(json.dumps(llm_input, indent=2))

        # First attempt
        schedule = self._call_llm(system_prompt, llm_input)
        if isinstance(schedule, Message):
            return schedule

        # Validate and repair if needed
        error = validate_day_plan(schedule)
        if error:
            print(f"Validation failed: {error}")
            correction_prompt = system_prompt + f"\n\nFIX THIS ERROR:\n{error}\nOutput valid JSON only."
            schedule = self._call_llm(correction_prompt, llm_input)
            if isinstance(schedule, Message):
                return schedule
            if validate_day_plan(schedule):
                return self._error("INVALID_PLAN_AFTER_REPAIR", "Could not fix scheduling issues")

        print("Final Schedule Generated:")
        print(json.dumps(schedule, indent=2))

        # Convert scheduled tasks → add_event tool calls
        tool_calls = []
        for task in schedule.get("scheduled_tasks", []):
            tool_calls.append({
                "name": "add_event",
                "arguments": {
                    "summary": task["title"],
                    "start_datetime": task["start_datetime"],
                    "end_datetime": task["end_datetime"],
                    "timezone": "Asia/Kolkata"
                }
            })

        # Log unscheduled
        unscheduled = schedule.get("unscheduled_tasks", [])
        if unscheduled:
            print("Unscheduled tasks:")
            for t in unscheduled:
                print(f"  - {t['title']}: {t['reason']}")

        print("\n================ DAY PLANNER AGENT END ==================\n")

        # Return PLAN message with tool calls for ToolExecutor
        return Message(
            PLAN,
            {
                "tool_calls": tool_calls,
                "unscheduled_tasks": unscheduled  # optional: for user feedback later
            }
        )

    def _call_llm(self, system_prompt: str, llm_input: dict):
        print("Calling LLM for day planning...")
        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(llm_input)},
                ],
                temperature=0.0,
                max_tokens=1000,
            )
        except Exception as e:
            return self._error("LLM_FAILED", str(e))

        raw = response.choices[0].message.content
        print("Raw LLM Output:")
        print(raw)

        cleaned = clean_llm_output(raw)
        print("Cleaned Output:")
        print(cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            return self._error("INVALID_JSON", f"Parse failed: {e}\nRaw: {raw}")

    def _error(self, error_type: str, message: str) -> Message:
        print(f"DAY PLANNER ERROR [{error_type}]: {message}")
        return Message(
            PLAN,
            {
                "tool_calls": [],
                "error": f"{error_type}: {message}"
            }
        )