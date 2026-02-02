"""
supervisor.executors.execute
Universal Parallel Tool Execution Engine
FINAL PRODUCTION VERSION – January 2026
"""

import asyncio
import inspect
from functools import partial
from typing import Dict, Any, List, Callable
from datetime import datetime
import json
import traceback

from core.message import Message
from core.protocols import PLAN, EXECUTION_RESULT

# Low-level tools
from tools.calendar.functions import (
    add_event,
    delete_event_natural,
    get_calendar_events,
    delete_all_events_on_date,
)
from tools.gmail.sender import send_simple_mail
from tools.gmail.query_engine import process_gmail_query

# High-level agents
from tools.calendar.agent import CalendarAgent
from tools.gmail.agent import EmailAgent


# ---------------------------------------------------------------------
# TOOL EXECUTOR
# ---------------------------------------------------------------------

class ToolExecutor:
    def __init__(self, llm_client):
        print("\n" + "=" * 80)
        print("[INIT] ToolExecutor starting")
        print("=" * 80)

        self.llm_client = llm_client
        self.calendar_agent = CalendarAgent(llm_client)
        self.email_agent = EmailAgent(llm_client)

        self.tools: Dict[str, Callable] = {
            # Calendar
            "get_calendar_events": get_calendar_events,
            "add_event": add_event,
            "delete_event_natural": delete_event_natural,
            "delete_all_events_on_date": delete_all_events_on_date,

            # Gmail
            "process_gmail_query": process_gmail_query,
            "send_simple_mail": send_simple_mail,

            # Agents
            "run_calendar_agent": self._run_calendar_agent,
            "run_email_agent": self._run_email_agent,
        }

        print(f"[INIT] Registered tools ({len(self.tools)}):")
        for t in self.tools:
            print(f"   • {t}")

        print("[INIT] ToolExecutor READY")
        print("=" * 80 + "\n")

    # =====================================================================
    # AGENT WRAPPERS
    # =====================================================================

    async def _run_calendar_agent(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        print("\n[AGENT → CalendarAgent]")
        dry_run = input_data.pop("dry_run", False)

        print(f"dry_run = {dry_run}")
        print("Input:")
        print(json.dumps(input_data, indent=2))

        result = self.calendar_agent.process(input_data)

        print("Output:")
        print(json.dumps(result, indent=2))
        return result

    async def _run_email_agent(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        print("\n[AGENT → EmailAgent]")
        dry_run = input_data.pop("dry_run", False)

        print(f"dry_run = {dry_run}")
        print("Input:")
        print(json.dumps(input_data, indent=2))

        result = self.email_agent.process(input_data, dry_run=dry_run)

        print("Output:")
        print(json.dumps(result, indent=2))
        return result

    # =====================================================================
    # SINGLE TOOL EXECUTION
    # =====================================================================

    async def _execute_single(self, tool_call: Dict[str, Any], index: int) -> Dict[str, Any]:
        tool_name = tool_call.get("name")
        started_at = datetime.utcnow().isoformat()

        print("\n" + "-" * 80)
        print(f"[EXEC #{index}] Tool: {tool_name}")
        print("-" * 80)

        arguments = tool_call.get("arguments") or tool_call.get("args") or {}

        if tool_name not in self.tools:
            error = f"Unknown tool: {tool_name}"
            print(f"[EXEC #{index}] ERROR → {error}")
            return self._fail(index, tool_name, error, arguments, started_at)

        tool_func = self.tools[tool_name]

        try:
            print("[ARGS]")
            print(json.dumps(arguments, indent=2) if arguments else "(none)")

            # Special case: delete_event_natural needs llm_client
            if tool_name == "delete_event_natural":
                result = await self._run_with_llm(tool_func, arguments)
            else:
                result = await self._run_tool(tool_func, arguments)

            finished_at = datetime.utcnow().isoformat()
            print(f"[EXEC #{index}] SUCCESS")

            return {
                "index": index,
                "tool": tool_name,
                "success": True,
                "arguments": arguments,
                "result": result,
                "started_at": started_at,
                "finished_at": finished_at,
            }

        except Exception as e:
            print(f"[EXEC #{index}] FAILED → {e}")
            print(traceback.format_exc())
            return self._fail(index, tool_name, str(e), arguments, started_at)

    async def _run_tool(self, func: Callable, arguments: Dict[str, Any]):
        if inspect.iscoroutinefunction(func):
            return await func(**arguments)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, **arguments))

    async def _run_with_llm(self, func: Callable, arguments: Dict[str, Any]):
        if inspect.iscoroutinefunction(func):
            return await func(**arguments, llm_client=self.llm_client)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, partial(func, **arguments, llm_client=self.llm_client)
        )

    def _fail(self, index, tool, error, arguments, started_at):
        return {
            "index": index,
            "tool": tool,
            "success": False,
            "error": error,
            "arguments": arguments,
            "started_at": started_at,
            "finished_at": datetime.utcnow().isoformat(),
        }

    # =====================================================================
    # BATCH EXECUTION
    # =====================================================================

    async def _execute_batch(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not tool_calls:
            return []
        print(f"\n[PARALLEL] Executing {len(tool_calls)} tool(s)")
        return await asyncio.gather(
            *[self._execute_single(call, i) for i, call in enumerate(tool_calls)]
        )

    # =====================================================================
    # MAIN ASYNC PIPELINE
    # =====================================================================

    async def _handle_async(self, message: Message) -> Message:
        if message.type != PLAN:
            raise ValueError(f"Expected PLAN message, got {message.type}")

        payload = message.payload or {}
        tool_calls = payload.get("tool_calls", [])

        if not tool_calls:
            return Message(EXECUTION_RESULT, {
                "executions": [],
                "summary": payload.get("summary", "No actions required"),
            })

        print(f"\n[EXECUTION] Top-level tool calls: {len(tool_calls)}")

        executions = await self._execute_batch(tool_calls)
        all_execs = list(executions)
        summaries: List[str] = []

        # Collect nested calls (from agents only)
        nested_calls: List[Dict[str, Any]] = []

        for exe in executions:
            if not exe["success"]:
                summaries.append(f"Failed: {exe.get('error')}")
                continue

            result = exe.get("result", {})
            if not isinstance(result, dict):
                continue

            if result.get("tool_calls"):
                nested_calls.extend(result["tool_calls"])

            if result.get("changes_summary"):
                summaries.append(result["changes_summary"])

        # Execute nested calls
        if nested_calls:
            print(f"\n[NESTED] Executing {len(nested_calls)} nested tool(s)")
            nested_execs = await self._execute_batch(nested_calls)
            all_execs.extend(nested_execs)

            for exe in nested_execs:
                if exe["success"]:
                    summaries.append(
                        exe.get("result", {}).get("message")
                        or f"{exe['tool']} completed"
                    )
                else:
                    summaries.append(f"Failed: {exe.get('error')}")

        final_summary = "; ".join(summaries) or "Actions completed"

        print("\n[EXECUTION COMPLETE]")
        print(final_summary)

        return Message(EXECUTION_RESULT, {
            "executions": all_execs,
            "summary": final_summary,
        })

    # =====================================================================
    # SYNC ENTRYPOINT
    # =====================================================================

    def handle(self, message: Message) -> Message:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._handle_async(message))

        if loop.is_running():
            raise RuntimeError(
                "ToolExecutor.handle() called inside an active event loop. "
                "Use `await _handle_async()` instead."
            )

        return loop.run_until_complete(self._handle_async(message))
