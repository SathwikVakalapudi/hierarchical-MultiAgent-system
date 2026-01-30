import json
from core.message import Message
from core.protocols import (
    USER_INTENT,
    DATA_REQUEST,
    DATA_RESPONSE,
    CONTEXT_FOR_PLANNING,
    PLAN,
    EXECUTE,
    EXECUTION_RESULT,
    FINAL_RESULT,
    TOOL_ACTIONS,
)


class SupervisorAgent:
    """
    Layer 2: Orchestrator
    - Uses LLM to select tools
    - Collects context
    - Calls planner
    - Safely executes plan
    """

    def __init__(self, planner, tools: dict, llm_client):
        self.planner = planner
        self.tools = tools
        self.llm = llm_client

    # -----------------------------
    # LLM-based tool selection
    # -----------------------------
    
    
    def _select_tools(self, user_intent: dict) -> list:
        prompt = f"""
You are a Supervisor Agent responsible ONLY for deciding
which tools are required to gather information.

STRICT RULES:
- You MUST NOT plan actions
- You MUST NOT suggest execution steps
- You MUST NOT modify user intent
- You MUST ONLY select tools from the provided list
- Output MUST be valid JSON

Available tools:
{list(self.tools.keys())}

User intent:
{user_intent}

Decision guidelines:
- If intent mentions email, inbox, unread, reply → gmail
- If intent mentions meetings, schedule, availability, calendar → calendar
- If unsure → select all relevant tools
- If no tools are needed → return empty list

OUTPUT FORMAT (JSON ONLY):
{{
  "tools_to_query": ["tool_name"]
}}
"""

        response = self.llm.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )

        raw_text = response.output_text.strip()

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            raise RuntimeError("Supervisor LLM returned invalid JSON")

        tools = data.get("tools_to_query", [])

        # Safety check
        for tool in tools:
            if tool not in self.tools:
                raise RuntimeError(f"Unknown tool selected by LLM: {tool}")

        return tools

    # -----------------------------
    # Main entry point
    # -----------------------------
    def handle(self, message: Message) -> Message:
        if message.type != USER_INTENT:
            raise ValueError("Supervisor only accepts USER_INTENT")

        # 1️⃣ Ask LLM which tools to query
        tools_to_query = self._select_tools(message.payload)

        # 2️⃣ Collect context from tools
        tool_data = {}

        for tool_name in tools_to_query:
            tool_agent = self.tools[tool_name]

            response = tool_agent.handle(
                Message(DATA_REQUEST, {})
            )

            if response.type != DATA_RESPONSE:
                raise RuntimeError(f"{tool_name} failed to return DATA_RESPONSE")

            tool_data[tool_name] = response.payload

        # 3️⃣ Ask planner to generate plan
        plan_message = self.planner.handle(
            Message(
                CONTEXT_FOR_PLANNING,
                {
                    "user_intent": message.payload,
                    "tool_data": tool_data,
                }
            )
        )

        if plan_message.type != PLAN:
            raise RuntimeError("Planner failed to return PLAN")

        steps = plan_message.payload.get("steps", [])

        if not steps:
            return Message(
                FINAL_RESULT,
                {"message": "No actions required"}
            )

        # 4️⃣ Execute plan safely
        results = []

        for step in steps:
            tool = step["tool"]
            action = step["action"]
            args = step.get("args", {})

            # Tool validation
            if tool not in self.tools:
                raise RuntimeError(f"Planner requested unknown tool: {tool}")

            # Action validation
            if action not in TOOL_ACTIONS.get(tool, []):
                raise RuntimeError(
                    f"Unsafe action '{action}' for tool '{tool}'"
                )

            result = self.tools[tool].handle(
                Message(EXECUTE, {"action": action, "args": args})
            )

            if result.type != EXECUTION_RESULT:
                raise RuntimeError(
                    f"Execution failed for {tool}.{action}"
                )

            results.append(result.payload)

        return Message(FINAL_RESULT, {"results": results})
