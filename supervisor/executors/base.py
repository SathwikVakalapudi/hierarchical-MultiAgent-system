from core.message import Message
from core.protocols import DATA_REQUEST, DATA_RESPONSE, FINAL_RESULT, TOOL_ACTIONS

class BaseExecutor:
    """
    Base executor for supervisors.
    Provides:
    - Context fetching from tools
    - Tool action validation
    - Final result wrapper
    """

    def __init__(self, tools: dict):
        """
        tools: dict of tool_name -> agent_instance
        """
        self.tools = tools

    # ------------------------------
    # Context fetching
    # ------------------------------
    def fetch_observations(self, domains: list) -> dict:
        observations = {}
        for domain in domains:
            tool = self.tools.get(domain)
            if not tool:
                raise RuntimeError(f"No tool available for domain: {domain}")

            print(f"🔍 Fetching data from tool: {domain}")
            response = tool.handle(Message(DATA_REQUEST, {}))

            if response.type != DATA_RESPONSE:
                raise RuntimeError(f"Tool '{domain}' failed to return DATA_RESPONSE")

            observations[domain] = response.payload
            print(f"✅ Data from '{domain}': {response.payload}")

        return observations

    # ------------------------------
    # Step validation
    # ------------------------------
    def validate_step(self, tool: str, action: str):
        if tool not in TOOL_ACTIONS:
            raise RuntimeError(f"Unknown tool: {tool}")

        if action not in TOOL_ACTIONS[tool]:
            raise RuntimeError(f"Invalid action '{action}' for tool '{tool}'")

    # ------------------------------
    # Final result wrapper
    # ------------------------------
    def final(self, payload: dict) -> Message:
        print("📤 Sending final result")
        return Message(FINAL_RESULT, payload)
