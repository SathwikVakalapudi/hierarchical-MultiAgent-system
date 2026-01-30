from __future__ import annotations

"""
tools.gmail.llm - Pure LLM functions for Gmail intelligence
GLOBAL CLIENT VERSION – January 2026
"""

from typing import Dict, Any, List, Tuple
import json
import re
import time
from datetime import datetime, timedelta

from groq import Groq

# ------------------------------------------------------------------
# GLOBAL CONFIG
# ------------------------------------------------------------------

DEFAULT_MODEL = "llama-3.3-70b-versatile"

# SINGLE GLOBAL CLIENT (recommended pattern)
client = Groq(
    api_key="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"
)

# ------------------------------------------------------------------
# UTIL
# ------------------------------------------------------------------

def _safe_json_parse(content: str, function_name: str) -> Dict[str, Any] | None:
    """
    Safely parse LLM output as JSON with fallback regex cleanup.
    """
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        # Try to extract the JSON-like block
        match = re.search(r'\{.*\}', content, re.DOTALL)
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

Return ONLY valid JSON object with these keys:
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
  "clarification_needed": str or null (only if ambiguous)
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
            parsed = _safe_json_parse(response.choices[0].message.content.strip(), "parse_user_query")
            if parsed:
                return parsed
        except Exception as e:
            print(f"[parse_user_query] attempt {attempt+1} failed: {e}")
            time.sleep(0.8)

    # Hard fallback
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
    """Convert parsed filters to Gmail search syntax."""
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
    """Summarize email content and classify intent using LLM."""
    prompt = f"""
Summarize this email clearly and analyze its intent.

Subject: {subject}
From: {sender}
Body excerpt: {body[:6000]}
Thread context: {thread_context[:1000]}

Return ONLY valid JSON:
{{
  "summary": "1-2 sentence clear summary",
  "tone": "positive|negative|neutral|urgent|formal|friendly|other",
  "urgency": "low|medium|high",
  "action_required": true|false,
  "key_points": ["point 1", "point 2", ...]
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
            parsed = _safe_json_parse(response.choices[0].message.content.strip(), "summarize_email")
            if parsed:
                parsed.setdefault("fallback_used", False)
                return parsed
        except Exception as e:
            print(f"[summarize_email] attempt {attempt+1} failed: {e}")
        time.sleep(0.6)

    # Fallback
    return {
        "summary": f"{subject} from {sender}",
        "tone": "neutral",
        "urgency": "low",
        "action_required": False,
        "key_points": [],
        "fallback_used": True
    }

# ------------------------------------------------------------------
# REAL MESSAGE EXTRACTION (rule-based)
# ------------------------------------------------------------------

def extract_real_message(raw: str) -> Tuple[str | None, str | None]:
    """
    Rule-based extraction of the actual message content from natural language input.
    Returns (suggested_subject, real_content) or (None, None)
    """
    if not raw:
        return None, None

    raw_lower = raw.lower()

    # Common patterns: "send ... saying ...", "email ... about ...", etc.
    separators = [
        r'\bsay(?:ing|in)?\b',
        r'\b(?:regarding|about|on|for)\b',
        r':\s*',
        r'[-–—]\s*',
        r'\bthat\b',
    ]

    for pattern in separators:
        parts = re.split(pattern, raw, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            before, after = parts
            after = after.strip().strip('"').strip("'").strip()
            if len(after) > 3:
                # Guess subject
                if any(w in before.lower() for w in ['leave', 'sick', 'fever', 'absent', 'medical']):
                    subject = "Leave Request"
                elif any(w in before.lower() for w in ['urgent', 'important', 'asap']):
                    subject = "Urgent Message"
                elif 'meeting' in before.lower():
                    subject = "Meeting Update"
                else:
                    subject = "Message"
                return subject, after

    # Fallback: after email address
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', raw)
    if email_match:
        after_email = raw[email_match.end():].strip()
        after_email = re.sub(r'^(?:regarding|about|saying|that|:|-|–|—)\s*', '', after_email, flags=re.I)
        after_email = after_email.strip().strip('"').strip("'")
        if len(after_email) > 3:
            return "Message", after_email

    return None, None

# ------------------------------------------------------------------
# EMAIL REWRITER
# ------------------------------------------------------------------

def rewrite_email(body_text: str = "") -> Dict[str, str]:
    """Turn raw user input into polished email (subject + body)."""
    raw = (body_text or "").strip()
    if not raw:
        return {"subject": "Empty Message", "body": "(no content)"}

    prompt = f"""
USER INPUT: "{raw}"

TASK: Rewrite into a complete, polished, professional email.

RULES:
1. Expand appropriately: routine → 2-3 sentences, situational → 3-4, social/sarcastic → witty 4-5
2. Preserve key user words (sick, pls, urgent, etc.)
3. Start with "Hi [Name]," — end with "Best regards, Sathwik"
4. No meta phrases like "send mail saying"
5. Keep natural tone

RETURN ONLY JSON:
{{
  "subject": "Professional subject line",
  "body": "Full email body"
}}
"""

    system = (
        "You are an elite ghostwriter. "
        "Transform raw thoughts into intelligent, articulate emails."
    )

    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        parsed = json.loads(content)
        return {
            "subject": parsed.get("subject", "Message"),
            "body": parsed.get("body", raw)
        }
    except Exception as e:
        print(f"[rewrite_email] failed: {e}")
        return {"subject": "Message", "body": raw}

# ------------------------------------------------------------------
# EMAIL FILTER (LLM ranking)
# ------------------------------------------------------------------

def filter_emails_llm(
    emails: List[Dict[str, Any]],
    user_query: str
) -> List[Dict[str, Any]]:
    """Rank emails by relevance to user query using LLM."""
    if not emails:
        return []

    snippets = [
        f"{i+1}. {e.get('subject','')} — from {e.get('sender','')}"
        for i, e in enumerate(emails[:15])
    ]

    prompt = f"""
Rank these emails by relevance to the user query (0–10 scale).

User query: "{user_query}"

Emails:
{"\n".join(snippets)}

Return ONLY JSON array of objects with score >= 5:
[
  {{"index": 1, "relevance_score": 8, "reason": "short reason"}}
]
"""

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            parsed = _safe_json_parse(response.choices[0].message.content.strip(), "filter_emails_llm")
            if isinstance(parsed, list):
                scored = []
                for item in parsed:
                    idx = item.get("index")
                    if isinstance(idx, int) and 1 <= idx <= len(emails):
                        e = emails[idx - 1].copy()
                        e["relevance_score"] = item.get("relevance_score", 0)
                        e["relevance_reason"] = item.get("reason", "")
                        scored.append(e)
                return sorted(scored, key=lambda x: x["relevance_score"], reverse=True)
        except Exception:
            time.sleep(0.5)

    return emails[:10]

# ------------------------------------------------------------------
# RECIPIENT EXTRACTION (LLM + rule-based hybrid)
# ------------------------------------------------------------------

def extract_recipients(text: str) -> Dict[str, Any]:
    """
    Extract recipients from natural language input.
    Supports: "send to thanujram@gmail.com", "email boss and john", etc.
    """
    # Step 1: Fast regex for obvious emails
    email_pattern = r'[\w\.-]+@[\w\.-]+\.[\w]+'
    found_emails = re.findall(email_pattern, text)

    # Step 2: If we have clear emails → use them
    if found_emails:
        main = found_emails[0]
        return {
            "emails": found_emails,
            "main_recipient": main,
            "cc_candidates": found_emails[1:] if len(found_emails) > 1 else [],
            "guessed": [],
            "reasoning": "Found explicit email addresses in text"
        }

    # Step 3: LLM fallback for name-based extraction
    prompt = f"""
Extract email recipients from this natural language input:

Text: "{text}"

Rules:
- Find any explicit email addresses
- If only names → guess likely emails (gmail.com > yahoo.com > outlook.com)
- Identify main recipient (first after "to"/"send"/"email")
- Detect possible CC/BCC mentions

Return ONLY JSON:
{{
  "emails": ["email1@gmail.com", ...],
  "main_recipient": "primary@email.com" or null,
  "cc_candidates": ["cc1", "cc2"],
  "guessed": ["name@gmail.com", ...],
  "reasoning": "brief explanation"
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
            parsed = _safe_json_parse(response.choices[0].message.content.strip(), "extract_recipients")
            if parsed and isinstance(parsed, dict):
                parsed.setdefault("emails", [])
                parsed.setdefault("main_recipient", None)
                parsed.setdefault("cc_candidates", [])
                parsed.setdefault("guessed", [])
                parsed.setdefault("reasoning", "No clear recipients found")
                return parsed
        except Exception as e:
            print(f"[extract_recipients] attempt {attempt+1} failed: {e}")
            time.sleep(0.7)

    # Ultimate fallback
    return {
        "emails": [],
        "main_recipient": None,
        "cc_candidates": [],
        "guessed": [],
        "reasoning": "No recipients could be extracted"
    }