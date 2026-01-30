"""
supervisor/executors/perceive_plan_act.py
Perceive → Plan → Act Executor – FINAL PRODUCTION VERSION (January 2026)

Full safe execution path:
1. Perceive context (minimal + refined, like perceive_only)
2. Plan actions using PlannerAgent
3. Execute plan (parallel + nested support)

Uses existing components:
- PerceiveOnlyExecutor (for smart context gathering)
- PlannerAgent (for task extraction + delegation)
- ToolExecutor (for actual execution)
"""

import json
from datetime import datetime
from typing import Dict, Any

from core.message import Message
from core.protocols import PLAN, EXECUTION_RESULT, CONTEXT_FOR_PLANNING

# Import your existing components
from supervisor.executors.perceive_only import PerceiveOnlyExecutor
from planner.agent import PlannerAgent
from supervisor.executors.execute import ToolExecutor


class PerceivePlanActExecutor:
    """
    Safe default path: Always perceive first, then plan, then act.
    Used for any action involving calendar or gmail modifications.
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

        # Initialize the three phases
        self.perceive_executor = PerceiveOnlyExecutor(llm_client)
        self.planner_agent = PlannerAgent(llm_client)
        self.tool_executor = ToolExecutor(llm_client)

    def handle(self, message: Message) -> Message:
        print("\n" + "="*80)
        print("PERCEIVE → PLAN → ACT PIPELINE STARTED")
        print("="*80 + "\n")

        if message.type != PLAN:
            raise ValueError(f"PerceivePlanActExecutor expects PLAN message, got {message.type}")

        original_payload = message.payload or {}
        user_query = original_payload.get("user_query")

        if not user_query:
            raise ValueError("Missing user_query in payload")

        print(f"User Query: {user_query}\n")

        # ==================================================================
        # PHASE 1: PERCEIVE – Gather context safely
        # ==================================================================
        print("PHASE 1: Perceiving context...")
        perceive_message = Message(
            type=PLAN,
            payload={
                "user_query": user_query,
                # Carry forward any existing partial observations if present
                "observations": original_payload.get("observations", {})
            }
        )

        context_message = self.perceive_executor.handle(perceive_message)

        if context_message.type != PLAN:
            raise RuntimeError("PerceiveOnlyExecutor did not return PLAN message")

        context_payload = context_message.payload
        observations = context_payload.get("observations", {})

        print(f"Perception complete:")
        print(f"   → Calendar events: {len(observations.get('calendar_events', []))}")
        print(f"   → Gmail threads: {len(observations.get('gmail_threads', []))}")
        print(f"   → Refinements: {observations.get('refinements_performed', 0)}\n")

        # ==================================================================
        # PHASE 2: PLAN – Decide what to do with the context
        # ==================================================================
        print("PHASE 2: Planning actions...")
        plan_input_message = Message(
            type=CONTEXT_FOR_PLANNING,
            payload={
                "user_query": user_query,
                "observations": observations
            }
        )

        plan_message = self.planner_agent.handle(plan_input_message)

        if plan_message.type != PLAN:
            raise RuntimeError("PlannerAgent did not return PLAN message")

        plan_payload = plan_message.payload
        tool_calls = plan_payload.get("tool_calls", [])
        plan_summary = plan_payload.get("summary", "No plan generated")

        print(f"Planning complete:")
        print(f"   → Tool calls planned: {len(tool_calls)}")
        print(f"   → Summary: {plan_summary}\n")

        if not tool_calls:
            print("No actions needed → skipping execution")
            final_summary = f"Analysis complete: {plan_summary}"
            return Message(
                EXECUTION_RESULT,
                {
                    "executions": [],
                    "summary": final_summary,
                    "observations": observations,
                    "plan": plan_payload
                }
            )

        # ==================================================================
        # PHASE 3: ACT – Execute the plan
        # ==================================================================
        print("PHASE 3: Executing plan...")
        execution_message = Message(type=PLAN, payload=plan_payload)
        result_message = self.tool_executor.handle(execution_message)

        if result_message.type != EXECUTION_RESULT:
            raise RuntimeError("ToolExecutor did not return EXECUTION_RESULT")

        result_payload = result_message.payload
        executions = result_payload.get("executions", [])
        execution_summary = result_payload.get("summary", "Execution completed")

        print(f"Execution complete:")
        print(f"   → Total tool calls executed: {len(executions)}")
        print(f"   → Final result: {execution_summary}\n")

        # ==================================================================
        # FINAL RESULT
        # ==================================================================
        final_summary = f"{execution_summary} (after perceiving relevant context and planning)"

        print("="*80)
        print("PERCEIVE → PLAN → ACT PIPELINE COMPLETE")
        print(f"Final Summary: {final_summary}")
        print("="*80 + "\n")

        return Message(
            EXECUTION_RESULT,
            {
                "executions": executions,
                "summary": final_summary,
                "observations": observations,
                "plan": plan_payload,
                "perception_reasoning": observations.get("reasoning", ""),
                "completed_at": datetime.now().isoformat()
            }
        )