# tools/calendar/test.py
# COMPLETE END-TO-END LIVE TEST SUITE
# December 2025 – Production Ready
# WARNING: This script WILL modify your REAL Google Calendar!

import json
from datetime import datetime, timedelta

from groq import Groq
from tools.calendar.agent import CalendarAgent
from tools.calendar.functions import add_event, delete_event_natural
from tools.calendar.auth_bootstrap import bootstrap_oauth
from tools.calendar.service import get_access_token

# ==================================================
# CONFIGURATION
# ==================================================
GROQ_API_KEY = "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"  # Replace only if rotated
client = Groq(api_key=GROQ_API_KEY)

# ==================================================
# AUTHENTICATION
# ==================================================
def ensure_authentication() -> bool:
    """Check and refresh Google Calendar OAuth if needed."""
    print("\n🔑 Checking Google Calendar authentication...\n")
    try:
        get_access_token()
        print("✅ Authentication is valid!\n")
        return True
    except Exception as e:
        print(f"❌ Authentication failed: {e}\n")
        choice = input("🔄 Do you want to run OAuth setup now? (y/n): ").strip().lower()
        if choice == 'y':
            try:
                bootstrap_oauth()
                print("\n✅ OAuth completed successfully! You're now authenticated.\n")
                return True
            except Exception as auth_e:
                print(f"\n❌ OAuth setup failed: {auth_e}\n")
                return False
        else:
            print("\n🚫 Tests aborted — authentication required.\n")
            return False


# ==================================================
# MOCK EXISTING EVENTS (for planning context)
# ==================================================
def get_mock_events():
    """Return simulated events for tomorrow to help LLM plan correctly."""
    tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
    return [
        {
            "id": "client_meeting_001",
            "summary": "Client Meeting",
            "start": {"dateTime": f"{tomorrow}T18:00:00+05:30"},
            "end": {"dateTime": f"{tomorrow}T19:00:00+05:30"}
        },
        {
            "id": "team_lunch_001",
            "summary": "Lunch with Team",
            "start": {"dateTime": f"{tomorrow}T13:00:00+05:30"},
            "end": {"dateTime": f"{tomorrow}T14:00:00+05:30"}
        }
    ]


# ==================================================
# TEST CASES
# ==================================================
test_cases = [
    {
        "name": "Add gym workout at 6pm → should detect conflict and resolve",
        "user_query": "Add a gym workout tomorrow at 6pm for 1 hour",
        "calendar_tasks": ["add gym workout tomorrow at 6pm for 1 hour"]
    },
    {
        "name": "Delete the client meeting in the evening",
        "user_query": "Cancel the client meeting tomorrow evening",
        "calendar_tasks": ["delete client meeting tomorrow evening"]
    },
    {
        "name": "Reschedule team lunch to 2pm",
        "user_query": "Move my team lunch tomorrow to 2pm",
        "calendar_tasks": ["move team lunch tomorrow to 2pm"]
    }
]


# ==================================================
# MAIN LIVE TEST RUNNER
# ==================================================
def run_live_tests():
    if not ensure_authentication():
        return

    agent = CalendarAgent(llm_client=client)
    mock_events = get_mock_events()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    print("═" * 100)
    print("           LIVE CALENDAR AGENT – END-TO-END TEST")
    print(f"           Target Date: {tomorrow} (Tomorrow)")
    print("           THIS WILL ADD, MOVE, AND DELETE EVENTS ON YOUR REAL CALENDAR")
    print("═" * 100)

    print("\n⚠️  WARNING: Real changes will be made to your Google Calendar!\n")
    confirm = input("   >>> TYPE 'yes' TO CONTINUE, anything else to cancel: ").strip().lower()

    if confirm != "yes":
        print("\n🚫 Tests cancelled by user. No changes made.\n")
        return

    print("\n🚀 Starting tests...\n")

    scope_days = [tomorrow]

    for i, case in enumerate(test_cases, 1):
        print(f"\n🧪 TEST {i}/{len(test_cases)}: {case['name']}")
        print("─" * 100)
        print(f"👤 User Query: {case['user_query']}\n")

        input_data = {
            "user_query": case["user_query"],
            "calendar_tasks": case["calendar_tasks"],
            "existing_events": mock_events,
            "scope_days": scope_days,
            "preferences": {
                "timezone": "Asia/Kolkata",
                "default_event_duration_minutes": 60,
                "working_hours": {"start": "09:00", "end": "18:00"}
            }
        }

        # === PLAN PHASE ===
        result = agent.process(input_data)

        print("🧠 AGENT PLANNING RESULT:")
        print(f"   Success: {result['success']}")
        print(f"   Summary: {result['changes_summary']}")
        print(f"   Reasoning:\n      {result['reasoning']}\n")

        if not result.get("tool_calls"):
            print("⚠️  No tool calls planned — nothing to execute.\n")
            continue

        print("🔧 EXECUTING REAL TOOL CALLS:\n")
        for j, call in enumerate(result["tool_calls"], 1):
            tool_name = call["name"]
            args = call["arguments"]

            print(f"   {j}. {tool_name}")
            print(f"      Arguments: {json.dumps(args, indent=4)}")

            try:
                if tool_name == "add_event":
                    response = add_event(**args)
                    link = response.get("htmlLink", "(no link)")
                    print(f"       ✅ Event created successfully!")
                    print(f"          → Open: {link}\n")

                elif tool_name == "delete_event_natural":
                    response = delete_event_natural(
                        user_description=args["user_description"],
                        date_hint=args["date_hint"],
                        llm_client=client  # Required for natural language matching
                    )
                    print(f"       ✅ {response.get('message', 'Event deleted successfully')}\n")

                else:
                    print(f"       ⚠️  Unknown tool: {tool_name}\n")

            except Exception as e:
                print(f"       ❌ EXECUTION FAILED: {str(e)}\n")

        print("─" * 100)

    print("\n" + "═" * 100)
    print("               ALL TESTS COMPLETED SUCCESSFULLY!")
    print("               Check your Google Calendar to see the changes.")
    print("               You can now close this window.")
    print("═" * 100 + "\n")


# ==================================================
# ENTRY POINT
# ==================================================
if __name__ == "__main__":
    run_live_tests()