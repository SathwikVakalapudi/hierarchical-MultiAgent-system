from core.message import Message
from core.protocols import (
    CONTEXT_FOR_PLANNING,
    PLAN,
    EXECUTE,
    EXECUTION_RESULT,
)
from .base import BaseExecutor


class PlanThenActExecutor(BaseExecutor):
    def __init__(self, planner_agent, day_planner_agent, tools, working_hours):
        super().__init__(tools)
        self.planner_agent = planner_agent
        self.day_planner_agent = day_planner_agent
        self.working_hours = working_hours

    def execute(self, plan: dict):
        observations = {}

        # ------------------------------
        # PlannerAgent
        # ------------------------------
        plan_msg = self.planner_agent.handle(
            Message(
                CONTEXT_FOR_PLANNING,
                {
                    "intent": plan.get("intent"),
                    "observations": observations,
                },
            )
        )

        if plan_msg.type != PLAN:
            raise RuntimeError("PlannerAgent did not return PLAN")

        tasks = plan_msg.payload.get("tasks", [])
        non_calendar_steps = plan_msg.payload.get("non_calendar_steps", [])

        results = {
            "calendar": [],
            "non_calendar": [],
            "unscheduled_tasks": [],
        }

        # ------------------------------
        # Execute non-calendar steps
        # ------------------------------
        for step in non_calendar_steps:
            tool_name = step["tool"]
            action = step["action"]
            args = step.get("args", {})

            self.validate_step(tool_name, action)

            response = self.tools[tool_name].handle(
                Message(EXECUTE, {"action": action, "args": args})
            )

            if response.type != EXECUTION_RESULT:
                raise RuntimeError(f"{tool_name}.{action} failed")

            results["non_calendar"].append(
                {
                    "tool": tool_name,
                    "action": action,
                    "output": response.payload,
                }
            )

        return self.final(results)
