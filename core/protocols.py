"""
protocols.py
-----------------
This file defines the communication contract of the system.
It contains:
- Message types (agent-to-agent IPC)
- Plan metadata keys
- Tool action registries
- Tool capability definitions
- Execution control flags

NO business logic should live here.
"""

# =====================================================
# Message Types (Agent ↔ Agent Communication)
# =====================================================

# Entry / User
USER = "USER"
USER_INTENT = "USER_INTENT"

# Context & Data Flow
DATA_REQUEST = "DATA_REQUEST"
DATA_RESPONSE = "DATA_RESPONSE"
CONTEXT_FOR_PLANNING = "CONTEXT_FOR_PLANNING"

# Planning Layers
MAIN_PLAN = "MAIN_PLAN"          # High-level intent → execution strategy
PLAN = "PLAN"                    # Step-by-step executable plan
SUPERVISOR_PLAN = "SUPERVISOR_PLAN"  # (reserved for future)

# Execution
EXECUTE = "EXECUTE"
EXECUTION_RESULT = "EXECUTION_RESULT"

# Final Output
FINAL_RESULT = "FINAL_RESULT"


# =====================================================
# Plan Metadata Keys (inside PLAN payload)
# =====================================================
# These are REQUIRED keys that planners should provide

PLAN_META_KEYS = {
    "needs_data",        # bool → does execution require external context?
    "needs_planning",    # bool → is multi-step reasoning required?
    "confidence",        # float → planner confidence score
    "reasoning",         # str → explanation for debugging / observability
}


# =====================================================
# Tool-specific Supported Actions
# =====================================================

CALENDAR_ACTIONS = {
    "add_event",
    "get_events_on_date",
    "get_events_in_range",
    "get_plans_for_day",
    "delete_event",
}

GMAIL_ACTIONS = {
    "list_unread",
    "search",
    "mark_read",
    "star",
    "send_email",
}


# =====================================================
# Tool Action Registry
# =====================================================
# Used by Supervisor for validation & routing

TOOL_ACTIONS = {
    "calendar": list(CALENDAR_ACTIONS),
    "gmail": list(GMAIL_ACTIONS),
}


# =====================================================
# Tool Capabilities
# =====================================================
# Used for safety checks & execution optimization

TOOL_CAPABILITIES = {
    "calendar": {
        "read": True,
        "write": True,
        "needs_context": True,     # Requires date / time info
        "safe_actions": list(CALENDAR_ACTIONS),
    },
    "gmail": {
        "read": True,
        "write": True,
        "needs_context": False,    # Can execute directly
        "safe_actions": list(GMAIL_ACTIONS),
    },
}


# =====================================================
# Execution Control Flags
# =====================================================
# Global execution policy (can be overridden later)

EXECUTION_FLAGS = {
    "allow_parallel": False,   # future extension
    "allow_retry": True,
    "max_retries": 2,
    "stop_on_failure": True,
}
