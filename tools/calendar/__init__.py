"""
tools.calendar - Google Calendar integration for the personal assistant framework

High-level API for:
- Creating events with smart defaults
- Natural-language deletion ("delete gym tomorrow", "cancel meeting with John")
- LLM-assisted fuzzy event matching
- Fetching events by date, range or description
- Human-readable daily/weekly plan summaries
- Secure OAuth handling with automatic token refresh

Public functions are re-exported here for convenient import:
    from tools.calendar import add_event, delete_event_natural, get_plans_for_day
"""

from typing import Any

# Core calendar operations
from .functions import (
    add_event,
    delete_all_events_on_date,
    delete_event_natural,
    get_event,
    get_events_in_range,
    get_events_on_date,
    get_plans_for_day,
)

# Auth & token helpers (legacy / manual flow)
# from .auth_bootstrap import bootstrap_oauth
from .service import get_access_token

__all__ = [
    # Main high-level functions (recommended for most use cases)
    "add_event",
    "delete_event_natural",           # LLM-powered natural language delete
    "delete_all_events_on_date",
    "get_plans_for_day",              # human-readable summary
    # Lower-level / query functions
    "get_event",
    "get_events_on_date",
    "get_events_in_range",
    # Auth & token utilities
    # "bootstrap_oauth",                # manual one-time bootstrap
    "get_access_token",               # raw access token (with refresh)
]

__version__ = "0.2.1"  # bumped after cleanup + natural delete improvements
__description__ = (
    "Intelligent Google Calendar client with natural language support, "
    "LLM-powered matching and secure OAuth handling"
)