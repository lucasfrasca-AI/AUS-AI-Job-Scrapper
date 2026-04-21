"""
Scraper for LinkedIn AU jobs via public HTML search (no paid API).
CLI: python tools/scrape_linkedin.py --query "cybersecurity" --field "Cybersecurity" [--since ISO_TIMESTAMP]
Output: JSON list to stdout

Note: LinkedIn aggressively blocks scrapers. On 429 or login redirect, logs warning and returns [].
f_WT=2 filters for remote jobs only.
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://www.linkedin.com/jobs/search/"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
]

MAX_PAGES = 5
JOBS_PER_PAGE = 25


def get_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-AU,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.linkedin.com/",
    }


def is_blocked(response: requests.Response) -> bool:
    if response.status_code == 429:
        return True
    if "/login" in response.url or "/authwall" in response.url:
        return True
    if response.status_code in (401, 403):
        return True
    return False


def fetch_description(job_url: str) -> str:
    try:
        time.sleep(random.uniform(2, 3))
        response = requests.get(job_url, headers=get_headers(), timeout=15)
        if is_blocked(response):
            return ""
        soup = BeautifulSoup(response.text, "lxml")
        desc_el = soup.find(
            "div", class_=lambda c: c and "description__text" in (c or "")
        ) or soup.find("div", class_="show-more-less-html__markup")
        return desc_el.get_text(separator=" ", strip=True)[:3000] if desc_el else ""
    except Exception:
        return ""


def scrape_linkedin(query: str, field: str, since: datetime | None) -> list[dict]:
    jobs = []
    seen_urls: set[str] = set()

    for page in range(MAX_PAGES):
        params = {
            "keywords": query,
            "location": "Australia",
            "f_WT": "2",
            "start": page * JOBS_PER_PAGE,
        }

        try:
            response = requests.get(
                BASE_URL, params=params, headers=get_headers(), timeout=15
            )
        except Exception as e:
            print(
                f"WARNING: LinkedIn request failed for '{query}': {e}", file=sys.stderr
            )
            break

        if is_blocked(response):
            print(
                f"WARNING: LinkedIn blocked request for '{query}' "
                f"(status={response.status_code}, url={response.url}). Skipping.",
                file=sys.stderr,
            )
            break

        soup = BeautifulSoup(response.text, "lxml")

        cards = soup.find_all("li", class_=lambda c: c and "result-card" in (c or ""))
        if not cards:
            cards = soup.find_all("div", class_=lambda c: c and "base-card" in (c or ""))
        if not cards:
            break

        for card in cards:
            link_el = card.find("a", class_=lambda c: c and "base-card__full-link" in (c or ""))
            if not link_el:
                link_el = card.find("a", href=True)
            if not link_el:
                continue

            apply_url = link_el.get("href", "").split("?")[0]
            if not apply_url or apply_url in seen_urls:
                continue
            seen_urls.add(apply_url)

            title_el = card.find("h3", class_=lambda c: c and "base-search-card__title" in (c or ""))
            title = title_el.get_text(strip=True) if title_el else ""

            company_el = card.find("h4", class_=lambda c: c and "base-search-card__subtitle" in (c or ""))
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.find("span", class_=lambda c: c and "job-search-card__location" in (c or ""))
            location = location_el.get_text(strip=True) if location_el else ""

            date_el = card.find("time")
            date_posted = date_el.get("datetime", date_el.get_text(strip=True)) if date_el else ""

            jobs.append({
                "title": title,
                "company": company,
                "source": "LinkedIn",
                "field": field,
                "location": location,
                "salary": "Not listed",
                "date_posted": date_posted,
                "apply_url": apply_url,
                "description": "",
            })

        time.sleep(random.uniform(2, 3))

    return jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--field", required=True, choices=["Cybersecurity", "AI"])
    parser.add_argument("--since", default=None)
    args = parser.parse_args()

    since_dt = None
    if args.since:
        try:
            since_dt = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
        except ValueError:
            pass

    jobs = scrape_linkedin(args.query, args.field, since_dt)
    print(json.dumps(jobs))


if __name__ == "__main__":
    main()
