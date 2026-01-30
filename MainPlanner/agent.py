import json
from groq import Groq

from core.message import Message
from core.protocols import USER, MAIN_PLAN



class MainPlannerAgent:
    """
    Layer 1: Main Planner (Improved Version)
    Routes user requests into 3 safe, scalable paths.
    """

    ALLOWED_EXECUTION_PATHS = {
        "respond_only",
        "perceive_only",
        "perceive_then_act",        # NEW: All actions perceive first
    }

    ALLOWED_CONTEXT_DOMAINS = {"gmail", "calendar"}

    def __init__(self, llm_client: Groq):
        self.llm = llm_client
        self.model = "llama-3.3-70b-versatile"

    def handle(self, message: Message) -> Message:
        print("\n================ MAIN PLANNER START ================\n")

        if message.type != USER:
            raise ValueError("MainPlannerAgent only handles USER messages")

        user_query = message.payload.get("text", "").strip()
        if not user_query:
            raise ValueError("User query is empty")

        print(f"User Query: {user_query}")

        decision = self._decide(user_query)

        print("\nMAIN PLANNER DECISION")
        for key, value in decision.items():
            print(f"   {key}: {value}")

        print("\n================ MAIN PLANNER END ==================\n")

        return Message(type=MAIN_PLAN, payload=decision)

    def _decide(self, user_query: str) -> dict:
        system_prompt = self._build_system_prompt()

        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                ],
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise RuntimeError(f"Groq LLM call failed in MainPlanner: {e}")

        raw_content = response.choices[0].message.content.strip()
        print(f"\nRaw LLM Output:\n{raw_content}")

        try:
            decision = json.loads(raw_content)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"MainPlanner failed to return valid JSON:\n{raw_content}\nError: {e}")

        decision = self._repair(decision)
        self._validate(decision)

        return decision

    def _build_system_prompt(self) -> str:
        return """
You are the MainPlanner agent in a personal assistant with Gmail and Calendar access.

Your job is to route the user request into one of THREE paths.

### Execution Paths:
- "respond_only": General questions, explanations, chit-chat. No tools needed.
- "perceive_only": Only fetch and summarize current state (e.g., "What's on my calendar today?", "Show emails from HR").
- "perceive_then_act": Any action: add/delete/update events, send emails, reply, etc. ALWAYS perceive context first for safety.

### Context Domains:
Only use: "gmail", "calendar"

### Output ONLY valid JSON:
{
  "execution_path": "one of the three paths above",
  "context_domains": ["gmail"] or ["calendar"] or ["gmail", "calendar"] or [],
  "confidence": 0.0 to 1.0,
  "reasoning": "short clear explanation"
}

### Examples:

1. User: "What can you do?"
→ {
  "execution_path": "respond_only",
  "context_domains": [],
  "confidence": 1.0,
  "reasoning": "General capability question"
}

2. User: "What's on my calendar tomorrow?"
→ {
  "execution_path": "perceive_only",
  "context_domains": ["calendar"],
  "confidence": 1.0,
  "reasoning": "Read-only calendar query"
}

3. User: "Send a quick hello email to john@example.com"
→ {
  "execution_path": "perceive_then_act",
  "context_domains": ["gmail"],
  "confidence": 0.95,
  "reasoning": "Email send is an action → perceive first if needed"
}

4. User: "Add gym tomorrow at 6pm"
→ {
  "execution_path": "perceive_then_act",
  "context_domains": ["calendar"],
  "confidence": 1.0,
  "reasoning": "Calendar modification → must perceive to check conflicts"
}

5. User: "Delete my dentist appointment"
→ {
  "execution_path": "perceive_then_act",
  "context_domains": ["calendar"],
  "confidence": 1.0,
  "reasoning": "Delete requires identifying correct event → perceive first"
}

6. User: "Reply to Sarah's latest email"
→ {
  "execution_path": "perceive_then_act",
  "context_domains": ["gmail"],
  "confidence": 1.0,
  "reasoning": "Reply needs email content → perceive first"
}

7. User: "Schedule meeting and notify team"
→ {
  "execution_path": "perceive_then_act",
  "context_domains": ["calendar", "gmail"],
  "confidence": 0.95,
  "reasoning": "Multi-action requiring both domains"
}

Now analyze the user query and output ONLY valid JSON.
""".strip()

    def _validate(self, decision: dict):
        required_keys = {"execution_path", "context_domains", "confidence", "reasoning"}

        missing = required_keys - decision.keys()
        if missing:
            raise RuntimeError(f"MainPlanner missing required keys: {missing}")

        path = decision["execution_path"]
        if path not in self.ALLOWED_EXECUTION_PATHS:
            raise RuntimeError(f"Invalid execution_path: {path}")

        if not isinstance(decision["context_domains"], list):
            raise RuntimeError("context_domains must be a list")

        for domain in decision["context_domains"]:
            if domain not in self.ALLOWED_CONTEXT_DOMAINS:
                raise RuntimeError(f"Invalid context domain: {domain}")

        if not (0.0 <= decision["confidence"] <= 1.0):
            raise RuntimeError("confidence must be between 0.0 and 1.0")

    def _repair(self, decision: dict) -> dict:
        repaired = decision.copy()
        repaired.setdefault("context_domains", [])
        repaired.setdefault("confidence", 0.8)
        repaired.setdefault("reasoning", "Auto-repaired by MainPlanner")

        # Safety: Default any ambiguous action to perceive_then_act
        path = repaired.get("execution_path", "")
        if path not in self.ALLOWED_EXECUTION_PATHS:
            repaired["execution_path"] = "perceive_then_act"
            repaired["reasoning"] += " | Defaulted to safe action path"

        return repaired