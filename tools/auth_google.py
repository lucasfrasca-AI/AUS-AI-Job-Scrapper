"""
One-time Google OAuth setup. Run this once to authenticate and save token.json.
Usage: python tools/auth_google.py
"""

from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def main():
    token_path = Path(TOKEN_FILE)
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        print("Already authenticated. token.json is valid — no action needed.")
        return

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        print("Token refreshed successfully.")
    else:
        if not Path(CREDENTIALS_FILE).exists():
            print(f"ERROR: {CREDENTIALS_FILE} not found in project root.")
            print("Download it from Google Cloud Console → APIs & Services → Credentials.")
            return
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        print("Authentication successful!")

    token_path.write_text(creds.to_json())
    print("token.json saved. You are ready to run the scrapers.")


if __name__ == "__main__":
    main()
