"""
supervisor.executors.execute - Universal Parallel Tool Execution Engine
FINAL PRODUCTION VERSION – December 2025 → January 2026 (updated for args/arguments compatibility)
Full nested execution + debug logging + safe async handling
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
from tools.calendar.functions import add_event, delete_event_natural, get_calendar_events, delete_all_events_on_date
from tools.gmail.sender import send_simple_mail
from tools.gmail.query_engine import process_gmail_query

# High-level intelligent agents
from tools.calendar.agent import CalendarAgent
from tools.gmail.agent import EmailAgent


class ToolExecutor:
    def __init__(self, llm_client):
        print("\n" + "=" * 80)
        print("[INIT] ToolExecutor initialization started")
        print("=" * 80)

        self.llm_client = llm_client
        self.calendar_agent = CalendarAgent(self.llm_client)
        self.email_agent = EmailAgent(self.llm_client)

        self.tools: Dict[str, Callable] = {
            "get_calendar_events": get_calendar_events,
            "add_event": add_event,
            "delete_event_natural": delete_event_natural,
            "delete_all_events_on_date": delete_all_events_on_date,
            "process_gmail_query": process_gmail_query,
            "send_simple_mail": send_simple_mail,
            "run_calendar_agent": self._run_calendar_agent,
            "run_email_agent": self._run_email_agent,
        }

        print(f"[INIT] Registered {len(self.tools)} tools:")
        for name in self.tools:
            print(f"   → {name}")
        print("[INIT] ToolExecutor READY")
        print("=" * 80 + "\n")

    # ======================================================================
    # AGENT DELEGATION WRAPPERS
    # ======================================================================

    async def _run_calendar_agent(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        print("\n[AGENT → CalendarAgent] START")
        dry_run = input_data.pop("dry_run", False)
        print(f"[AGENT → CalendarAgent] dry_run = {dry_run}")
        print("[AGENT → CalendarAgent] Input:")
        print(json.dumps(input_data, indent=2))

        result = self.calendar_agent.process(input_data)

        print("[AGENT → CalendarAgent] OUTPUT:")
        print(json.dumps(result, indent=2))
        print("[AGENT → CalendarAgent] END\n")
        return result

    async def _run_email_agent(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        print("\n[AGENT → EmailAgent] START")
        dry_run = input_data.pop("dry_run", False)
        print(f"[AGENT → EmailAgent] dry_run = {dry_run}")
        print("[AGENT → EmailAgent] Input:")
        print(json.dumps(input_data, indent=2))

        result = self.email_agent.process(input_data, dry_run=dry_run)

        print("[AGENT → EmailAgent] OUTPUT:")
        print(json.dumps(result, indent=2))
        print("[AGENT → EmailAgent] END\n")
        return result

    # ======================================================================
    # SINGLE TOOL EXECUTION
    # ======================================================================

    async def _execute_single(self, tool_call: Dict[str, Any], index: int) -> Dict[str, Any]:
        print("\n" + "-" * 80)
        print(f"[EXECUTE #{index}] {tool_call.get('name', 'unknown')}")
        print("-" * 80)

        started_at = datetime.utcnow().isoformat()
        tool_name = tool_call.get("name")

        # ─── FIXED: support both "arguments" (OpenAI-style) and "args" (Groq/CalendarAgent-style) ───
        arguments = tool_call.get("arguments") or tool_call.get("args", {})

        # Optional: warn when arguments are empty (helps debugging)
        if not arguments:
            print(f"[EXECUTE #{index}] WARNING: No arguments received for tool '{tool_name}'")

        if not tool_name or tool_name not in self.tools:
            error = "Invalid or unknown tool"
            print(f"[EXECUTE #{index}] ERROR: {error}")
            return {
                "index": index,
                "tool": tool_name or "unknown",
                "success": False,
                "error": error,
                "started_at": started_at,
                "finished_at": datetime.utcnow().isoformat(),
            }

        tool_func = self.tools[tool_name]

        try:
            # ---- SAFE JSON LOGGING ----
            print(f"[EXECUTE #{index}] Arguments:")
            print(json.dumps(arguments, indent=2))

            # ---- SPECIAL HANDLING: delete_event_natural ----
            if tool_name == "delete_event_natural":
                print(f"[EXECUTE #{index}] Running delete_event_natural with injected llm_client")

                if inspect.iscoroutinefunction(tool_func):
                    result = await tool_func(
                        **arguments,
                        llm_client=self.llm_client
                    )
                else:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        partial(tool_func, **arguments, llm_client=self.llm_client)
                    )

            # ---- NORMAL TOOL EXECUTION PATH ----
            else:
                if inspect.iscoroutinefunction(tool_func):
                    print(f"[EXECUTE #{index}] Running ASYNC tool")
                    result = await tool_func(**arguments)
                else:
                    print(f"[EXECUTE #{index}] Running SYNC tool in thread pool")
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        partial(tool_func, **arguments)
                    )

            finished_at = datetime.utcnow().isoformat()
            print(f"[EXECUTE #{index}] SUCCESS")
            print(f"[EXECUTE #{index}] Result:")
            print(json.dumps(result, indent=2) if isinstance(result, (dict, list)) else result)

            return {
                "index": index,
                "tool": tool_name,
                "success": True,
                "result": result,
                "arguments": arguments,
                "started_at": started_at,
                "finished_at": finished_at,
            }

        except Exception as e:
            finished_at = datetime.utcnow().isoformat()
            print(f"[EXECUTE #{index}] FAILED: {str(e)}")
            print(traceback.format_exc())

            return {
                "index": index,
                "tool": tool_name,
                "success": False,
                "error": str(e),
                "arguments": arguments,
                "started_at": started_at,
                "finished_at": finished_at,
            }

    # ======================================================================
    # BATCH EXECUTION
    # ======================================================================

    async def _execute_batch(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not tool_calls:
            return []
        print(f"\n[PARALLEL] Executing {len(tool_calls)} tool(s) in parallel")
        return await asyncio.gather(*[
            self._execute_single(call, i) for i, call in enumerate(tool_calls)
        ])

    # ======================================================================
    # MAIN ASYNC PIPELINE
    # ======================================================================

    async def _handle_async(self, message: Message) -> Message:
        print("\n" + "=" * 80)
        print("TOOL EXECUTION PHASE STARTED")
        print("=" * 80)

        if message.type != PLAN:
            raise ValueError(f"Expected PLAN message, got {message.type}")

        payload = message.payload or {}
        tool_calls = payload.get("tool_calls", [])

        if not tool_calls:
            print("No tool calls → nothing to do")
            return Message(EXECUTION_RESULT, {
                "executions": [],
                "summary": payload.get("summary", "No actions required")
            })

        print(f"Top-level tool calls: {len(tool_calls)}")

        all_executions = []
        final_summaries = []

        # Execute top-level tools (may include agents)
        executions = await self._execute_batch(tool_calls)
        all_executions.extend(executions)

        # Collect nested tool_calls from agent outputs
        nested_calls = []
        for exe in executions:
            if exe["success"]:
                result = exe.get("result", {})
                if isinstance(result, dict):
                    tool_calls_list = result.get("tool_calls", [])
                    if tool_calls_list:
                        print(f"\n[NESTED] Found {len(tool_calls_list)} nested tool call(s) from {exe['tool']}")
                        # Optional: show what exactly is coming from the agent
                        print("[NESTED RAW CALLS]")
                        print(json.dumps(tool_calls_list, indent=2))
                        nested_calls.extend(tool_calls_list)
                    if result.get("changes_summary"):
                        final_summaries.append(result["changes_summary"])

        # Execute nested actions
        if nested_calls:
            print(f"\n[NESTED] Executing {len(nested_calls)} nested action(s)")
            nested_execs = await self._execute_batch(nested_calls)
            all_executions.extend(nested_execs)

            for exe in nested_execs:
                if exe["success"]:
                    res = exe.get("result", {})
                    summary = (
                        res.get("changes_summary") or
                        res.get("message") or
                        f"{exe['tool']} completed"
                    )
                    final_summaries.append(summary)
                else:
                    final_summaries.append(f"Failed: {exe.get('error')}")

        final_summary = "; ".join(final_summaries) if final_summaries else "Actions completed"

        print("\n" + "=" * 80)
        print("EXECUTION COMPLETE")
        print(f"Total executions: {len(all_executions)}")
        print(f"Final Summary: {final_summary}")
        print("=" * 80 + "\n")

        return Message(
            EXECUTION_RESULT,
            {
                "executions": all_executions,
                "summary": final_summary
            }
        )

    # ======================================================================
    # SYNC ENTRYPOINT
    # ======================================================================

    def handle(self, message: Message) -> Message:
        """Synchronous wrapper that safely runs the async pipeline"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                return loop.create_task(self._handle_async(message))
            else:
                return loop.run_until_complete(self._handle_async(message))
        except RuntimeError:
            return asyncio.run(self._handle_async(message))