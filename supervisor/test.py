from __future__ import annotations

"""
supervisor/test.py
Comprehensive standalone test suite for ToolExecutor
Uses safe mocks — no real Gmail/Calendar changes
December 27, 2025
"""

import asyncio
import json
from datetime import datetime

from groq import Groq

# Core project imports
from core.message import Message
from core.protocols import PLAN, EXECUTION_RESULT
from supervisor.executors.execute import ToolExecutor
api_key ="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"

client = Groq(api_key=api_key)

# ======================
# MOCK TOOL FUNCTIONS
# ======================

def mock_add_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    timezone: str = "Asia/Kolkata"
) -> dict:
    """Mock calendar event creation"""
    print(f"[MOCK] Created calendar event:")
    print(f"       Summary: {summary}")
    print(f"       Time: {start_datetime} → {end_datetime} ({timezone})")
    return {
        "status": "created",
        "id": "mock_cal_001",
        "summary": summary,
        "start": start_datetime,
        "end": end_datetime
    }


async def mock_send_simple_mail(
    to: str,
    subject: str,
    body_text: str,
    style: str = "professional"
) -> dict:
    """Mock email sending with simulated delay"""
    print(f"[MOCK] Sending email:")
    print(f"       To: {to}")
    print(f"       Subject: {subject}")
    print(f"       Style: {style}")
    print(f"       Body preview: {body_text[:120]}{'...' if len(body_text) > 120 else ''}")
    await asyncio.sleep(0.4)  # Simulate network latency
    return {
        "status": "sent",
        "message_id": "mock_mail_456",
        "recipient": to
    }


def mock_delete_event_natural(
    user_description: str,
    date_hint: str = "today",
    llm_client=None  # Unused in mock, but kept for signature compatibility
) -> dict:
    """Mock natural-language event deletion"""
    print(f"[MOCK] Deleting event:")
    print(f"       Description: '{user_description}'")
    print(f"       Date hint: {date_hint}")
    return {
        "status": "deleted",
        "matched_event": {
            "id": "mock_cal_789",
            "summary": user_description.capitalize()
        }
    }


# ======================
# TEST SCENARIOS
# ======================

TEST_CASES = [
    {
        "name": "Single Calendar Event Creation",
        "payload": {
            "tool_calls": [
                {
                    "name": "add_event",
                    "arguments": {
                        "summary": "Gym Workout",
                        "start_datetime": "2025-12-28T18:00:00",
                        "end_datetime": "2025-12-28T19:00:00",
                        "timezone": "Asia/Kolkata"
                    }
                }
            ]
        }
    },
    {
        "name": "Schedule Meeting + Notify Team (Parallel)",
        "payload": {
            "tool_calls": [
                {
                    "name": "add_event",
                    "arguments": {
                        "summary": "Daily Team Sync",
                        "start_datetime": "2025-12-30T10:00:00",
                        "end_datetime": "2025-12-30T10:30:00",
                        "timezone": "Asia/Kolkata"
                    }
                },
                {
                    "name": "send_simple_mail",
                    "arguments": {
                        "to": "team@company.com",
                        "subject": "Daily Sync Scheduled",
                        "body_text": "Hi team,\n\nJust added our daily standup on Dec 30 at 10 AM IST.\n\nLooking forward to it!\n\n— Your Assistant",
                        "style": "friendly"
                    }
                }
            ]
        }
    },
    {
        "name": "Natural Language Event Deletion",
        "payload": {
            "tool_calls": [
                {
                    "name": "delete_event_natural",
                    "arguments": {
                        "user_description": "dentist appointment",
                        "date_hint": "next week"
                    }
                }
            ]
        }
    },
    {
        "name": "Mixed Success/Failure (Error Handling)",
        "payload": {
            "tool_calls": [
                {
                    "name": "add_event",
                    "arguments": {
                        "summary": "Coffee with Sarah",
                        "start_datetime": "2025-12-29T15:00:00",
                        "end_datetime": "2025-12-29T16:00:00"
                    }
                },
                {
                    "name": "unknown_tool_xyz",
                    "arguments": {"action": "do_something"}
                }
            ]
        }
    },
    {
        "name": "Empty Tool Calls (No Action)",
        "payload": {
            "tool_calls": []
        }
    }
]


# ======================
# MAIN TEST RUNNER
# ======================

def run_tests() -> None:
    print("=" * 80)
    print("TOOL EXECUTOR TEST SUITE")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%B %d, %Y')}")
    print()

    # Initialize Groq client safely
    try:
        llm_client = Groq(api_key=api_key)  # Reads GROQ_API_KEY from environment
        print("Groq client initialized successfully\n")
    except Exception as e:
        print(f"Failed to initialize Groq client: {e}")
        print("Please set your GROQ_API_KEY environment variable.")
        print("Example: export GROQ_API_KEY=gsk_...")
        return

    # Instantiate executor
    executor = ToolExecutor(llm_client)

    # Patch with mock tools
    executor.tools.update({
        "add_event": mock_add_event,
        "send_simple_mail": mock_send_simple_mail,
        "delete_event_natural": mock_delete_event_natural,
    })

    print(f"Mock tools loaded: {list(executor.tools.keys())}\n")

    # Run each test
    for idx, case in enumerate(TEST_CASES, 1):
        name = case["name"]
        payload = case["payload"]

        print(f"TEST {idx}: {name}")
        print("-" * 70)

        plan_message = Message(type=PLAN, payload=payload)
        result_message = executor.handle(plan_message)

        if result_message.type != EXECUTION_RESULT:
            print(f"ERROR: Expected EXECUTION_RESULT, got {result_message.type}")
            continue

        result = result_message.payload
        executions = result.get("executions", [])
        summary = result.get("summary", "No summary")

        print(f"\nSummary: {summary}")
        print("Execution Details:")

        if not executions:
            print("   No tools were executed.")
        else:
            for exe in executions:
                status = "SUCCESS" if exe["success"] else "FAILED"
                tool_name = exe["tool"]
                print(f"   • [{exe['index']}] {tool_name} → {status}")
                if exe["success"]:
                    result_data = exe.get("result", {})
                    print(f"     Result: {json.dumps(result_data, indent=4)}")
                else:
                    error = exe.get("error", "Unknown error")
                    print(f"     Error: {error}")

        print("\n" + "=" * 80 + "\n")


# ======================
# ENTRY POINT
# ======================

if __name__ == "__main__":
    # Handle both direct execution and imported cases
    try:
        # If already in an async loop (e.g. Jupyter), warn
        asyncio.get_running_loop()
        print("Warning: Running inside an existing event loop.")
        print("Call run_tests() manually or use: asyncio.run(run_tests())")
    except RuntimeError:
        # No loop → safe to run
        run_tests()