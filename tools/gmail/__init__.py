"""
tools.gmail - Gmail integration for the personal assistant

High-level, clean API for:
- Sending emails
- Searching & processing inbox
- Filtering (rule-based + LLM)
- Rewriting emails with AI
- Secure service access
"""

from .service import get_gmail_service
from .query_engine import process_gmail_query
from .sender import send_simple_mail
from .llm import rewrite_email
from .filter import (
    filter_emails_rule_based,
    filter_emails_llm,
)

__all__ = [
    "get_gmail_service",
    "process_gmail_query",
    "send_simple_mail",
    "rewrite_email",
    "filter_emails_rule_based",
    "filter_emails_llm",
]

__version__ = "0.1.0"
__description__ = "Clean Gmail client with AI-powered features"