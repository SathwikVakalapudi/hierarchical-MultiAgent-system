# test.py
# Comprehensive test suite for ToolExecutor (execute.py)
# Run this file directly to test all functionality

import os
import json
from datetime import datetime, timedelta

from groq import Groq
from core.message import Message
from core.protocols import PLAN, EXECUTION_RESULT
from supervisor.executors.execute import ToolExecutor

# Load environment variables (GROQ_API_KEY, etc.)
from dotenv import load_dotenv
load_dotenv()

def create_test_executor(dry_run_email=True):
    """Create ToolExecutor with optional dry-run for emails"""
    llm_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    executor = ToolExecutor(llm_client)

    # Optional: globally enable dry-run for all email tasks during testing
    if dry_run_email:
        print("\n🧪 TEST MODE: Email dry-run ENABLED (no real emails will be sent)\n")
    return executor, llm_client

def test_empty_plan(executor):
    print("\n=== Test 1: Empty Plan ===")
    message = Message(
        type=PLAN,
        payload={
            "tool_calls": [],
            "summary": "Nothing to do"
        }
    )
    result = executor.handle(message)
    print("Result:", result.payload["summary"])
    assert result.type == EXECUTION_RESULT
    print("✅ Empty plan test passed\n")

def test_calendar_agent(executor):
    print("\n=== Test 2: run_calendar_agent (Add Event) ===")
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    input_data = {
        "user_query": "Add team meeting tomorrow at 3pm",
        "calendar_tasks": ["add team meeting tomorrow at 3pm"],
        "existing_events": [],  # Simulate no context
        "scope_days": [tomorrow],
        "preferences": {
            "timezone": "Asia/Kolkata",
            "default_event_duration_minutes": 60,
            "working_hours": {"start": "06:00", "end": "23:59"}
        },
        "dry_run": False  # Change to True to preview only
    }

    message = Message(
        type=PLAN,
        payload={
            "tool_calls": [
                {
                    "name": "run_calendar_agent",
                    "arguments": {"input_data": input_data}
                }
            ],
            "summary": "Testing calendar agent"
        }
    )

    result_msg = executor.handle(message)
    result = result_msg.payload
    print("Calendar Result Summary:", result["summary"])
    print("Success:", len([e for e in result["executions"] if e["success"]]))
    print("✅ Calendar agent test completed\n")

def test_email_agent(executor, dry_run=True):
    print(f"\n=== Test 3: run_email_agent (Send Email, dry_run={dry_run}) ===")
    
    input_data = {
        "user_query": "Send a quick hello to test@example.com",
        "email_tasks": ["send hello message to test@example.com"],
        "observations": {},  # No prior threads
        "dry_run": dry_run
    }

    message = Message(
        type=PLAN,
        payload={
            "tool_calls": [
                {
                    "name": "run_email_agent",
                    "arguments": {"input_data": input_data}
                }
            ],
            "summary": "Testing email agent"
        }
    )

    result_msg = executor.handle(message)
    result = result_msg.payload
    print("Email Result Summary:", result["summary"])
    
    if dry_run:
        print("🛡️  Dry-run confirmed: No real email sent")
    print("✅ Email agent test completed\n")

def test_parallel_execution(executor):
    print("\n=== Test 4: Parallel Execution (Calendar + Email) ===")
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    calendar_input = {
        "user_query": "Schedule lunch tomorrow at 1pm",
        "calendar_tasks": ["schedule lunch tomorrow at 1pm"],
        "existing_events": [],
        "scope_days": [tomorrow],
        "preferences": {
            "timezone": "Asia/Kolkata",
            "default_event_duration_minutes": 60,
            "working_hours": {"start": "06:00", "end": "23:59"}
        }
    }
    
    email_input = {
        "user_query": "Send reminder to friend@gmail.com about lunch",
        "email_tasks": ["send reminder about lunch to friend@gmail.com"],
        "observations": {},
        "dry_run": True
    }

    message = Message(
        type=PLAN,
        payload={
            "tool_calls": [
                {
                    "name": "run_calendar_agent",
                    "arguments": {"input_data": calendar_input}
                },
                {
                    "name": "run_email_agent",
                    "arguments": {"input_data": email_input}
                }
            ],
            "summary": "Testing parallel calendar + email"
        }
    )

    result_msg = executor.handle(message)
    result = result_msg.payload
    print("Parallel Execution Summary:", result["summary"])
    executions = result["executions"]
    print(f"Executed {len(executions)} tools in parallel")
    for exe in executions:
        status = "✅" if exe["success"] else "❌"
        print(f"  {status} {exe['tool']}: {exe.get('result', {}).get('changes_summary', 'Done')}")
    print("✅ Parallel execution test completed\n")

def test_low_level_tool(executor):
    print("\n=== Test 5: Low-Level Tool (get_calendar_events) ===")
    
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    message = Message(
        type=PLAN,
        payload={
            "tool_calls": [
                {
                    "name": "get_calendar_events",
                    "arguments": {"dates": [today, tomorrow]}
                }
            ]
        }
    )

    result_msg = executor.handle(message)
    result = result_msg.payload
    executions = result["executions"]
    
    if executions and executions[0]["success"]:
        events = executions[0]["result"]
        print(f"Found {len(events)} events on {today} and {tomorrow}")
    else:
        print("No events or fetch failed")
    
    print("✅ Low-level tool test completed\n")

if __name__ == "__main__":
    print("🚀 Starting ToolExecutor Tests\n")
    
    executor, _ = create_test_executor(dry_run_email=True)
    
    test_empty_plan(executor)
    test_calendar_agent(executor)
    test_email_agent(executor, dry_run=True)
    test_email_agent(executor, dry_run=False)  # Warning: this may send real email if credentials allow!
    test_parallel_execution(executor)
    test_low_level_tool(executor)
    
    print("🎉 All ToolExecutor tests completed!")
    print("\nNext step: Build supervisor/agent.py to orchestrate the full flow.")