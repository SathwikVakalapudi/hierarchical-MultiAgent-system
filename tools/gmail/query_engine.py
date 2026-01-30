from __future__ import annotations

"""
tools.gmail.query_engine - Advanced Gmail intelligence pipeline
GLOBAL CLIENT VERSION – January 2026
"""

import time
import http.client
import ssl
import re
from base64 import urlsafe_b64decode
from html import unescape
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any

from .service import get_gmail_service
from .llm import (
    parse_user_query,
    build_gmail_query,
    summarize_email,
    filter_emails_llm,
)
from .filter import filter_emails_rule_based


# ------------------------------------------------------------------
# MESSAGE FETCHING
# ------------------------------------------------------------------

def fetch_message_with_retry(
    service,
    message_id: str,
    retries: int = 6,
    initial_delay: float = 1.0
) -> Dict[str, Any] | None:
    delay = initial_delay
    for attempt in range(1, retries + 1):
        try:
            return service.users().messages().get(
                userId="me",
                id=message_id,
                format="full"
            ).execute()
        except (http.client.IncompleteRead, ConnectionResetError, ssl.SSLError, TimeoutError) as e:
            if attempt == retries:
                print(f"[fetch] Exhausted retries for {message_id}: {e}")
                return None
            time.sleep(delay)
            delay = min(delay * 2, 60)
        except Exception as e:
            print(f"[fetch] Fatal error for {message_id}: {e}")
            return None
    return None


# ------------------------------------------------------------------
# PAYLOAD EXTRACTION
# ------------------------------------------------------------------

def extract_body_from_payload(payload: Dict[str, Any]) -> str:
    def decode_part(part: Dict[str, Any]) -> str:
        data = part.get("body", {}).get("data")
        if not data:
            return ""
        try:
            decoded = urlsafe_b64decode(data).decode("utf-8", errors="replace")
            if part.get("mimeType") == "text/html":
                decoded = re.sub(r"<[^>]+>", " ", decoded)
                decoded = unescape(decoded)
            return decoded.strip()
        except Exception:
            return ""

    def walk(parts: List[Dict[str, Any]]) -> str:
        for p in parts:
            if p.get("mimeType") in ("text/plain", "text/html"):
                content = decode_part(p)
                if content:
                    return content
            if p.get("parts"):
                found = walk(p["parts"])
                if found:
                    return found
        return ""

    return walk(payload.get("parts", [])) or decode_part(payload)


def extract_attachments(payload: Dict[str, Any]) -> List[str]:
    attachments = []

    def scan(parts):
        for p in parts:
            if p.get("filename") and p.get("body", {}).get("attachmentId"):
                attachments.append(p["filename"])
            if p.get("parts"):
                scan(p["parts"])

    if payload.get("parts"):
        scan(payload["parts"])

    return attachments


def fetch_thread_context(service, thread_id: str, current_msg_id: str) -> str:
    try:
        thread = service.users().threads().get(
            userId="me",
            id=thread_id,
            format="minimal"
        ).execute()

        context = []
        for msg in thread.get("messages", []):
            if msg["id"] == current_msg_id:
                continue
            headers = {
                h["name"].lower(): h["value"]
                for h in msg["payload"].get("headers", [])
            }
            context.append(f"{headers.get('from','Unknown')}: {msg.get('snippet','')}")

        return "\n".join(context[-5:])
    except Exception as e:
        print(f"[thread] Failed to fetch context: {e}")
        return ""


# ------------------------------------------------------------------
# EMAIL SUMMARIZATION (THREADED)
# ------------------------------------------------------------------

def summarize_email_threaded(email: Dict[str, Any], idx: int, total: int) -> Dict[str, Any]:
    print(f"[{idx}/{total}] Summarizing: {email['subject'][:60]}...")

    try:
        summary = summarize_email(
            subject=email["subject"],
            sender=email["sender"],
            body=email["body"],
            thread_context=email.get("thread_context", "")
        )
    except Exception as e:
        print(f"[summarize] failed: {e}")
        summary = {"summary": "[Unavailable]", "fallback_used": True}

    return {
        "id": email["id"],
        "sender": email["sender"],
        "subject": email["subject"],
        "date": email.get("date", "Unknown"),
        "labels": email["labels"],
        "attachments": email["attachments"],
        "relevance_score": email.get("relevance_score"),
        "relevance_reason": email.get("relevance_reason"),
        "summary": summary,
    }


# ------------------------------------------------------------------
# MAIN PIPELINE
# ------------------------------------------------------------------

def process_gmail_query(
    user_query: str,
    auto_mark_read: bool = True,
    auto_star: bool = False,
    max_total_results: int = 20,
    max_threads: int = 10
) -> Dict[str, Any]:

    service = get_gmail_service()
    warnings: List[str] = []

    # 1️⃣ Parse query
    filters = parse_user_query(user_query)
    gmail_query = build_gmail_query(filters)
    print(f"[query_engine] Gmail search: {gmail_query}")

    # 2️⃣ Fetch message IDs
    message_ids = []
    response = service.users().messages().list(
        userId="me",
        q=gmail_query,
        maxResults=500
    ).execute()

    message_ids = [m["id"] for m in response.get("messages", [])][:max_total_results * 2]

    if not message_ids:
        return {
            "status": "no_emails",
            "formatted_result": "No emails found matching your query.",
            "result": []
        }

    # 3️⃣ Fetch messages
    raw_emails = []
    for msg_id in message_ids:
        msg = fetch_message_with_retry(service, msg_id)
        if not msg:
            continue

        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        thread_id = msg.get("threadId", msg_id)

        email = {
            "id": msg_id,
            "thread_id": thread_id,
            "subject": headers.get("subject", "(No Subject)"),
            "sender": headers.get("from", "Unknown"),
            "date": headers.get("date", "Unknown"),
            "labels": msg.get("labelIds", []),
            "body": extract_body_from_payload(msg["payload"]),
            "attachments": extract_attachments(msg["payload"]),
            "thread_context": fetch_thread_context(service, thread_id, msg_id)
        }

        raw_emails.append(email)

    # 4️⃣ Filtering
    pre_filtered = filter_emails_rule_based(raw_emails)
    filtered = filter_emails_llm(pre_filtered, user_query)

    if not filtered:
        return {
            "status": "filtered_empty",
            "warnings": warnings,
            "formatted_result": "No emails matched after filtering.",
            "result": []
        }

    final_emails = filtered[:max_total_results]

    # 5️⃣ Mark read/star
    if auto_mark_read or auto_star:
        try:
            service.users().messages().batchModify(
                userId="me",
                body={
                    "ids": [e["id"] for e in final_emails],
                    "removeLabelIds": ["UNREAD"] if auto_mark_read else [],
                    "addLabelIds": ["STARRED"] if auto_star else []
                }
            ).execute()
        except Exception as e:
            warnings.append(f"Could not update labels: {str(e)}")

    # 6️⃣ Summarization
    summaries = []
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [
            executor.submit(summarize_email_threaded, e, i + 1, len(final_emails))
            for i, e in enumerate(final_emails)
        ]
        for f in as_completed(futures):
            summaries.append(f.result())

    # ── Create nice bullet-point formatted output ─────────────────────────────
    # Replace the entire formatting section with this:

    lines = ["Today's / Recent matching emails:"] if "today" in user_query.lower() else ["Matching emails:"]

    if not summaries:
        lines.append("  (no relevant emails found)")
    else:
        lines.append("")  # empty line after title
        
        for email in summaries:
            sender = email["sender"].split("<")[0].strip() if "<" in email["sender"] else email["sender"][:35]
            subj = (email["subject"][:65] + "…") if len(email["subject"]) > 65 else email["subject"]
            
            date_str = ""
            if email["date"] != "Unknown":
                try:
                    # Try to make date more readable
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(email["date"])
                    date_str = f"  ({dt.strftime('%b %d')})"
                except:
                    date_str = f"  ({email['date'][:10]})"
            
            line = f"• {sender} — {subj}{date_str}"
            if email["attachments"]:
                line += f"  📎{len(email['attachments'])}"
            lines.append(line)
            
            summ = email.get("summary", {}).get("summary", "").strip()
            if summ and summ != "[Unavailable]":
                summ = summ[:110] + "…" if len(summ) > 110 else summ
                lines.append(f"   ↳ {summ}")
            lines.append("")  # spacing between items

    formatted_result = "\n".join(lines)

    return {
        "status": "success",
        "result": summaries,                    # raw structured data
        "formatted_result": formatted_result,   # nice bullet points for display/print
        "query": user_query,
        "gmail_search_used": gmail_query,
        "warnings": warnings,
        "stats": {
            "candidates_fetched": len(message_ids),
            "final_shown": len(summaries)
        }
    }