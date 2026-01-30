# tools/calendar/service.py
# FINAL HYBRID VERSION – Production ready (Jan 2026)
# Consistent paths, reliable refresh, desktop OAuth flow

import json
import os
import requests
from typing import Optional
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ==================================================
# PATHS (all relative to this file = tools/calendar/)
# ==================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CREDS_FILE = os.path.join(BASE_DIR, "credentials.json")   # or "google_calendar.json" if you prefer
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

SCOPES = ["https://www.googleapis.com/auth/calendar"]


# ==================================================
# EARLY VALIDATION
# ==================================================
if not os.path.exists(CREDS_FILE):
    raise FileNotFoundError(
        f"Missing OAuth credentials file: {CREDS_FILE}\n"
        "Download from Google Cloud Console → Credentials → OAuth 2.0 Client IDs → Desktop app type"
    )

# Quick format check
# ==================================================
# Expose client credentials (needed only for legacy bootstrap_oauth)
# ==================================================
# ==================================================
# Expose credentials for auth_bootstrap.py (legacy support)
# ==================================================
with open(CREDS_FILE, 'r') as f:
    creds_data = json.load(f)
_client = creds_data.get("installed") or creds_data.get("web")
CLIENT_ID = _client["client_id"]
CLIENT_SECRET = _client["client_secret"]
REDIRECT_URI = _client["redirect_uris"][0]

# ==================================================
# TOKEN MANAGEMENT
# ==================================================
def is_calendar_authenticated() -> bool:
    """Check if we have a token file."""
    return os.path.exists(TOKEN_FILE)


def load_tokens() -> Optional[dict]:
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[CalendarAuth] Failed to load {TOKEN_FILE}: {e}")
        return None


def save_tokens(access_token: str, refresh_token: Optional[str] = None, expires_in: int = 3600):
    """Save or update token.json – preserves existing refresh_token if not provided."""
    existing = load_tokens() or {}
    refresh_token = refresh_token or existing.get("refresh_token")

    data = {
        "token": access_token,
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": existing.get("client_id") or "unknown",
        "client_secret": existing.get("client_secret") or "unknown",
        "scopes": SCOPES,
        "expiry": (datetime.now() + timedelta(seconds=expires_in)).isoformat(),
    }

    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"[CalendarAuth] Tokens saved/updated → {TOKEN_FILE}")


# ==================================================
# MAIN SERVICE FACTORY – auto-authenticates
# ==================================================
def get_calendar_service():
    creds = None

    # 1. Try existing token.json (preferred)
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"[CalendarAuth] Invalid/malformed token.json: {e}")

    # 2. Refresh if expired but has refresh_token
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            print("[CalendarAuth] Token refreshed successfully")
            # Optional: save refreshed token
            save_tokens(creds.token, creds.refresh_token, creds.expiry.timestamp() - datetime.now().timestamp())
        except Exception as e:
            print(f"[CalendarAuth] Refresh failed: {e} → falling back to full OAuth flow")

    # 3. Full OAuth flow if no creds / refresh failed
    if not creds or not creds.valid:
        print("[CalendarAuth] Starting interactive OAuth flow (browser will open)...")
        flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

        # Save the fresh credentials
        with open(TOKEN_FILE, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())
        print(f"[CalendarAuth] New token saved → {TOKEN_FILE}")

    # Build and return service
    try:
        service = build("calendar", "v3", credentials=creds)
        print("[CalendarAuth] Google Calendar service initialized successfully")
        return service
    except HttpError as e:
        raise RuntimeError(f"Failed to build Calendar service: {e}")


# ==================================================
# MANUAL REFRESH / ACCESS TOKEN (if needed elsewhere)
# ==================================================
def get_access_token() -> str:
    tokens = load_tokens()
    if not tokens:
        raise RuntimeError("No tokens found. Run get_calendar_service() first to authenticate.")

    expired = True
    if "expiry" in tokens:
        try:
            expiry_dt = datetime.fromisoformat(tokens["expiry"].replace("Z", ""))
            expired = datetime.now() >= expiry_dt
        except Exception:
            expired = True

    if expired and tokens.get("refresh_token"):
        payload = {
            "client_id": tokens.get("client_id", ""),
            "client_secret": tokens.get("client_secret", ""),
            "refresh_token": tokens["refresh_token"],
            "grant_type": "refresh_token",
        }
        r = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=10).json()

        if "access_token" not in r:
            raise RuntimeError(f"Token refresh failed: {r.get('error_description', r)}")

        save_tokens(r["access_token"], tokens["refresh_token"], r["expires_in"])
        return r["access_token"]

    if "token" not in tokens:
        raise RuntimeError("No valid access token available.")

    return tokens["token"]