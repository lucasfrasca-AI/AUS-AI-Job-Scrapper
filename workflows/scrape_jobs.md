# Workflow: Scrape Jobs

## Objective
Scrape Australian Cybersecurity and AI job listings from LinkedIn, SEEK, Indeed, and Jora. Filter for Sydney/Remote/Hybrid positions, deduplicate across sources, and pass results to `process-job` for categorization and sheet writing.

## Trigger
- **Scheduled:** Every Monday at 9am UTC via `check-jobs` Trigger.dev task
- **Manual:** Trigger `trigger-now` from the Trigger.dev dashboard, or run locally:
  ```
  python tools/run_all_scrapers.py
  ```

---

## Inputs
- `--since ISO_TIMESTAMP` (optional): only return jobs posted after this date. Stored in `.tmp/last_run.json` after each successful run.
- On first run (no `.tmp/last_run.json`): scrapes all available history.

## Outputs
- JSON list of raw job dicts written to stdout by `run_all_scrapers.py`
- Each job is dispatched to `process-job` by `check-jobs.ts`

---

## Search Keywords

### Cybersecurity (12 queries)
`cybersecurity`, `penetration tester`, `SOC analyst`, `security engineer`, `GRC`, `cloud security`, `CISO`, `information security`, `red team`, `blue team`, `incident response`, `vulnerability analyst`

### AI (11 queries)
`AI engineer`, `machine learning engineer`, `data scientist`, `prompt engineer`, `LLM engineer`, `MLOps`, `GenAI`, `artificial intelligence`, `AI product manager`, `computer vision engineer`, `NLP engineer`

---

## Site-Specific Notes

### SEEK
- **Endpoint:** `https://chalice-search-api.cloud.seek.com.au/search` (public JSON API)
- Response includes structured data — no HTML parsing needed
- `workType=remote` filter applied server-side
- Apply URL format: `https://www.seek.com.au/job/{id}`
- Pagination via `page` parameter (22 results per page)
- Generally reliable; rarely blocks

### Indeed AU
- **URL:** `https://au.indeed.com/jobs?q={query}&l=Australia+(Remote)`
- HTML scraping with BeautifulSoup4
- Job key (`data-jk`) used to build apply URL: `https://au.indeed.com/viewjob?jk={jk}`
- Description fetched from detail page (separate request, 2–3s delay)
- Scraped up to 5 pages (50 results) per query
- **Rate limit risk:** If getting CAPTCHAs or empty results, reduce MAX_PAGES in `scrape_indeed.py`

### Jora AU
- **URL:** `https://au.jora.com/j?q={query}&l=Australia&rbl=Remote`
- HTML scraping with BeautifulSoup4
- Description fetched from detail page
- Up to 5 pages per query
- **Known quirk:** Jora HTML structure changes periodically. If cards return empty, inspect the live page and update CSS selectors in `scrape_jora.py`

### LinkedIn
- **URL:** `https://www.linkedin.com/jobs/search/?keywords={query}&location=Australia&f_WT=2`
- `f_WT=2` = remote filter
- Rotates user agents to reduce blocking
- **Blocking behaviour:** If LinkedIn returns 429 or redirects to `/login` or `/authwall`, the scraper logs a warning to stderr and returns `[]` — it does NOT crash the run
- Up to 5 pages (125 results) per query
- LinkedIn blocking is common; treat LinkedIn results as a bonus, not a guarantee
- **If consistently blocked:** consider adding a `LINKEDIN_SESSION_COOKIE` env var and setting it in the `Cookie` header

---

## Location Filter

Jobs are kept only if their `location` field contains at least one of:
`sydney`, `remote`, `hybrid`, `australia`

Jobs specifying only Melbourne, Brisbane, Perth, Adelaide etc. with no remote component are excluded.

Implementation: `run_all_scrapers.py → should_keep(location)`

---

## Deduplication

1. **Within a run:** `run_all_scrapers.py` generates `job_id = MD5(source:title:company)[:12]` and deduplicates by `job_id + field` key. A job matching both Cybersecurity and AI queries is emitted twice with different `field` values.
2. **Across runs:** `sheets_append.py` checks column 11 (Apply URL) before writing — skips silently if already present.
3. **Trigger.dev level:** `processJob.trigger()` is called with `idempotencyKey: job-{source}-{jobId}` — Trigger.dev will not dispatch a duplicate run.

---

## Manual Re-Run Instructions

### Full re-scrape (ignore since date):
```bash
# Delete the last run timestamp
rm .tmp/last_run.json

# Run locally
python tools/run_all_scrapers.py

# Or trigger from Trigger.dev dashboard via trigger-now task
```

### Incremental re-run:
```bash
python tools/run_all_scrapers.py --since "2026-01-01T00:00:00+00:00"
```

### Test a single scraper:
```bash
python tools/scrape_seek.py --query "cybersecurity" --field "Cybersecurity"
python tools/scrape_linkedin.py --query "AI engineer" --field "AI"
```

---

## Error Handling

| Error | Behaviour |
|---|---|
| LinkedIn 429 / login redirect | Log warning to stderr, return `[]`, continue |
| Scraper subprocess fails | Log warning, continue with other scrapers |
| Scraper returns invalid JSON | Log warning, treat as empty result |
| Scraper times out (>120s) | Log warning, treat as empty result |
| All scrapers fail | `run_all_scrapers.py` returns `[]`; `check-jobs` dispatches 0 jobs |

---

## Lessons Learned
- SEEK is the most reliable source — prioritize fixing SEEK issues first
- LinkedIn blocks are expected; the system is designed to tolerate them
- Always check stderr output for WARNING lines when debugging empty results
- `.tmp/last_run.json` must exist for incremental runs; delete it to force a full scrape
