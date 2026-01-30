import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send"
]

def get_gmail_service():
    # Use the current folder (tools/gmail/) for credentials
    folder = os.path.dirname(__file__)
    token_path = os.path.join(folder, "token.json")
    secret_path = os.path.join(folder, "client_secret.json")

    creds = None

    # Load existing token
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # If no token or invalid → run OAuth flow
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
        creds = flow.run_local_server(
            port=8080,
            prompt='consent',
            access_type='offline'
        )

        # Save token for next runs
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    # Build Gmail service object
    service = build("gmail", "v1", credentials=creds)
    return service
