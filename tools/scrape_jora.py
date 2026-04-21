"""
Scraper for Jora AU jobs via HTML parsing.
CLI: python tools/scrape_jora.py --query "cybersecurity" --field "Cybersecurity" [--since ISO_TIMESTAMP]
Output: JSON list to stdout
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://au.jora.com/j"
JORA_ORIGIN = "https://au.jora.com"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

MAX_PAGES = 5


def get_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-AU,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def fetch_description(job_url: str) -> str:
    try:
        time.sleep(random.uniform(2, 3))
        response = requests.get(job_url, headers=get_headers(), timeout=15)
        if response.status_code != 200:
            return ""
        soup = BeautifulSoup(response.text, "lxml")
        desc_el = (
            soup.find("div", class_="job-description")
            or soup.find("div", {"id": "job-description"})
            or soup.find("section", class_="description")
        )
        return desc_el.get_text(separator=" ", strip=True)[:3000] if desc_el else ""
    except Exception:
        return ""


def scrape_jora(query: str, field: str, since: datetime | None) -> list[dict]:
    jobs = []
    seen_urls: set[str] = set()

    for page in range(1, MAX_PAGES + 1):
        params = {
            "q": query,
            "l": "Australia",
            "rbl": "Remote",
            "p": page,
        }

        try:
            response = requests.get(
                BASE_URL, params=params, headers=get_headers(), timeout=15
            )
            if response.status_code != 200:
                print(
                    f"WARNING: Jora returned {response.status_code} for '{query}'",
                    file=sys.stderr,
                )
                break
            soup = BeautifulSoup(response.text, "lxml")
        except Exception as e:
            print(f"WARNING: Jora request failed for '{query}': {e}", file=sys.stderr)
            break

        cards = soup.find_all("article", class_=lambda c: c and "result" in (c or ""))
        if not cards:
            cards = soup.find_all("div", class_=lambda c: c and "job-card" in (c or ""))
        if not cards:
            break

        for card in cards:
            link_el = card.find("a", href=True)
            if not link_el:
                continue

            href = link_el.get("href", "")
            apply_url = urljoin(JORA_ORIGIN, href) if href.startswith("/") else href

            if apply_url in seen_urls:
                continue
            seen_urls.add(apply_url)

            title_el = card.find("h2") or card.find("h3") or link_el
            title = title_el.get_text(strip=True) if title_el else ""

            company_el = card.find(class_=lambda c: c and "company" in (c or "").lower())
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.find(class_=lambda c: c and "location" in (c or "").lower())
            location = location_el.get_text(strip=True) if location_el else ""

            salary_el = card.find(class_=lambda c: c and "salary" in (c or "").lower())
            salary = salary_el.get_text(strip=True) if salary_el else "Not listed"

            date_el = card.find("time") or card.find(
                class_=lambda c: c and "date" in (c or "").lower()
            )
            date_posted = date_el.get_text(strip=True) if date_el else ""

            jobs.append({
                "title": title,
                "company": company,
                "source": "Jora",
                "field": field,
                "location": location,
                "salary": salary,
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

    jobs = scrape_jora(args.query, args.field, since_dt)
    print(json.dumps(jobs))


if __name__ == "__main__":
    main()
