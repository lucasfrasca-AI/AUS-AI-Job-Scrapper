"""
Appends an enriched job dict to the correct Google Sheet tab.
Checks for duplicates (apply_url or job_id) before appending.

Input: enriched job dict as JSON on stdin
Output: {"status": "added"} or {"status": "skipped"} to stdout

Sheet: "AU Job Board"
Tabs:  "Cybersecurity Jobs" | "AI Jobs"
Columns: Date Added | Title | Company | Job Type | Level | Location | Remote Flag |
         Salary | Date Posted | Source | Apply URL | Key Requirements
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

SHEET_MAP = {
    "Cybersecurity": "Cybersecurity Jobs",
    "AI": "AI Jobs",
}

HEADERS = [
    "Date Added", "Title", "Company", "Job Type", "Level",
    "Location", "Remote Flag", "Salary", "Date Posted",
    "Source", "Apply URL", "Key Requirements",
]

HEADER_BG = {"red": 0.812, "green": 0.886, "blue": 0.953}  # #CFE2F3

LEVEL_COLOURS = {
    "Entry/Junior": {"red": 0.851, "green": 0.918, "blue": 0.827},   # #D9EAD3
    "Mid-level":    {"red": 1.0,   "green": 0.949, "blue": 0.800},   # #FFF2CC
    "Senior":       {"red": 0.988, "green": 0.898, "blue": 0.804},   # #FCE5CD
}


def get_credentials() -> Credentials:
    creds = None
    token_path = Path(TOKEN_FILE)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(CREDENTIALS_FILE).exists():
                print(
                    f"ERROR: {CREDENTIALS_FILE} not found. "
                    "Download OAuth credentials from Google Cloud Console.",
                    file=sys.stderr,
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return creds


def get_or_create_sheet(service, spreadsheet_id: str, sheet_name: str) -> int:
    """Returns the sheetId for the named tab, creating it if missing."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = meta.get("sheets", [])

    for sheet in sheets:
        props = sheet.get("properties", {})
        if props.get("title") == sheet_name:
            return props["sheetId"]

    # Create the sheet tab
    body = {"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}
    resp = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body=body
    ).execute()
    new_sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]

    # Write headers
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1",
        valueInputOption="RAW",
        body={"values": [HEADERS]},
    ).execute()

    # Freeze row 1
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": new_sheet_id,
                            "gridProperties": {"frozenRowCount": 1},
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                }
            ]
        },
    ).execute()

    # Header background colour
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": new_sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": HEADER_BG,
                                "textFormat": {"bold": True},
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat)",
                    }
                }
            ]
        },
    ).execute()

    return new_sheet_id


def get_existing_values(service, spreadsheet_id: str, sheet_name: str) -> list[list]:
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A:L",
        ).execute()
        return result.get("values", [])
    except HttpError:
        return []


def is_duplicate(existing_rows: list[list], apply_url: str, job_id: str) -> bool:
    for row in existing_rows[1:]:  # skip header
        if len(row) >= 11:
            existing_url = row[10] if len(row) > 10 else ""
            if existing_url and existing_url == apply_url:
                return True
    return False


def append_row(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    sheet_id: int,
    job: dict,
) -> None:
    row = [
        job.get("date_added", ""),
        job.get("title", ""),
        job.get("company", ""),
        job.get("job_type", ""),
        job.get("level", ""),
        job.get("location", ""),
        job.get("remote_flag", ""),
        job.get("salary", "Not listed"),
        job.get("date_posted", ""),
        job.get("source", ""),
        job.get("apply_url", ""),
        job.get("key_requirements", ""),
    ]

    append_resp = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A:L",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    # Determine which row was just appended
    updated_range = append_resp.get("updates", {}).get("updatedRange", "")
    try:
        row_num = int(updated_range.split("!")[1].split(":")[0][1:]) - 1  # 0-indexed
    except (IndexError, ValueError):
        return

    # Apply row background colour based on level
    level = job.get("level", "Mid-level")
    colour = LEVEL_COLOURS.get(level, LEVEL_COLOURS["Mid-level"])

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row_num,
                            "endRowIndex": row_num + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {"backgroundColor": colour}
                        },
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                }
            ]
        },
    ).execute()


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"error": "No input provided"}), file=sys.stderr)
        sys.exit(1)

    try:
        job = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        sys.exit(1)

    field = job.get("field", "")
    sheet_name = SHEET_MAP.get(field)
    if not sheet_name:
        print(json.dumps({"error": f"Unknown field: {field}"}), file=sys.stderr)
        sys.exit(1)

    if not SPREADSHEET_ID:
        print(
            "ERROR: GOOGLE_SHEET_ID not set in .env", file=sys.stderr
        )
        sys.exit(1)

    try:
        creds = get_credentials()
        service = build("sheets", "v4", credentials=creds)

        sheet_id = get_or_create_sheet(service, SPREADSHEET_ID, sheet_name)
        existing = get_existing_values(service, SPREADSHEET_ID, sheet_name)

        apply_url = job.get("apply_url", "")
        job_id = job.get("job_id", "")

        if is_duplicate(existing, apply_url, job_id):
            print(json.dumps({"status": "skipped"}))
            return

        append_row(service, SPREADSHEET_ID, sheet_name, sheet_id, job)
        print(json.dumps({"status": "added"}))

    except HttpError as e:
        print(json.dumps({"error": f"Sheets API error: {e}"}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
