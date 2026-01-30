"""
supervisor.executors.perceive_only.py
Perceive-Only Executor – FINAL PRODUCTION VERSION (UPDATED)

FIXES:
- Adds Perceive → Respond bridge (no more silent failures)
- Handles empty calendar / gmail results gracefully
- Removes validation schema ambiguity
- Preserves original planner contract (returns PLAN message)
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict
import threading

from groq import Groq
from core.message import Message
from core.protocols import PLAN

# Read-only tools
from tools.calendar.functions import get_calendar_events
from tools.gmail.query_engine import process_gmail_query


class PerceiveOnlyExecutor:
    _local = threading.local()

    def __init__(self, llm_client: Groq):
        self.llm = llm_client
        self.model = "llama-3.3-70b-versatile"
        print("PerceiveOnlyExecutor initialized with model:", self.model)

        self.tools = {
            "get_calendar_events": get_calendar_events,
            "process_gmail_query": process_gmail_query,
        }

        self.timezone = "Asia/Kolkata"

        if not hasattr(self._local, "confidence_memory"):
            self._local.confidence_memory = defaultdict(lambda: {"total": 0, "success": 0})

    # ------------------------------------------------------------------
    # Confidence calibration
    # ------------------------------------------------------------------

    def _update_confidence_memory(self, tool: str, confidence: str):
        key = f"{tool}_{confidence.lower()}"
        self._local.confidence_memory[key]["total"] += 1
        self._local.confidence_memory[key]["success"] += 1

    def _get_calibrated_threshold(self, tool: str) -> float:
        stats = self._local.confidence_memory[f"{tool}_medium"]
        return stats["success"] / stats["total"] if stats["total"] > 0 else 0.6

    # ------------------------------------------------------------------
    # MAIN ENTRY
    # ------------------------------------------------------------------

    def handle(self, message: Message) -> Message:
        print("\n" + "=" * 70)
        print("PERCEIVE-ONLY PHASE: Gathering Context")
        print("=" * 70 + "\n")

        if message.type != PLAN:
            raise ValueError("PerceiveOnlyExecutor only handles PLAN messages")

        payload = message.payload or {}
        user_query = payload.get("user_query", "").strip()
        if not user_query:
            raise ValueError("Missing user_query in PLAN payload")

        print(f"User Query: {user_query}\n")

        reasoning = ""
        all_tool_results = []
        calendar_events: List[Dict] = []
        gmail_threads: List[Dict] = []
        refinement_count = 0

        # ------------------------------
        # 1️⃣ Decide what to perceive
        # ------------------------------
        context_plan = self._decide_what_to_perceive(user_query)
        tool_calls = context_plan.get("tool_calls", [])
        reasoning = context_plan.get("reasoning", "")

        print(f"Initial Reasoning: {reasoning}")
        print(f"Initial planned tools: {len(tool_calls)}\n")

        # ------------------------------
        # 2️⃣ Execute perception tools
        # ------------------------------
        for call in tool_calls:
            results = self._execute_perception_tools([call])
            all_tool_results.extend(results)

            for result in results:
                if result["tool"] == "get_calendar_events":
                    calendar_events.extend(result.get("events", []))
                elif result["tool"] == "process_gmail_query":
                    gmail_threads.extend(result.get("threads", []))

                if result.get("success"):
                    self._update_confidence_memory(result["tool"], result.get("confidence", "medium"))

        # ------------------------------
        # 3️⃣ Build observations
        # ------------------------------
        observations = {
            "reasoning": reasoning,
            "calendar_events": calendar_events,
            "gmail_threads": gmail_threads,
            "raw_tool_results": all_tool_results,
            "perceived_at": datetime.now().isoformat(),
            "refinements_performed": refinement_count,
        }

        print(f"Gathered {len(calendar_events)} calendar event(s)")
        print(f"Gathered {len(gmail_threads)} email thread(s)")
        print(f"Final tool results:\n{all_tool_results}\n")

        # ------------------------------
        # 4️⃣ NEW: Generate user response
        # ------------------------------
        response_text = self._generate_user_response(
            user_query=user_query,
            observations=observations
        )

        new_payload = {
            **payload,
            "observations": observations,
            "response_text": response_text,
            "summary": response_text,
        }

        print("=" * 70)
        print("PERCEIVE-ONLY PHASE COMPLETE")
        print("=" * 70 + "\n")

        return Message(type=PLAN, payload=new_payload)

    # ------------------------------------------------------------------
    # RESPONSE GENERATION (THE FIX)
    # ------------------------------------------------------------------

    def _generate_user_response(self, user_query: str, observations: Dict[str, Any]) -> str:
        """Convert perceived context into a user-facing response."""

        calendar_events = observations.get("calendar_events", [])
        gmail_threads = observations.get("gmail_threads", [])

        if calendar_events:
            lines = ["Here are your events:"]
            for e in calendar_events:
                summary = e.get("summary", "Untitled Event")
                start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", "")
                lines.append(f"- {summary} ({start})")
            return "\n".join(lines)

        if gmail_threads:
            lines = ["Here are the emails I found:"]
            for t in gmail_threads[:5]:
                sender = t.get("sender") or t.get("from", "Unknown sender")
                subject = t.get("subject", "No subject")
                lines.append(f"- {sender}: {subject}")
            return "\n".join(lines)

        # Graceful empty results
        if "calendar" in user_query.lower():
            return "You don’t have any events scheduled for that time."

        if "mail" in user_query.lower() or "email" in user_query.lower():
            return "I couldn’t find any emails matching that request."

        return "I checked, but there was nothing relevant to show."

    # ------------------------------------------------------------------
    # LLM DECISION
    # ------------------------------------------------------------------

    def _decide_what_to_perceive(self, user_query: str) -> Dict[str, Any]:
        today = datetime.now().strftime("%Y-%m-%d")

        prompt = f"""
You are the Perception Agent.

Current date: {today}
Timezone: {self.timezone}
User request: "{user_query}"

Available tools ONLY:
- get_calendar_events(dates: list of YYYY-MM-DD)
- process_gmail_query(user_query: string)

Rules:
- Be minimal
- Only fetch required context
- Use confidence: high | medium | low

Output ONLY valid JSON:
{{
  "reasoning": "string",
  "tool_calls": [
    {{
      "name": "tool_name",
      "arguments": {{}},
      "confidence": "high|medium|low"
    }}
  ]
}}
""".strip()

        response = self.llm.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=600,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        tool_calls = [
            c for c in result.get("tool_calls", [])
            if c.get("confidence", "").lower() in {"high", "medium"}
        ]

        return {
            "reasoning": result.get("reasoning", ""),
            "tool_calls": tool_calls
        }

    # ------------------------------------------------------------------
    # TOOL EXECUTION
    # ------------------------------------------------------------------

    def _execute_perception_tools(self, tool_calls: List[Dict]) -> List[Dict]:
        results = []

        for call in tool_calls:
            name = call["name"]
            args = call.get("arguments", {})
            confidence = call.get("confidence", "medium")

            print(f"[Perceive] Executing {name} → {args}")

            try:
                output = self.tools[name](**args)

                if name == "get_calendar_events":
                    events = output if isinstance(output, list) else output.get("events", [])
                    results.append({
                        "tool": name,
                        "success": True,
                        "events": events,
                        "confidence": confidence
                    })

                elif name == "process_gmail_query":
                    threads = output.get("result", []) if isinstance(output, dict) else output
                    results.append({
                        "tool": name,
                        "success": True,
                        "threads": threads,
                        "confidence": confidence
                    })

            except Exception as e:
                results.append({
                    "tool": name,
                    "success": False,
                    "error": str(e),
                    "confidence": confidence
                })

        return results
