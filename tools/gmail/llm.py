from __future__ import annotations

"""
tools.gmail.llm - Pure LLM functions for Gmail intelligence
FINAL PRODUCTION VERSION – January 2026
"""

from typing import Dict, Any, List, Tuple
import json
import re
import time

from groq import Groq

# ------------------------------------------------------------------
# GLOBAL CONFIG
# ------------------------------------------------------------------

DEFAULT_MODEL = "llama-3.3-70b-versatile"

# SINGLE GLOBAL CLIENT
client = Groq(
    api_key="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"
)

# ------------------------------------------------------------------
# UTIL
# ------------------------------------------------------------------

def _safe_json_parse(content: str, function_name: str) -> Dict[str, Any] | List[Any] | None:
    """
    Safely parse LLM output as JSON (object OR array) with regex fallback.
    """
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}|\[.*\]', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        print(f"[{function_name}] JSON parse failed. Raw: {content[:200]}...")
        return None

# ------------------------------------------------------------------
# QUERY PARSER
# ------------------------------------------------------------------

def parse_user_query(user_query: str) -> Dict[str, Any]:
    """
    Parse natural language Gmail search query into structured filters using LLM.
    """
    prompt = f"""
You are an expert Gmail query parser.

User query: "{user_query}"

Return ONLY valid JSON:
{{
  "keywords": str or null,
  "from": str or null,
  "subject": str or null,
  "is_unread": bool,
  "has_attachment": bool,
  "last_n_days": int or null,
  "before_date": "YYYY/MM/DD" or null,
  "action_required": bool,
  "inbox": bool,
  "clarification_needed": str or null
}}
"""

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=250,
                response_format={"type": "json_object"},
            )
            parsed = _safe_json_parse(
                response.choices[0].message.content,
                "parse_user_query"
            )
            if isinstance(parsed, dict):
                return parsed
        except Exception as e:
            print(f"[parse_user_query] attempt {attempt+1} failed: {e}")
            time.sleep(0.8)

    return {
        "keywords": user_query,
        "from": None,
        "subject": None,
        "is_unread": False,
        "has_attachment": False,
        "last_n_days": None,
        "before_date": None,
        "action_required": False,
        "inbox": True,
        "clarification_needed": None
    }

# ------------------------------------------------------------------
# GMAIL QUERY BUILDER
# ------------------------------------------------------------------

def build_gmail_query(filters: Dict[str, Any]) -> str:
    parts = []

    if filters.get("keywords"):
        parts.append(f'"{filters["keywords"]}"')
    if filters.get("from"):
        parts.append(f"from:{filters['from']}")
    if filters.get("subject"):
        parts.append(f"subject:{filters['subject']}")
    if filters.get("is_unread"):
        parts.append("is:unread")
    if filters.get("has_attachment"):
        parts.append("has:attachment")
    if filters.get("inbox"):
        parts.append("in:inbox")
    if filters.get("last_n_days"):
        parts.append(f"newer_than:{filters['last_n_days']}d")
    if filters.get("before_date"):
        parts.append(f"before:{filters['before_date']}")

    return " ".join(parts) or "in:inbox"

# ------------------------------------------------------------------
# EMAIL SUMMARY
# ------------------------------------------------------------------

def summarize_email(
    subject: str,
    sender: str,
    body: str,
    thread_context: str = ""
) -> Dict[str, Any]:
    prompt = f"""
Summarize this email clearly and analyze intent.

Subject: {subject}
From: {sender}
Body: {body[:6000]}
Thread context: {thread_context[:1000]}

Return ONLY JSON:
{{
  "summary": "...",
  "tone": "...",
  "urgency": "low|medium|high",
  "action_required": true|false,
  "key_points": []
}}
"""

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            parsed = _safe_json_parse(
                response.choices[0].message.content,
                "summarize_email"
            )
            if isinstance(parsed, dict):
                parsed.setdefault("fallback_used", False)
                return parsed
        except Exception as e:
            print(f"[summarize_email] attempt {attempt+1} failed: {e}")
        time.sleep(0.6)

    return {
        "summary": f"{subject} from {sender}",
        "tone": "neutral",
        "urgency": "low",
        "action_required": False,
        "key_points": [],
        "fallback_used": True
    }

# ------------------------------------------------------------------
# EMAIL REWRITER (FIXED SIGNATURE)
# ------------------------------------------------------------------

def rewrite_email(
    body_text: str,
    subject: str | None = None,
    context: str = "",
    style: str = "natural"
) -> Dict[str, str]:
    """
    Rewrite raw text into a polished email.
    Compatible with EmailAgent.
    """

    raw = (body_text or "").strip()
    if not raw:
        return {"subject": subject or "Message", "body": "(no content)"}

    prompt = f"""
USER INPUT:
{raw}

CONTEXT:
{context}

STYLE:
{style}

Rewrite into a complete, professional email.

Return ONLY JSON:
{{
  "subject": "...",
  "body": "..."
}}
"""

    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert email writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=700,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)
        return {
            "subject": parsed.get("subject", subject or "Message"),
            "body": parsed.get("body", raw)
        }
    except Exception as e:
        print(f"[rewrite_email] failed: {e}")
        return {
            "subject": subject or "Message",
            "body": raw
        }

# ------------------------------------------------------------------
# EMAIL FILTER (FIXED JSON ARRAY HANDLING)
# ------------------------------------------------------------------

def filter_emails_llm(
    emails: List[Dict[str, Any]],
    user_query: str
) -> List[Dict[str, Any]]:
    if not emails:
        return []

    snippets = [
        f"{i+1}. {e.get('subject','')} — from {e.get('sender','')}"
        for i, e in enumerate(emails[:15])
    ]

    prompt = f"""
Rank emails by relevance (0–10).

User query: "{user_query}"

Emails:
{chr(10).join(snippets)}

Return JSON ARRAY ONLY:
[
  {{"index": 1, "relevance_score": 8, "reason": "..."}}
]
"""

    for _ in range(3):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=400,
            )
            parsed = _safe_json_parse(
                response.choices[0].message.content,
                "filter_emails_llm"
            )

            if isinstance(parsed, list):
                ranked = []
                for item in parsed:
                    idx = item.get("index")
                    if isinstance(idx, int) and 1 <= idx <= len(emails):
                        e = emails[idx - 1].copy()
                        e["relevance_score"] = item.get("relevance_score", 0)
                        e["relevance_reason"] = item.get("reason", "")
                        ranked.append(e)
                return sorted(ranked, key=lambda x: x["relevance_score"], reverse=True)
        except Exception:
            time.sleep(0.5)

    return emails[:10]

# ------------------------------------------------------------------
# RECIPIENT EXTRACTION (FIXED: STRING + DICT SAFE)
# ------------------------------------------------------------------

def extract_recipients(text: str | Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract recipients from string OR structured input.
    """

    if isinstance(text, dict):
        text = (
            text.get("body")
            or text.get("text")
            or text.get("content")
            or ""
        )
    else:
        text = text or ""

    email_pattern = r'[\w\.-]+@[\w\.-]+\.[\w]+'
    found_emails = re.findall(email_pattern, text)

    if found_emails:
        return {
            "emails": found_emails,
            "main_recipient": found_emails[0],
            "cc_candidates": found_emails[1:],
            "guessed": [],
            "reasoning": "Explicit email address(es) found"
        }

    prompt = f"""
Extract email recipients from this text:

"{text}"

Return ONLY JSON:
{{
  "emails": [],
  "main_recipient": null,
  "cc_candidates": [],
  "guessed": [],
  "reasoning": "..."
}}
"""

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.15,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            parsed = _safe_json_parse(
                response.choices[0].message.content,
                "extract_recipients"
            )
            if isinstance(parsed, dict):
                parsed.setdefault("emails", [])
                parsed.setdefault("main_recipient", None)
                parsed.setdefault("cc_candidates", [])
                parsed.setdefault("guessed", [])
                parsed.setdefault("reasoning", "LLM inference")
                return parsed
        except Exception as e:
            print(f"[extract_recipients] attempt {attempt+1} failed: {e}")
            time.sleep(0.6)

    return {
        "emails": [],
        "main_recipient": None,
        "cc_candidates": [],
        "guessed": [],
        "reasoning": "No recipients found"
    }
