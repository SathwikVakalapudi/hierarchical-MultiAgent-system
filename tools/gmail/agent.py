from __future__ import annotations

"""
tools.gmail.agent - Intelligent Email Specialist Agent
Updated Jan 2026: Supports structured email_tasks + human confirmation before send
"""

from typing import List, Dict, Any, Optional

from groq import Groq
from .query_engine import process_gmail_query
from .sender import send_simple_mail
from .llm import rewrite_email, extract_recipients  # assuming typo fixed: extract_recipients


DEFAULT_MODEL = "llama-3.3-70b-versatile"
GROQ_API_KEY = "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"

client = Groq(api_key=GROQ_API_KEY)


class EmailAgent:
    def __init__(self, llm_client: Groq = None):
        self.llm = llm_client or client
        self.model = DEFAULT_MODEL
        self.my_email = "sathwikvakalapudi@gmail.com"

    def process(self, input_data: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """
        Main entry point.
        Returns structured result including pending_emails when confirmation is required.
        """
        user_query = input_data.get("user_query", "").strip()
        email_tasks: List[Dict[str, Any]] = input_data.get("email_tasks", [])
        observations: Dict[str, Any] = input_data.get("observations", {})
        user_feedback: Optional[str] = input_data.get("email_feedback")          # from previous round
        confirmed: bool = input_data.get("confirmed", False)                     # did user approve?

        if not email_tasks:
            return {
                "tool_calls": [],
                "reasoning": "No email-related tasks detected.",
                "changes_summary": "No actions taken.",
                "success": False,
                "awaiting_confirmation": False,
                "pending_emails": []
            }

        tool_calls: List[Dict[str, Any]] = []
        reasoning_parts: List[str] = []
        changes: List[str] = []
        pending_emails: List[Dict[str, Any]] = []

        for task in email_tasks:
            if isinstance(task, str):
                task = {"action": "send", "body": task}

            action = task.get("action", "unknown").lower()

            if action in ("send", "reply"):
                if action == "send":
                    args = self._prepare_send_args(task, user_query, user_feedback)
                else:
                    args = self._prepare_reply_args(task, user_query, observations, user_feedback)

                if not args.get("to") or "@" not in args["to"]:
                    reasoning_parts.append(f"Could not determine valid recipient for task → skipped")
                    changes.append("Task skipped: invalid recipient")
                    continue

                email_preview = {
                    "action": action,
                    "to": args["to"],
                    "subject": args["subject"],
                    "body": args["body_text"],
                    "original_query_snippet": user_query[:100] + "..." if len(user_query) > 100 else user_query,
                    "task_index": email_tasks.index(task),  # optional - helps track which task
                }

                # ── Confirmation logic ───────────────────────────────────────
                if confirmed and not dry_run:
                    # User already approved this email → send it now
                    tool_calls.append({
                        "name": "send_simple_mail",
                        "arguments": {
                            "to": args["to"],
                            "subject": args["subject"],
                            "body_text": args["body_text"],
                        }
                    })
                    changes.append(f"Sent {action} to {args['to']} – Subject: {args['subject']}")
                    reasoning_parts.append(f"**Sent confirmed {action}** to **{args['to']}**")
                else:
                    # Not yet confirmed → ask user
                    pending_emails.append(email_preview)
                    reasoning_parts.append(
                        f"Prepared {action} to **{args['to']}** "
                        f"(subject: {args['subject'][:60]}...) – **awaiting confirmation**"
                    )
                    changes.append(f"Prepared email to {args['to']} – waiting for approval")

            elif action == "search":
                search_result = self._handle_search_task(task.get("query", user_query))
                status = search_result.get("status", "error")
                emails = search_result.get("result", [])

                if status == "success" and emails:
                    count = len(emails)
                    top_emails = "\n".join(
                        f"- **{e['sender']}**: {e['subject']}\n  {e['summary'].get('summary', 'No summary')}"
                        for e in emails[:5]
                    )
                    changes.append(f"Retrieved {count} email(s)")
                    reasoning_parts.append(f"**Found {count} emails**:\n{top_emails}")
                else:
                    changes.append("No matching emails found")
                    reasoning_parts.append("Search returned no results")

            else:
                reasoning_parts.append(f"Skipped unknown action: {action}")
                changes.append("Task skipped")

        return {
            "tool_calls": tool_calls,
            "reasoning": "\n\n".join(reasoning_parts) or "All tasks processed",
            "changes_summary": "; ".join(changes) or "No changes",
            "success": bool(tool_calls or pending_emails),
            "awaiting_confirmation": bool(pending_emails),
            "pending_emails": pending_emails,
        }

    def _prepare_send_args(
        self,
        task: Dict[str, Any],
        full_query: str,
        feedback: Optional[str] = None
    ) -> Dict[str, str]:
        to = extract_recipients(task).get("main_recipient", self.my_email)

        body = task.get("body", full_query).strip()

        extra_prompt = ""
        if feedback:
            extra_prompt = f"\nUser requested changes / feedback:\n{feedback}\nApply these improvements."

        try:
            rewritten = rewrite_email(
                body_text=body,
                context=f"Original request: {full_query}{extra_prompt}",
                style="natural, friendly, concise"
            )
        except Exception as e:
            print(f"[Send] Rewrite failed: {e}")
            rewritten = {
                "subject": "Message from Sathwik",
                "body": f"Hello,\n\n{body}\n\nBest regards,\nSathwik"
            }

        return {
            "to": to,
            "subject": rewritten["subject"],
            "body_text": rewritten["body"],
        }

    def _prepare_reply_args(
        self,
        task: Dict[str, Any],
        full_query: str,
        observations: Dict[str, Any],
        feedback: Optional[str] = None
    ) -> Dict[str, str]:
        to = extract_recipients(task).get("main_recipient", self.my_email)
        body = task.get("body", full_query).strip()

        thread_id = task.get("thread_id")
        original_subject = "Re: Previous Message"
        context_snippet = ""

        if thread_id:
            context_snippet = "\n\n--- Replying in thread ---\n"

        extra_prompt = ""
        if feedback:
            extra_prompt = f"\nUser feedback on draft:\n{feedback}\nRevise accordingly."

        try:
            rewritten = rewrite_email(
                subject=original_subject,
                body_text=f"{body}{context_snippet}",
                style="professional",
                context=f"Reply to incoming email{extra_prompt}"
            )
        except Exception as e:
            print(f"[Reply] Rewrite failed: {e}")
            rewritten = {
                "subject": original_subject,
                "body": f"{body}\n\nBest regards,\nSathwik"
            }

        return {
            "to": to,
            "subject": rewritten["subject"],
            "body_text": rewritten["body"],
        }

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