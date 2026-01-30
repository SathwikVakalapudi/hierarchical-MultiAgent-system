from __future__ import annotations

"""
tools.calendar.agent - Standalone Intelligent Calendar Specialist Agent
Updated January 2026 – Fully self-contained with Google Calendar auth via service.py
"""

import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
from googleapiclient.errors import HttpError
import pytz
from groq import Groq

from .service import get_calendar_service

DEFAULT_MODEL = "llama-3.3-70b-versatile"
TIMEZONE = "Asia/Kolkata"
TZ = pytz.timezone(TIMEZONE)
SCOPES = ['https://www.googleapis.com/auth/calendar']


class CalendarAgent:
    def __init__(self, llm_client: Optional[Groq] = None):
        self.llm = llm_client or Groq()  # assumes GROQ_API_KEY in environment
        self.model = DEFAULT_MODEL
        self.service = get_calendar_service()  # uses the reliable version from service.py

    # ────────────── MAIN PROCESSING LOGIC ──────────────
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        user_query = input_data.get("user_query", "").strip()
        calendar_tasks = input_data.get("calendar_tasks", [])
        existing_events = input_data.get("existing_events", [])
        scope_days = input_data.get("scope_days", [])
        preferences = input_data.get("preferences", {})

        if not calendar_tasks:
            return {
                "tool_calls": [],
                "reasoning": "No calendar tasks identified.",
                "changes_summary": "No calendar changes needed.",
                "success": True
            }

        event_context = self._format_events_for_prompt(existing_events)
        target_dates = scope_days or self._infer_target_dates(calendar_tasks, user_query)

        today_str = datetime.now(TZ).strftime("%Y-%m-%d")
        tomorrow_str = (datetime.now(TZ) + timedelta(days=1)).strftime("%Y-%m-%d")

        prompt = f"""You are a precise, safety-conscious calendar assistant.
Execute the request efficiently and respectfully.

USER QUERY:
{user_query}

TASKS:
{json.dumps(calendar_tasks, indent=2)}

CURRENT EVENTS (relevant period):
{event_context or "No existing events found."}

PREFERENCES:
• Timezone: {preferences.get("timezone", TIMEZONE)}
• Default event duration: {preferences.get("default_event_duration_minutes", 60)} min
• Working hours: {preferences.get("working_hours", {"start": "09:00", "end": "18:00"})}

TODAY:     {today_str}
TOMORROW:  {tomorrow_str}

IMPORTANT RULES:
- Prefer working hours unless explicitly requested otherwise
- Avoid overlapping events unless user asks
- Be very careful with deletions — confirm intent in reasoning
- Use ISO 8601 format for datetimes (YYYY-MM-DDTHH:MM:SS+05:30)
- Timezone must match user's preference or Asia/Kolkata

AVAILABLE ACTIONS (return only these):
1. add_event(summary: str, start_datetime: str, end_datetime: str, timezone: str = "Asia/Kolkata")
2. delete_event_natural(user_description: str, date_hint: str = "today")
3. delete_all_events_on_date(date_str: str)   # format: YYYY-MM-DD

Return ONLY valid JSON in this exact structure — no extra text:

{{
  "reasoning": "short step-by-step explanation",
  "tool_calls": [
    {{"name": "add_event", "args": {{"summary": "...", "start_datetime": "...", "end_datetime": "...", "timezone": "..."}} }},
    ...
  ],
  "changes_summary": "human-readable summary of changes",
  "success": true/false
}}
""".strip()

        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=1200,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content.strip()

            # More robust JSON extraction
            json_match = re.search(r'\{[\s\S]*\}', content)
            if not json_match:
                raise ValueError("No valid JSON object found in LLM response")

            result = json.loads(json_match.group(0))

            return {
                "tool_calls": result.get("tool_calls", []),
                "reasoning": result.get("reasoning", "No reasoning provided").strip(),
                "changes_summary": result.get("changes_summary", "Calendar updated.").strip(),
                "success": result.get("success", bool(result.get("tool_calls", []))),
            }

        except Exception as e:
            return {
                "tool_calls": [],
                "reasoning": f"Processing failed: {str(e)}",
                "changes_summary": "Could not process calendar request.",
                "success": False
            }

    # ────────────── TOOL IMPLEMENTATIONS ──────────────
    def add_event(self, summary: str, start_datetime: str, end_datetime: str,
                  timezone: str = TIMEZONE) -> Dict[str, Any]:
        try:
            body = {
                "summary": summary,
                "start": {"dateTime": start_datetime, "timeZone": timezone},
                "end": {"dateTime": end_datetime, "timeZone": timezone},
            }
            event = self.service.events().insert(calendarId="primary", body=body).execute()
            return {
                "success": True,
                "event_id": event.get("id"),
                "htmlLink": event.get("htmlLink"),
                "summary": event.get("summary")
            }
        except HttpError as e:
            return {"success": False, "error": e._get_reason(), "status": e.resp.status}

    def get_events_on_date(self, date_str: str) -> List[Dict[str, Any]]:
        time_min = f"{date_str}T00:00:00+05:30"
        time_max = f"{date_str}T23:59:59+05:30"
        try:
            result = self.service.events().list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            return result.get("items", [])
        except HttpError:
            return []

    def delete_all_events_on_date(self, date_str: str) -> Dict[str, Any]:
        events = self.get_events_on_date(date_str)
        if not events:
            return {"success": True, "message": f"No events on {date_str}", "deleted_count": 0}

        deleted_ids = []
        failures = 0

        for event in events:
            if self._delete_event_by_id(event["id"]):
                deleted_ids.append(event["id"])
            else:
                failures += 1

        success = failures == 0
        count = len(deleted_ids)
        message = f"Deleted {count} event{'s' if count != 1 else ''} on {date_str}"
        if failures:
            message += f" ({failures} failed)"

        return {
            "success": success,
            "message": message,
            "deleted_count": count,
            "deleted_ids": deleted_ids
        }

    def delete_event_natural(self, user_description: str, date_hint: str = "today") -> Dict[str, Any]:
        today = datetime.now(TZ).date()

        if date_hint.lower() in ["tomorrow"]:
            target = today + timedelta(days=1)
        elif date_hint.lower() in ["yesterday"]:
            target = today - timedelta(days=1)
        else:
            target = today

        date_str = target.strftime("%Y-%m-%d")
        events = self.get_events_on_date(date_str)

        for event in events:
            summary = event.get("summary", "").lower()
            if user_description.lower() in summary:
                if self._delete_event_by_id(event["id"]):
                    return {
                        "success": True,
                        "message": f"Deleted: {event.get('summary')} on {date_str}",
                        "deleted_id": event["id"]
                    }

        return {
            "success": False,
            "message": f"No matching event found for '{user_description}' on {date_str}",
            "deleted_id": None
        }

    def _delete_event_by_id(self, event_id: str) -> bool:
        try:
            self.service.events().delete(calendarId="primary", eventId=event_id).execute()
            return True
        except Exception:
            return False

    # ────────────── HELPERS ──────────────
    def _format_events_for_prompt(self, events: List[Dict[str, Any]]) -> str:
        if not events:
            return "No existing events."

        lines = []
        for e in events:
            summary = e.get("summary", "(No title)")
            start_raw = e["start"].get("dateTime") or e["start"].get("date")
            end_raw = e["end"].get("dateTime") or e["end"].get("date")
            start = self._format_time(start_raw)
            end = self._format_time(end_raw)
            time_str = "All day" if start == "All day" else f"{start}–{end}" if end else start
            lines.append(f"- {summary}: {time_str} (ID: {e.get('id', 'unknown')})")

        return "\n".join(lines)

    @staticmethod
    def _format_time(dt_str: Optional[str]) -> str:
        if not dt_str or "T" not in dt_str:
            return "All day"
        return dt_str.split("T")[1][:5]  # HH:MM

    def _infer_target_dates(self, tasks: List[str], query: str = "") -> List[str]:
        text = (" ".join(tasks) + " " + query).lower()
        now = datetime.now(TZ)
        today = now.date()
        dates = set()

        if any(w in text for w in ["today", "tonight", "now"]):
            dates.add(today.strftime("%Y-%m-%d"))

        if "tomorrow" in text:
            dates.add((today + timedelta(days=1)).strftime("%Y-%m-%d"))

        # Basic weekday detection (can be expanded)
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day in enumerate(weekdays):
            if day in text:
                days_ahead = (i - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                dates.add((today + timedelta(days=days_ahead)).strftime("%Y-%m-%d"))

        if not dates:
            # Default to tomorrow if unclear
            dates.add((today + timedelta(days=1)).strftime("%Y-%m-%d"))

        return sorted(dates)