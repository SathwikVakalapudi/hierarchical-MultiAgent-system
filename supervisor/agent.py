# supervisor/agent.py
"""
supervisor/agent.py
Main Supervisor Agent – Orchestrates the Full Pipeline
January 2026 – Production Ready (FIXED)
"""

from typing import Dict, Any
from datetime import datetime
from groq import Groq

from core.message import Message
from core.protocols import USER, MAIN_PLAN, EXECUTION_RESULT, PLAN

# Layer 1: Main Planner
from MainPlanner.agent import MainPlannerAgent

# Executors
from supervisor.executors.respond_only import RespondOnlyExecutor
from supervisor.executors.perceive_only import PerceiveOnlyExecutor
from supervisor.executors.perceive_plan_act import PerceivePlanActExecutor

# Memory
from memory.chat_memory_manager import ChatMemoryManager


class SupervisorAgent:
    """
    Top-level orchestrator.
    Routes user requests safely and returns natural, helpful responses.
    """

    def __init__(self, llm_client: Groq):
        self.llm_client = llm_client

        self.main_planner = MainPlannerAgent(llm_client)
        self.respond_only = RespondOnlyExecutor(llm_client)
        self.perceive_only = PerceiveOnlyExecutor(llm_client)
        self.perceive_plan_act = PerceivePlanActExecutor(llm_client)

        # Chat history logger
        self.memory_manager = ChatMemoryManager()

    def handle(self, message: Message) -> Message:
        print("\n" + "=" * 100)
        print("SUPERVISOR AGENT: Processing User Request")
        print("=" * 100)

        if message.type != USER:
            raise ValueError(f"SupervisorAgent expects USER message, got {message.type}")

        user_query = message.payload.get("text", "").strip()
        if not user_query:
            return self._quick_response("I didn't catch that. How can I help you today?")

        print(f"User: {user_query}\n")

        # STEP 1: MAIN PLANNER
        plan_message = self.main_planner.handle(message)

        if plan_message.type != MAIN_PLAN:
            raise RuntimeError(f"MainPlanner returned invalid message type: {plan_message.type}")

        decision: Dict[str, Any] = plan_message.payload or {}

        path = decision.get("execution_path", "perceive_then_act")
        domains = decision.get("context_domains", [])
        confidence = float(decision.get("confidence", 0.0))
        reasoning = decision.get("reasoning", "")

        print(f"Routing Decision: {path.upper()} (confidence: {confidence:.2f})")
        print(f"Domains: {domains or 'none'}")
        print(f"Reasoning: {reasoning}\n")

        # PLAN MESSAGE FOR EXECUTORS
        plan_for_executor = Message(
            type=PLAN,
            payload={
                "user_query": user_query,
                "execution_path": path,
                "context_domains": domains,
                "main_planner_reasoning": reasoning,
                "confidence": confidence,
            },
        )

        start_time = datetime.now()
        result_message = None
        execution_error = None

        # STEP 2: EXECUTION ROUTING
        try:
            if path == "respond_only":
                result_message = self.respond_only.handle(plan_for_executor)
            elif path == "perceive_only":
                result_message = self.perceive_only.handle(plan_for_executor)
            elif path == "perceive_then_act":
                result_message = self.perceive_plan_act.handle(plan_for_executor)
            else:
                print(f"Unknown execution path '{path}', falling back safely.")
                result_message = self.perceive_plan_act.handle(plan_for_executor)

        except Exception as e:
            execution_error = str(e)
            import traceback
            traceback.print_exc()

        duration = (datetime.now() - start_time).total_seconds()

        # STEP 3: HANDLE RESULT OR ERROR
        if execution_error:
            final_response = "I'm sorry, something went wrong while processing your request. Please try again."
            status = "error"
            summary = f"Execution failed: {execution_error}"
        elif not result_message:
            final_response = "I ran into an internal issue while completing your request."
            status = "error"
            summary = "No result message received"
        elif result_message.type == PLAN:
            payload = result_message.payload or {}
            response_text = payload.get("response_text")
            summary = payload.get("summary", response_text or "Checked")
            final_response = response_text or "I checked, but there was nothing relevant to show."
            status = "success"
        elif result_message.type == EXECUTION_RESULT:
            payload = result_message.payload or {}
            summary = payload.get("summary", "Task completed")
            response_text = payload.get("response_text")
            if response_text:
                final_response = response_text
            else:
                lower_summary = summary.lower()
                if "email" in lower_summary and "send" in lower_summary:
                    final_response = "I've sent the email for you."
                elif "meeting" in lower_summary or "event" in lower_summary:
                    final_response = "Your meeting has been scheduled successfully."
                elif "calendar" in lower_summary:
                    final_response = "I've added that to your calendar."
                else:
                    final_response = f"Done! {summary}"
            status = "success"
        else:
            final_response = "Internal error: unexpected result type."
            status = "error"
            summary = "Unexpected message type"

        print(f"\nFinal Summary: {summary}")
        print(f"Completed in {duration:.2f}s")
        print("=" * 100)
        print("SUPERVISOR AGENT: DONE")
        print("=" * 100 + "\n")

        # ────────────────────────────────────────────────
        # LOG TO MEMORY (this is the important part)
        # ────────────────────────────────────────────────
        self.memory_manager.add_turn(
            user_query=user_query,
            main_planner={
                "execution_path": path,
                "context_domains": domains,
                "confidence": confidence,
                "reasoning": reasoning
            },
            planner={
                "summary": summary,
                "tool_calls": payload.get("tool_calls", []) if 'payload' in locals() else []
            },
            perception_summary=reasoning,  # MainPlanner's reasoning is usually the best perception
            plan_summary=summary,
            action_results=summary,        # best fallback — most executors put useful info here
            final_response=final_response,
            status=status,
            duration_seconds=duration,
            metadata={
                "agents_involved": ["supervisor", "main_planner", "planner"],
                "execution_path": path,
                "error": execution_error if execution_error else None
            }
        )

        return self._quick_response(final_response)

    def _quick_response(self, text: str) -> Message:
        return Message(
            type=EXECUTION_RESULT,
            payload={
                "response_text": text,
                "summary": text,
                "executions": [],
                "completed_at": datetime.now().isoformat(),
            },
        )