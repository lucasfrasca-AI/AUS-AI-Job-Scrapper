**# AUS-AI-Job-Scrapper**# AUS AI Job Scrapper

An automated job scraping pipeline built on the WAT framework (Workflows, Agents, Tools).
Scrapes Australian AI job listings, processes them via Claude AI, and writes results
directly to Google Sheets — orchestrated by Trigger.dev scheduled tasks.

## Architecture

```
Trigger.dev Scheduled Task (cron)
        ↓
check-task.ts       → polls job sources, dispatches per-job tasks
        ↓
process-item.ts     → scrapes, enriches, deduplicates each listing
        ↓
tools/ (Python)     → deterministic execution: scraping, Sheets write
        ↓
Google Sheets       → final output accessible from anywhere
```

The WAT framework separates concerns: Claude handles reasoning and orchestration,
Python scripts handle deterministic execution, Trigger.dev handles scheduling and
reliability.

## Stack

| Layer | Technology |
|---|---|
| Scheduling & orchestration | Trigger.dev SDK v4 |
| Job scraping | Python + BeautifulSoup4 + lxml |
| Google Sheets output | Google Sheets API v4 (OAuth) |
| Language | TypeScript (tasks) + Python (tools) |
| Auth | Google OAuth 2.0 — credentials stored locally, never committed |

## Setup

```bash
# Install Node dependencies
npm install

# Install Python dependencies
pip install -r requirements.txt

# Create .env in project root
TRIGGER_PROJECT_ID=your_project_id
TRIGGER_SECRET_KEY=your_secret_key
GOOGLE_SHEETS_ID=your_sheet_id

# Add Google OAuth credentials
# Download credentials.json from Google Cloud Console
# Run auth once to generate token.json
```

## Usage

```bash
# Local development
npm run dev

# Deploy to Trigger.dev cloud
npm run deploy
```

## Project Structure

```
AUS-AI-Job-Scrapper/
├── .env                    # API keys — never committed
├── credentials.json        # Google OAuth — never committed
├── token.json              # Google OAuth token — never committed
├── trigger.config.ts       # Trigger.dev project config
├── tsconfig.json
├── package.json
├── requirements.txt        # Python dependencies
├── mcp.json                # MCP server config
├── trigger/                # Trigger.dev task definitions
│   └── *.ts
├── tools/                  # Python scripts for deterministic execution
│   └── *.py
├── workflows/              # Markdown SOPs defining agent behaviour
│   └── *.md
└── .tmp/                   # Intermediate files (gitignored)
```

## Compliance Note

credentials.json and token.json must never be committed. Store all secrets in .env.
Regenerate OAuth credentials immediately if either file is accidentally exposed.
