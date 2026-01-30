# test_planner.py

import json
from datetime import datetime

from groq import Groq
from planner.agent import PlannerAgent
from core.message import Message
from core.protocols import CONTEXT_FOR_PLANNING

# --------------------------
# Initialize Groq client
# --------------------------
API_KEY = "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"
client = Groq(api_key=API_KEY)

# =====================================================
# Mock observations (simulate what PerceiveExecutor would return)
# =====================================================
def mock_observations():
    # Simulate fetched calendar events for tomorrow (Dec 28, 2025)
    tomorrow = (datetime.now().date().replace(day=28)).strftime("%Y-%m-%d")
    
    mock_events = [
        {
            "id": "abc123xyz",
            "summary": "Team Standup",
            "start": {"dateTime": f"{tomorrow}T10:00:00+05:30"},
            "end": {"dateTime": f"{tomorrow}T10:30:00+05:30"}
        },
        {
            "id": "def456uvw",
            "summary": "Lunch with Client",
            "start": {"dateTime": f"{tomorrow}T13:00:00+05:30"},
            "end": {"dateTime": f"{tomorrow}T14:00:00+05:30"}
        }
    ]

    return {
        "calendar_events": mock_events,
        "gmail_threads": [],  # Add mock emails if testing email tasks
        "reasoning": "Mocked perception for testing"
    }

# =====================================================
# Test Runner
# =====================================================
def run_tests():
    agent = PlannerAgent(llm_client=client)

    test_cases = [
        {
            "name": "Add gym tomorrow evening (conflict expected)",
            "user_query": "Add a gym session tomorrow evening at 6pm for 1 hour"
        },
        {
            "name": "Delete existing event by natural description",
            "user_query": "Delete the team standup tomorrow"
        },
        {
            "name": "Move an event",
            "user_query": "Move my lunch with client tomorrow to 2pm"
        },
        {
            "name": "Complex multi-task with email",
            "user_query": "Schedule a gym workout tomorrow at 6pm and send an email to Sarah saying I'll be late for our 7pm call"
        },
        {
            "name": "Simple calendar add (free slot)",
            "user_query": "Add dentist appointment on Monday at 11am"
        },
        {
            "name": "No calendar task (should do nothing)",
            "user_query": "Tell me a joke"
        },
        {
            "name": "Ambiguous delete (should be safe)",
            "user_query": "Delete lunch"
        }
    ]

    print("\n" + "="*60)
    print("     RUNNING PLANNER + CALENDAR AGENT TESTS")
    print("="*60 + "\n")

    mock_obs = mock_observations()

    for idx, case in enumerate(test_cases, 1):
        print(f"TEST {idx}: {case['name']}")
        print("-" * 80)
        print(f"Query: {case['user_query']}\n")

        message = Message(
            type=CONTEXT_FOR_PLANNING,
            payload={
                "user_query": case["user_query"],
                "observations": mock_obs
            }
        )

        try:
            result = agent.handle(message)
            plan = result.payload

            print("GENERATED PLAN:")
            if "tool_calls" in plan and plan["tool_calls"]:
                for i, call in enumerate(plan["tool_calls"]):
                    print(f"  [{i+1}] {call['name']} → {json.dumps(call['arguments'], indent=2)}")
            else:
                print("  No tool calls generated (expected for non-action queries)")

            print("\n" + "-" * 80 + "\n")

        except Exception as e:
            print(f"ERROR in test {idx}: {str(e)}\n")
            print("-" * 80 + "\n")

    print("="*60)
    print("           ALL TESTS COMPLETED")
    print("="*60)


if __name__ == "__main__":
    run_tests()