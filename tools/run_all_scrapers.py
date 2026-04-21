"""
Orchestrates all four scrapers, deduplicates across sources, and applies location filtering.
CLI: python tools/run_all_scrapers.py [--since ISO_TIMESTAMP]
Output: deduplicated JSON list to stdout

This is the entry point called by Trigger.dev's check-jobs task.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

CYBERSECURITY_QUERIES = [
    ("cybersecurity", "Cybersecurity"),
    ("penetration tester", "Cybersecurity"),
    ("SOC analyst", "Cybersecurity"),
    ("security engineer", "Cybersecurity"),
    ("GRC", "Cybersecurity"),
    ("cloud security", "Cybersecurity"),
    ("CISO", "Cybersecurity"),
    ("information security", "Cybersecurity"),
    ("red team", "Cybersecurity"),
    ("blue team", "Cybersecurity"),
    ("incident response", "Cybersecurity"),
    ("vulnerability analyst", "Cybersecurity"),
]

AI_QUERIES = [
    ("AI engineer", "AI"),
    ("machine learning engineer", "AI"),
    ("data scientist", "AI"),
    ("prompt engineer", "AI"),
    ("LLM engineer", "AI"),
    ("MLOps", "AI"),
    ("GenAI", "AI"),
    ("artificial intelligence", "AI"),
    ("AI product manager", "AI"),
    ("computer vision engineer", "AI"),
    ("NLP engineer", "AI"),
]

SCRAPERS = ["seek", "indeed", "jora", "linkedin"]

KEEP_LOCATIONS = ["sydney", "remote", "hybrid", "australia"]

TOOLS_DIR = Path(__file__).parent


def make_job_id(source: str, title: str, company: str) -> str:
    raw = f"{source}:{title.lower().strip()}:{company.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def should_keep(location: str) -> bool:
    loc_lower = location.lower()
    return any(kw in loc_lower for kw in KEEP_LOCATIONS)


def run_scraper(site: str, query: str, field: str, since: str | None) -> list[dict]:
    script = TOOLS_DIR / f"scrape_{site}.py"
    cmd = [sys.executable, str(script), "--query", query, "--field", field]
    if since:
        cmd += ["--since", since]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(
                f"WARNING: scrape_{site}.py exited with code {result.returncode} "
                f"for query '{query}': {result.stderr.strip()}",
                file=sys.stderr,
            )
            return []

        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)

        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        print(
            f"WARNING: scrape_{site}.py timed out for query '{query}'", file=sys.stderr
        )
        return []
    except json.JSONDecodeError as e:
        print(
            f"WARNING: scrape_{site}.py returned invalid JSON for query '{query}': {e}",
            file=sys.stderr,
        )
        return []
    except Exception as e:
        print(
            f"WARNING: scrape_{site}.py failed for query '{query}': {e}", file=sys.stderr
        )
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default=None, help="ISO timestamp for incremental scraping")
    args = parser.parse_args()

    all_queries = CYBERSECURITY_QUERIES + AI_QUERIES

    # job_id -> list of jobs (one per field if job matches both)
    combined: dict[str, dict] = {}
    # Track jobs that appear under both fields for duplication
    dual_field_tracker: dict[str, set[str]] = {}

    for query, field in all_queries:
        for site in SCRAPERS:
            print(
                f"Scraping {site} for '{query}' ({field})...", file=sys.stderr
            )
            jobs = run_scraper(site, query, field, args.since)

            for job in jobs:
                title = job.get("title", "")
                company = job.get("company", "")
                source = job.get("source", site.title())
                location = job.get("location", "")

                # Location filter
                if not should_keep(location):
                    continue

                job_id = make_job_id(source, title, company)
                job["job_id"] = job_id

                key = f"{job_id}:{field}"
                if key not in combined:
                    combined[key] = dict(job)
                    combined[key]["field"] = field

    result = list(combined.values())
    print(f"Total jobs after dedup + location filter: {len(result)}", file=sys.stderr)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
