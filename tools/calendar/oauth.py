import requests
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode

from tools.calendar.service import (
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    save_tokens
)

router = APIRouter()

AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPES = ["https://www.googleapis.com/auth/calendar"]


@router.get("/oauth/login")
def oauth_login():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent"
    }
    return RedirectResponse(f"{AUTH_URL}?{urlencode(params)}")


@router.get("/oauth/callback")
def oauth_callback(code: str):
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }

    r = requests.post(TOKEN_URL, data=data, timeout=10).json()

    if "access_token" not in r:
        return {
            "status": "error",
            "details": r
        }

    save_tokens(
        r["access_token"],
        r.get("refresh_token"),
        r["expires_in"]
    )


    return {"status": "Google Calendar connected successfully"}
