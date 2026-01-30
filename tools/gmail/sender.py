from __future__ import annotations

"""
tools.gmail.sender - Real Gmail sending with LLM rewriting
Final Production Version – December 2025
"""

import base64
from email.mime.text import MIMEText
from typing import Dict

from groq import Groq  # Import Groq to create client if needed
from .service import get_gmail_service
from .llm import rewrite_email


def send_simple_mail(
    to: str,
    subject: str,
    body_text: str,
) -> Dict[str, str]:
    """
    Send a professionally rewritten email via Gmail.
    """

    final_subject = subject
    final_body =body_text

    service = get_gmail_service()

    message = MIMEText(final_body)
    message["to"] = to
    message["from"] = "me"
    message["subject"] = final_subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {"raw": raw}

    try:
        sent = service.users().messages().send(userId="me", body=body).execute()
        print(f"[REAL EMAIL SENT] ID: {sent['id']}")
        return {
            "status": "sent",
            "message_id": sent["id"],
            "recipient": to,
            "subject": final_subject
        }
    except Exception as e:
        print(f"[EMAIL SEND FAILED] {e}")
        return {"status": "failed", "error": str(e)}