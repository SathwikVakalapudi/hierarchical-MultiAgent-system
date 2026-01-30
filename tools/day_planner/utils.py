import json

def clean_llm_output(text: str) -> str:
    """
    Clean LLM output to extract valid JSON.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "")
    return text.strip()

def validate_day_plan(plan: dict):
    """
    Validate day plan output for strict requirements.
    """
    if not isinstance(plan, dict):
        return "Plan must be a JSON object"

    if "scheduled_tasks" not in plan or "unscheduled_tasks" not in plan:
        return "Output must contain scheduled_tasks and unscheduled_tasks"

    if not isinstance(plan["scheduled_tasks"], list):
        return "scheduled_tasks must be a list"

    if not isinstance(plan["unscheduled_tasks"], list):
        return "unscheduled_tasks must be a list"

    for idx, task in enumerate(plan["scheduled_tasks"], start=1):
        for field in ("title", "start_datetime", "end_datetime", "priority"):
            if field not in task:
                return f"Scheduled task #{idx} missing field: {field}"

    return None
