# tools/calendar/auth_bootstrap.py
# Manual OAuth flow – prints URL, user pastes code

import requests
from urllib.parse import urlencode

from .service import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, save_tokens

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def bootstrap_oauth():
    """
    One-time manual OAuth bootstrap.
    Opens auth URL → paste code from browser → tokens saved.
    """
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }

    auth_url = f"{AUTH_URL}?{urlencode(params)}"

    print("\n=== Google Calendar OAuth Bootstrap ===")
    print("1. Open this URL in your browser:")
    print(auth_url)
    print("\n2. Sign in → allow access → you'll be redirected")
    print("3. Copy the 'code' from the URL bar (after ?code=...)")
    print("4. Paste it below\n")

    code = input("Paste the authorization code: ").strip()

    if not code:
        print("No code provided. Aborted.")
        return

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }

    try:
        r = requests.post(TOKEN_URL, data=data, timeout=15).json()
        if "access_token" not in r:
            raise Exception(f"OAuth error: {r.get('error_description', r)}")

        save_tokens(
            access_token=r["access_token"],
            refresh_token=r.get("refresh_token"),
            expires_in=r.get("expires_in", 3600),
        )
        print("\nSuccess! Tokens saved to token.json")
        print("You can now use calendar features normally.")
    except Exception as e:
        print(f"\nFailed: {e}")