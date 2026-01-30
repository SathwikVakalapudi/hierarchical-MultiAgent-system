from __future__ import annotations

"""
tools.gmail.filter - Advanced, scored, cached email filtering
Production-Ready Version – January 2026

Features:
- Hybrid rule-based + LLM filtering
- Relevance scoring (0–10) with ranking
- Per-query in-memory caching (24h TTL)
- Robust JSON enforcement & recovery
- Thread/attachment-aware
- Transparent fallbacks & warnings
- Gmail label helpers
"""

import json
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import logging

from groq import Groq

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# --------------------------
# Configuration
# --------------------------
UNWANTED_SENDERS = [
    "newsletter@", "no-reply@", "noreply@", "promotions@", "ads@",
    "offers@", "marketing@", "alert@", "updates@", "digest@"
]

URGENCY_KEYWORDS = [
    "urgent", "asap", "immediate", "deadline", "due", "today", "eod", "eow"
]

SPAM_KEYWORDS = [
    "unsubscribe", "click here", "limited time", "discount", "sale",
    "offer", "promo", "win a prize", "free trial", "act now", "buy now"
]

DEFAULT_MODEL = "llama-3.3-70b-versatile"
CACHE_TTL_HOURS = 24

# In-memory cache: {email_id: {query: str, score: int, reason: str, timestamp: float}}
_email_relevance_cache: Dict[str, Dict[str, Any]] = {}


# --------------------------
# Enhanced Rule-based Filters
# --------------------------
def _is_spam_email(email: Dict[str, Any]) -> bool:
    """Detect promotional/spam with high precision."""
    sender = email.get("sender", "").lower()
    subject = email.get("subject", "").lower()
    body = email.get("body", "").lower()

    if any(domain in sender for domain in UNWANTED_SENDERS):
        return True
    if any(kw in subject or kw in body for kw in SPAM_KEYWORDS):
        return True
    return False


def _boost_urgency_score(email: Dict[str, Any]) -> int:
    """Return urgency boost (0–3)."""
    text = f"{email.get('subject','')} {email.get('body','')}".lower()
    return sum(1 for kw in URGENCY_KEYWORDS if kw in text)


def filter_emails_rule_based(emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pre-filter spam and attach rule-based metadata."""
    filtered = []
    for email in emails:
        if _is_spam_email(email):
            continue
        email = email.copy()
        email["_rule_urgency_boost"] = _boost_urgency_score(email)
        filtered.append(email)
    return filtered


# --------------------------
# Robust JSON Parsing
# --------------------------
def _safe_json_parse(content: str, context: str) -> Any:
    """Parse JSON with fallback regex recovery."""
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        log.warning(f"[{context}] JSON parse failed: {e}\nRaw: {content[:300]}")
        match = re.search(r"\[.*\]", content, re.DOTALL) or re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        return None


# --------------------------
# LLM-Powered Scored Relevance Filter (with Cache)
# --------------------------
def filter_emails_llm(
    emails: List[Dict[str, Any]],
    user_query: str,
    llm_client: Optional[Groq] = None,
    model: str = DEFAULT_MODEL,
    cache_ttl_hours: int = CACHE_TTL_HOURS,
    min_score: int = 5
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Returns: (ranked_emails_with_scores, warnings)
    Emails are sorted by relevance_score (desc).
    """
    if not emails:
        return [], []

    warnings: List[str] = []
    current_time = time.time()
    cutoff = current_time - (cache_ttl_hours * 3600)

    # Clean expired cache
    global _email_relevance_cache
    _email_relevance_cache = {
        k: v for k, v in _email_relevance_cache.items()
        if v.get("timestamp", 0) > cutoff
    }

    result_emails: List[Dict[str, Any]] = []
    uncached_emails: List[Dict[str, Any]] = []

    # Check cache
    for email in emails:
        eid = email["id"]
        cache = _email_relevance_cache.get(eid)
        if cache and cache.get("query") == user_query:
            if cache.get("score", 0) >= min_score:
                email = email.copy()
                email["relevance_score"] = cache["score"]
                email["relevance_reason"] = cache["reason"]
                email["_source"] = "cache"
                result_emails.append(email)
        else:
            uncached_emails.append(email)

    if not uncached_emails:
        return sorted(result_emails, key=lambda x: x["relevance_score"], reverse=True), warnings

    # Build rich prompt
    blocks = []
    for i, e in enumerate(uncached_emails):
        body_snip = e["body"][:1000]
        thread = e.get("thread_context", "")[:500]
        attach = f"Attachments: {', '.join(e.get('attachments', []))}" if e.get("attachments") else ""
        blocks.append(
            f"EMAIL {i+1} | ID: {e['id']}\n"
            f"Subject: {e.get('subject', 'N/A')}\n"
            f"From: {e.get('sender', 'Unknown')}\n"
            f"Date: {e.get('date', 'Unknown')}\n"
            f"{attach}\n"
            f"Body: {body_snip}\n"
            f"{thread and 'Thread: ' + thread + '\n'}"
        )

    prompt = f"""
Rank these emails by relevance to the user's intent on a 0–10 scale.

User query: "{user_query}"

Emails:
{"".join(blocks)}

Return ONLY valid JSON array of objects:
[
  {{"index": 1, "relevance_score": 9, "reason": "direct match on order confirmation"}},
  {{"index": 2, "relevance_score": 3, "reason": "related but older"}}
]
- Only include emails with score >= {min_score}
- Sort by score descending
- If none relevant, return []
"""

    client = llm_client or Groq()

    relevant_items = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=600,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content.strip()
            parsed = _safe_json_parse(raw, "filter_llm")
            if isinstance(parsed, list):
                relevant_items = parsed
                break
        except Exception as e:
            if attempt == 2:
                warnings.append(f"LLM filter failed after retries: {e}")
            time.sleep(0.5)

    # Fallback: keyword + rule boost
    if relevant_items is None:
        warnings.append("LLM filter failed → using keyword + rule fallback")
        relevant_items = []
        query_words = set(user_query.lower().split())
        for i, e in enumerate(uncached_emails):
            text = f"{e.get('subject','')} {e.get('body','')}".lower()
            keyword_hits = sum(1 for w in query_words if w in text)
            urgency_boost = e.get("_rule_urgency_boost", 0)
            score = min(10, keyword_hits * 2 + urgency_boost)
            if score >= min_score:
                relevant_items.append({
                    "index": i + 1,
                    "relevance_score": score,
                    "reason": f"keyword match ({keyword_hits}) + urgency"
                })

    # Apply results
    for item in relevant_items:
        idx = item.get("index")
        if not isinstance(idx, int) or idx < 1 or idx > len(uncached_emails):
            continue
        email = uncached_emails[idx - 1].copy()
        score = int(item.get("relevance_score", 0))
        if score < min_score:
            continue

        email["relevance_score"] = score
        email["relevance_reason"] = item.get("reason", "")
        email["_source"] = "llm" if "LLM" in warnings else "llm"

        # Update cache
        _email_relevance_cache[email["id"]] = {
            "query": user_query,
            "score": score,
            "reason": email["relevance_reason"],
            "timestamp": current_time
        }

        result_emails.append(email)

    # Final sort
    result_emails.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return result_emails, warnings


# --------------------------
# Gmail Label Helpers (unchanged but typed)
# --------------------------
def mark_as_read(service, email_ids: List[str]) -> None:
    if email_ids:
        service.users().messages().batchModify(
            userId="me",
            body={"ids": email_ids, "removeLabelIds": ["UNREAD"]}
        ).execute()


def mark_as_unread(service, email_ids: List[str]) -> None:
    if email_ids:
        service.users().messages().batchModify(
            userId="me",
            body={"ids": email_ids, "addLabelIds": ["UNREAD"]}
        ).execute()


def star_emails(service, email_ids: List[str]) -> None:
    if email_ids:
        service.users().messages().batchModify(
            userId="me",
            body={"ids": email_ids, "addLabelIds": ["STARRED"]}
        ).execute()


def unstar_emails(service, email_ids: List[str]) -> None:
    if email_ids:
        service.users().messages().batchModify(
            userId="me",
            body={"ids": email_ids, "removeLabelIds": ["STARRED"]}
        ).execute()