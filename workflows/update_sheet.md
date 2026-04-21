# Workflow: Update Google Sheet

## Objective
Append new, categorized job rows to the "AU Job Board" Google Sheet. Prevent duplicates, apply row colours by seniority level, and maintain the correct column structure.

## Sheet Details
- **Spreadsheet name:** AU Job Board (identified by `GOOGLE_SHEET_ID` in `.env`)
- **Tab: Cybersecurity Jobs** — receives jobs with `field = "Cybersecurity"`
- **Tab: AI Jobs** — receives jobs with `field = "AI"`

---

## Column Structure (both tabs)

| Col | Header | Source field |
|---|---|---|
| A | Date Added | `date_added` (UTC ISO) |
| B | Title | `title` |
| C | Company | `company` |
| D | Job Type | `job_type` |
| E | Level | `level` |
| F | Location | `location` |
| G | Remote Flag | `remote_flag` |
| H | Salary | `salary` |
| I | Date Posted | `date_posted` |
| J | Source | `source` |
| K | Apply URL | `apply_url` |
| L | Key Requirements | `key_requirements` |

- Row 1 is frozen as a header row
- Header background: `#CFE2F3` (light blue), bold text

---

## Row Colour Scheme

| Level | Colour | Hex |
|---|---|---|
| Entry/Junior | Light green | `#D9EAD3` |
| Mid-level | Light yellow | `#FFF2CC` |
| Senior | Light orange | `#FCE5CD` |

Colour is applied immediately after each row is appended via `batchUpdate → repeatCell`.

---

## Deduplication Logic

Before any row is appended, `sheets_append.py` reads all existing values from the target tab and checks:
- **Column K (Apply URL):** if any existing row has the same `apply_url`, the job is skipped
- If duplicate detected → returns `{"status": "skipped"}` and exits cleanly

This check happens on every `processJob` run. The Google Sheets API call reads all rows (column A:L) each time — acceptable at the expected volume (~hundreds of jobs/week).

---

## Google OAuth Setup

Complete this once before the first run:

1. **Enable the Sheets API:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create or select a project
   - Go to **APIs & Services → Library** → search "Google Sheets API" → Enable

2. **Create OAuth credentials:**
   - Go to **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth 2.0 Client IDs**
   - Application type: **Desktop app**
   - Download the JSON file → rename to `credentials.json` → place in project root

3. **First-time auth:**
   - Run: `echo '{"title":"test","company":"test","source":"SEEK","field":"Cybersecurity","location":"Sydney","salary":"Not listed","date_posted":"","apply_url":"https://test.com","description":"","job_id":"test001","job_type":"Other Cybersecurity","level":"Mid-level","remote_flag":"Remote","key_requirements":"","date_added":"2026-01-01T00:00:00+00:00"}' | python tools/sheets_append.py`
   - A browser window will open → sign in → authorize access
   - `token.json` is saved automatically — future runs use it without prompting

4. **Set the sheet ID:**
   - Open your Google Sheet in the browser
   - Copy the ID from the URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`
   - Add to `.env`: `GOOGLE_SHEET_ID={SHEET_ID}`

---

## Adding New Job Types

To add a new job type to the categorization:

1. Open `tools/categorize_job.py`
2. For **Cybersecurity**: add a new entry to `CYBER_PATTERNS` list:
   ```python
   (re.compile(r"devsecops|devops security", re.I), "DevSecOps"),
   ```
3. For **AI**: add to `AI_PATTERNS` list similarly
4. The new type will appear in column D going forward

---

## Adding New Sources / Sites

1. Create `tools/scrape_{site}.py` following the same CLI interface:
   - Args: `--query`, `--field`, optional `--since`
   - Output: JSON list to stdout with the standard raw job dict schema
2. Add the site name to the `SCRAPERS` list in `tools/run_all_scrapers.py`
3. Document site-specific quirks and rate limits in `workflows/scrape_jobs.md`

---

## Changing the Target Sheet

1. Create a new Google Sheet (or use an existing one)
2. Update `GOOGLE_SHEET_ID` in `.env`
3. The tabs "Cybersecurity Jobs" and "AI Jobs" will be created automatically on first run

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `credentials.json` not found | Download from Google Cloud Console → save to project root |
| `token.json` expired / invalid | Delete `token.json` and re-run to trigger new auth flow |
| `GOOGLE_SHEET_ID` missing | Set in `.env` |
| Duplicate rows appearing | Check dedup logic in `sheets_append.py → is_duplicate()` — verify Apply URL column is K (index 10) |
| Header row missing colours | Manually delete the tab in Google Sheets and re-run — `get_or_create_sheet()` will rebuild it |
| Row colours not applying | Check the `updated_range` parse in `append_row()` — row index arithmetic may need adjusting for your sheet |

---

## Cloud Deployment Note

If running via Trigger.dev cloud (not `trigger dev` locally), `.tmp/last_run.json` will NOT persist between runs because task containers are ephemeral. Options:

1. **Accept full re-scrapes weekly** — dedup in `sheets_append.py` prevents duplicate rows, so this is safe
2. **Store lastRun in sheet:** add a "Metadata" tab with cell A1 = lastRun timestamp; update `check-jobs.ts` to read/write from that cell instead of `.tmp/last_run.json`
