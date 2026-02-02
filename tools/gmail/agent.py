from __future__ import annotations

"""
tools.gmail.agent - Intelligent Email Specialist Agent
FINAL PRODUCTION VERSION – January 2026
"""

from typing import List, Dict, Any, Optional

from groq import Groq
from .query_engine import process_gmail_query
from .sender import send_simple_mail
from .llm import rewrite_email, extract_recipients

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

DEFAULT_MODEL = "llama-3.3-70b-versatile"

client = Groq(
    api_key="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"
)

# ------------------------------------------------------------------
# EMAIL AGENT
# ------------------------------------------------------------------

class EmailAgent:
    def __init__(self, llm_client: Groq | None = None):
        self.llm = llm_client or client
        self.model = DEFAULT_MODEL
        self.my_email = "sathwikvakalapudi@gmail.com"

    # ------------------------------------------------------------------
    # MAIN ENTRY
    # ------------------------------------------------------------------

    def process(self, input_data: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        user_query = input_data.get("user_query", "").strip()
        email_tasks: List[Dict[str, Any]] = input_data.get("email_tasks", [])
        observations: Dict[str, Any] = input_data.get("observations", {})
        user_feedback: Optional[str] = input_data.get("email_feedback")
        confirmed: bool = input_data.get("confirmed", False)

        if not email_tasks:
            return {
                "tool_calls": [],
                "reasoning": "No email-related tasks detected.",
                "changes_summary": "No actions taken.",
                "success": False,
                "awaiting_confirmation": False,
                "pending_emails": [],
            }

        tool_calls: List[Dict[str, Any]] = []
        reasoning_parts: List[str] = []
        changes: List[str] = []
        pending_emails: List[Dict[str, Any]] = []

        for idx, task in enumerate(email_tasks):
            if isinstance(task, str):
                task = {"action": "send", "body": task}

            action = task.get("action", "unknown").lower()

            # ----------------------------------------------------------
            # SEND / REPLY
            # ----------------------------------------------------------

            if action in ("send", "reply"):
                if action == "send":
                    args = self._prepare_send_args(task, user_query, user_feedback)
                else:
                    args = self._prepare_reply_args(task, user_query, observations, user_feedback)

                to = args.get("to")

                if not to or "@" not in to:
                    reasoning_parts.append("Could not determine a valid recipient → skipped")
                    changes.append("Task skipped: invalid recipient")
                    continue

                preview = {
                    "action": action,
                    "to": to,
                    "subject": args["subject"],
                    "body": args["body_text"],
                    "original_query_snippet": (
                        user_query[:100] + "..." if len(user_query) > 100 else user_query
                    ),
                    "task_index": idx,
                }

                if confirmed and not dry_run:
                    tool_calls.append({
                        "name": "send_simple_mail",
                        "arguments": {
                            "to": to,
                            "subject": args["subject"],
                            "body_text": args["body_text"],
                        },
                    })
                    reasoning_parts.append(f"Sent confirmed {action} to {to}")
                    changes.append(f"Sent {action} to {to}")
                else:
                    pending_emails.append(preview)
                    reasoning_parts.append(
                        f"Prepared {action} to {to} (subject: {args['subject']}) — awaiting confirmation"
                    )
                    changes.append(f"Prepared email to {to}")

            # ----------------------------------------------------------
            # SEARCH
            # ----------------------------------------------------------

            elif action == "search":
                search_result = self._handle_search_task(task.get("query", user_query))
                emails = search_result.get("result", [])

                if search_result.get("status") == "success" and emails:
                    count = len(emails)
                    reasoning_parts.append(f"Found {count} matching emails")
                    changes.append(f"Retrieved {count} email(s)")
                else:
                    reasoning_parts.append("Search returned no results")
                    changes.append("No matching emails found")

            else:
                reasoning_parts.append(f"Unknown action skipped: {action}")
                changes.append("Task skipped")

        return {
            "tool_calls": tool_calls,
            "reasoning": "\n\n".join(reasoning_parts) or "All tasks processed",
            "changes_summary": "; ".join(changes) or "No changes",
            "success": bool(tool_calls or pending_emails),
            "awaiting_confirmation": bool(pending_emails),
            "pending_emails": pending_emails,
        }

    # ------------------------------------------------------------------
    # SEND
    # ------------------------------------------------------------------

    def _prepare_send_args(
        self,
        task: Dict[str, Any],
        full_query: str,
        feedback: Optional[str] = None,
    ) -> Dict[str, str]:

        recipient_source = (
            task.get("to")
            or task.get("body")
            or full_query
            or ""
        )

        to = extract_recipients(recipient_source).get(
            "main_recipient",
            self.my_email,
        )

        body = (task.get("body") or full_query or "").strip()

        context = f"Original request: {full_query}"
        if feedback:
            context += f"\nUser feedback:\n{feedback}"

        rewritten = rewrite_email(
            body_text=body,
            context=context,
            style="natural, friendly, concise",
        )

        return {
            "to": to,
            "subject": rewritten["subject"],
            "body_text": rewritten["body"],
        }

    # ------------------------------------------------------------------
    # REPLY
    # ------------------------------------------------------------------

    def _prepare_reply_args(
        self,
        task: Dict[str, Any],
        full_query: str,
        observations: Dict[str, Any],
        feedback: Optional[str] = None,
    ) -> Dict[str, str]:

        recipient_source = (
            task.get("to")
            or task.get("body")
            or full_query
            or ""
        )

        to = extract_recipients(recipient_source).get(
            "main_recipient",
            self.my_email,
        )

        body = (task.get("body") or full_query or "").strip()
        subject = task.get("subject") or "Re: Previous Message"

        context = "Replying to an existing email thread."
        if feedback:
            context += f"\nUser feedback:\n{feedback}"

        rewritten = rewrite_email(
            subject=subject,
            body_text=body,
            context=context,
            style="professional",
        )

        return {
            "to": to,
            "subject": rewritten["subject"],
            "body_text": rewritten["body"],
        }

    # ------------------------------------------------------------------
    # SEARCH
    # ------------------------------------------------------------------

    def _handle_search_task(self, query: str) -> Dict[str, Any]:
        try:
            return process_gmail_query(
                user_query=query,
                auto_mark_read=True,
                auto_star=False,
                max_total_results=15,
            )
        except Exception as e:
            print(f"[Search] Failed: {e}")
            return {"status": "error", "result": []}
