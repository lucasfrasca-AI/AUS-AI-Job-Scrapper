"""
Scraper for SEEK AU jobs via public JSON API.
CLI: python tools/scrape_seek.py --query "cybersecurity" --field "Cybersecurity" [--since ISO_TIMESTAMP]
Output: JSON list to stdout
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://www.seek.com.au/api/jobsearch/v5/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def parse_since(since_str: str | None) -> datetime | None:
    if not since_str:
        return None
    try:
        dt = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def scrape_seek(query: str, field: str, since: datetime | None) -> list[dict]:
    jobs = []
    page = 1

    while True:
        params = {
            "siteKey": "AU-Main",
            "where": "All Australia",
            "keywords": query,
            "workType": "remote",
            "page": page,
            "pageSize": 20,
        }

        try:
            response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"WARNING: SEEK request failed for '{query}': {e}", file=sys.stderr)
            break

        results = data.get("data", [])
        if not results:
            break

        for job in results:
            listing_date_str = job.get("listingDate", "")
            if since and listing_date_str:
                try:
                    listing_date = datetime.fromisoformat(
                        listing_date_str.replace("Z", "+00:00")
                    )
                    if listing_date.tzinfo is None:
                        listing_date = listing_date.replace(tzinfo=timezone.utc)
                    if listing_date < since:
                        continue
                except ValueError:
                    pass

            job_id_raw = str(job.get("id", ""))
            apply_url = f"https://www.seek.com.au/job/{job_id_raw}" if job_id_raw else ""

            # v5 API uses companyName directly; advertiser.description is fallback
            company = job.get("companyName", "") or (
                job.get("advertiser", {}).get("description", "")
                if isinstance(job.get("advertiser"), dict) else ""
            )

            # v5 API uses salaryLabel; may be empty string
            salary_label = (job.get("salaryLabel") or "").strip()
            salary = salary_label if salary_label else "Not listed"

            # v5 API uses locations[0]['label'] for location string
            locations = job.get("locations") or []
            location = locations[0]["label"] if locations else ""

            # workArrangements contains Remote/Hybrid info — append to location hint
            work_arr = job.get("workArrangements") or {}
            arr_items = work_arr.get("data", [])
            if arr_items:
                arr_text = arr_items[0].get("label", {}).get("text", "")
                if arr_text and arr_text.lower() not in location.lower():
                    location = f"{location} ({arr_text})" if location else arr_text

            jobs.append({
                "title": job.get("title", ""),
                "company": company,
                "source": "SEEK",
                "field": field,
                "location": location,
                "salary": salary,
                "date_posted": listing_date_str,
                "apply_url": apply_url,
                "description": job.get("teaser", ""),
            })

        total = data.get("totalCount", 0)
        if page * 20 >= total:
            break

        page += 1
        time.sleep(2)

    return jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--field", required=True, choices=["Cybersecurity", "AI"])
    parser.add_argument("--since", default=None)
    args = parser.parse_args()

    since = parse_since(args.since)
    jobs = scrape_seek(args.query, args.field, since)
    print(json.dumps(jobs))


if __name__ == "__main__":
    main()
