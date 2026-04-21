"""
Scraper for Indeed AU jobs via HTML parsing.
CLI: python tools/scrape_indeed.py --query "cybersecurity" --field "Cybersecurity" [--since ISO_TIMESTAMP]
Output: JSON list to stdout
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://au.indeed.com/jobs"
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
        desc_el = soup.find("div", {"id": "jobDescriptionText"}) or soup.find(
            "div", class_="jobsearch-jobDescriptionText"
        )
        return desc_el.get_text(separator=" ", strip=True)[:3000] if desc_el else ""
    except Exception:
        return ""


def scrape_indeed(query: str, field: str, since: datetime | None) -> list[dict]:
    jobs = []
    seen_jks: set[str] = set()

    for start in range(0, MAX_PAGES * 10, 10):
        params = {
            "q": query,
            "l": "Australia (Remote)",
            "start": start,
        }

        try:
            response = requests.get(
                BASE_URL, params=params, headers=get_headers(), timeout=15
            )
            if response.status_code != 200:
                print(
                    f"WARNING: Indeed returned {response.status_code} for '{query}'",
                    file=sys.stderr,
                )
                break
            soup = BeautifulSoup(response.text, "lxml")
        except Exception as e:
            print(f"WARNING: Indeed request failed for '{query}': {e}", file=sys.stderr)
            break

        cards = soup.find_all("div", attrs={"data-jk": True})
        if not cards:
            cards = soup.find_all("li", class_="css-5lfssm")
        if not cards:
            break

        for card in cards:
            jk = card.get("data-jk", "")
            if not jk or jk in seen_jks:
                continue
            seen_jks.add(jk)

            apply_url = f"https://au.indeed.com/viewjob?jk={jk}"

            title_el = card.find("h2", class_=lambda c: c and "jobTitle" in c)
            title = title_el.get_text(strip=True) if title_el else ""

            company_el = card.find("span", {"data-testid": "company-name"}) or card.find(
                "a", {"data-tn-element": "companyName"}
            )
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.find("div", {"data-testid": "text-location"}) or card.find(
                "div", class_=lambda c: c and "companyLocation" in c
            )
            location = location_el.get_text(strip=True) if location_el else ""

            salary_el = card.find("div", {"data-testid": "attribute_snippet_testid"})
            salary = salary_el.get_text(strip=True) if salary_el else "Not listed"

            date_el = card.find("span", {"data-testid": "myJobsStateDate"}) or card.find(
                "span", class_=lambda c: c and "date" in (c or "").lower()
            )
            date_posted = date_el.get_text(strip=True) if date_el else ""

            jobs.append({
                "title": title,
                "company": company,
                "source": "Indeed",
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

    jobs = scrape_indeed(args.query, args.field, since_dt)
    print(json.dumps(jobs))


if __name__ == "__main__":
    main()
