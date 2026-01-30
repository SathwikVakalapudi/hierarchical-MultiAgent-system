"""
tools.calendar.functions - Smart Google Calendar operations
Modernized January 2026 – Fully compatible with get_calendar_service()
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import pytz
from groq import Groq
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .service import get_calendar_service

# ──────────────────────────────────────────────
# GLOBAL LLM CLIENT
# ──────────────────────────────────────────────
GROQ_API_KEY = "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"
llm_global_client = Groq(api_key=GROQ_API_KEY)
DEFAULT_MODEL = "llama-3.3-70b-versatile"
TIMEZONE = "Asia/Kolkata"
TZ = pytz.timezone(TIMEZONE)

# ──────────────────────────────────────────────
# TIME FORMAT HELPER
# ──────────────────────────────────────────────
def _format_time(dt_str: Optional[str]) -> str:
    if not dt_str or "T" not in dt_str:
        return "All day"
    return dt_str.split("T")[1][:5]  # HH:MM only

# ──────────────────────────────────────────────
# ADD EVENT
# ──────────────────────────────────────────────
def add_event(summary: str, start_datetime: str, end_datetime: str, timezone: str = TIMEZONE) -> Dict[str, Any]:
    """Create a new Google Calendar event."""
    try:
        datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
        datetime.fromisoformat(end_datetime.replace("Z", "+00:00"))
    except ValueError as e:
        return {"error": f"Invalid datetime: {e}", "status_code": 400}

    service = get_calendar_service()
    event_body = {
        "summary": summary,
        "start": {"dateTime": start_datetime, "timeZone": timezone},
        "end": {"dateTime": end_datetime, "timeZone": timezone},
    }

    try:
        event = service.events().insert(calendarId="primary", body=event_body).execute()
        print(f"[add_event] SUCCESS → {summary} → {event.get('htmlLink', '(no link)')}")
        return event
    except HttpError as e:
        return {"error": e._get_reason(), "status_code": e.resp.status}

# ──────────────────────────────────────────────
# GET EVENTS
# ──────────────────────────────────────────────
def get_event(event_id: str) -> Dict[str, Any]:
    service = get_calendar_service()
    try:
        return service.events().get(calendarId="primary", eventId=event_id).execute()
    except HttpError:
        return {}

def get_events_on_date(date_str: str) -> List[Dict[str, Any]]:
    service = get_calendar_service()
    time_min = f"{date_str}T00:00:00+05:30"
    time_max = f"{date_str}T23:59:59+05:30"
    try:
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return events_result.get("items", [])
    except HttpError:
        return []

def get_events_in_range(start_datetime: str, end_datetime: str) -> List[Dict[str, Any]]:
    service = get_calendar_service()
    time_min = start_datetime if "T" in start_datetime else f"{start_datetime}T00:00:00+05:30"
    time_max = end_datetime if "T" in end_datetime else f"{end_datetime}T23:59:59+05:30"
    try:
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return events_result.get("items", [])
    except HttpError:
        return []

def get_calendar_events(dates: List[str]) -> List[Dict[str, Any]]:
    all_events: List[Dict[str, Any]] = []
    for date_str in dates:
        all_events.extend(get_events_on_date(date_str))
    return all_events

def get_plans_for_day(date_str: str) -> str:
    events = get_events_on_date(date_str)
    if not events:
        return f"No plans on {date_str}."
    lines = [f"Plans on {date_str}:"]
    for e in events:
        summary = e.get("summary", "(No title)")
        start = _format_time(e["start"].get("dateTime", e["start"].get("date")))
        end = _format_time(e["end"].get("dateTime", e["end"].get("date")))
        time_range = "All day" if start == "All day" else f"{start} → {end}"
        lines.append(f"- {summary}: {time_range}")
    return "\n".join(lines)

# ──────────────────────────────────────────────
# DELETE EVENTS
# ──────────────────────────────────────────────
def delete_all_events_on_date(date_str: str) -> dict:
    events = get_events_on_date(date_str)
    if not events:
        return {"success": True, "message": f"No events found on {date_str}", "date": date_str,
                "deleted_count": 0, "total_found": 0, "deleted_ids": [], "failures": 0}

    deleted_ids, failures = [], 0
    for event in events:
        if _delete_event_by_id(event["id"]):
            deleted_ids.append(event["id"])
        else:
            failures += 1

    success = failures == 0
    message = (f"Successfully deleted all {len(events)} events on {date_str}" if success else
               f"Deleted {len(deleted_ids)} of {len(events)} events on {date_str} ({failures} failed)")

    return {"success": success, "message": message, "date": date_str,
            "deleted_count": len(deleted_ids), "total_found": len(events),
            "deleted_ids": deleted_ids, "failures": failures}

def delete_event_natural(user_description: str, date_hint: str = "today",
                         llm_client: Optional[Groq] = None, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    """Delete event using natural language description with LLM matching."""
    client = llm_client or llm_global_client
    if client is None:
        return {"success": False, "message": "No LLM client available", "deleted_id": None}

    # Resolve date
    today = datetime.now(TZ).date()
    hint = date_hint.lower().strip()
    if hint == "tomorrow":
        target_date = today + timedelta(days=1)
    elif hint == "yesterday":
        target_date = today - timedelta(days=1)
    else:
        target_date = today
        weekdays = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        for i, day in enumerate(weekdays):
            if day in hint:
                days_ahead = (i - today.weekday()) % 7
                days_ahead = days_ahead if days_ahead != 0 else 7
                target_date = today + timedelta(days=days_ahead)
                break

    date_str = target_date.strftime("%Y-%m-%d")
    events = get_events_on_date(date_str)
    if not events:
        return {"success": False, "message": f"No events found on {date_str}", "deleted_id": None}

    # Build event list for LLM
    event_list = []
    for e in events:
        summary = e.get("summary", "(no title)").strip()
        start = _format_time(e["start"].get("dateTime"))
        end = _format_time(e["end"].get("dateTime"))
        time_str = f"{start}–{end}" if start != "All day" else "All day"
        event_list.append(f"• '{summary}' at {time_str} (ID: {e['id']})")

    prompt = f"""
User wants to delete an event described as: "{user_description}"

Date: {date_str}

Available events:
{"\n".join(event_list)}

Return ONLY JSON:
{{
  "event_id": "ID or NONE",
  "confidence": 0.0 to 1.0,
  "reason": "short explanation"
}}
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        event_id = result.get("event_id", "NONE").strip()
        confidence = float(result.get("confidence", 0))

        if event_id == "NONE" or confidence < 0.7:
            titles = [e.get("summary", "(no title)") for e in events]
            return {"success": False, "message": f"Could not confidently match '{user_description}'. Available events: {', '.join(titles[:5])}", "deleted_id": None}

        if _delete_event_by_id(event_id):
            title = next((e.get("summary") for e in events if e["id"] == event_id), "Unknown")
            return {"success": True, "message": f"Deleted '{title}' on {date_str}", "deleted_id": event_id}
        else:
            return {"success": False, "message": "API failed to delete event", "deleted_id": None}

    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}", "deleted_id": None}

# ──────────────────────────────────────────────
# DELETE BY ID
# ──────────────────────────────────────────────
def _delete_event_by_id(event_id: str) -> bool:
    service = get_calendar_service()
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        print(f"[_delete_event_by_id] SUCCESS → Event {event_id} deleted")
        return True
    except Exception as e:
        print(f"[_delete_event_by_id] FAILED → {e}")
        return False