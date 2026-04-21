"""
Categorizes a raw job dict using keyword/rule logic. No LLM used.
Input: raw job dict as JSON on stdin
Output: enriched job dict as JSON to stdout

Enrichment adds: job_type, level, remote_flag, key_requirements, date_added
"""

import json
import re
import sys
from datetime import datetime, timezone


# --- Level detection ---

ENTRY_KEYWORDS = [
    "junior", "graduate", "entry", "entry-level", "associate",
    "intern", "internship", "trainee", "grad",
]
SENIOR_KEYWORDS = [
    "senior", "lead", "principal", "staff", "manager", "head of",
    "director", "architect", "ciso", "vp", "vice president", "chief",
]


def detect_level(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    for kw in SENIOR_KEYWORDS:
        if kw in text:
            return "Senior"
    for kw in ENTRY_KEYWORDS:
        if kw in text:
            return "Entry/Junior"
    return "Mid-level"


# --- Remote flag detection ---

def detect_remote_flag(location: str, description: str) -> str:
    text = (location + " " + description).lower()
    if "hybrid" in text:
        return "Hybrid"
    if "remote" in text or "work from home" in text or "wfh" in text:
        return "Remote"
    return "On-site"


# --- Cybersecurity job type mapping ---

CYBER_PATTERNS = [
    (re.compile(r"penetration test|pentest|pen test|ethical hack", re.I), "Penetration Tester"),
    (re.compile(r"soc analyst|soc engineer|security operations", re.I), "SOC Analyst"),
    (re.compile(r"red team", re.I), "Red Team"),
    (re.compile(r"blue team", re.I), "Blue Team"),
    (re.compile(r"incident response|dfir|digital forensic", re.I), "Incident Response"),
    (re.compile(r"vulnerability analyst|vuln management|vuln assess", re.I), "Vulnerability Analyst"),
    (re.compile(r"cloud security", re.I), "Cloud Security"),
    (re.compile(r"grc|governance|compliance|risk and compliance|risk management", re.I), "GRC / Compliance"),
    (re.compile(r"ciso|head of security|security manager|security director", re.I), "Security Manager / CISO"),
    (re.compile(r"security engineer", re.I), "Security Engineer"),
]


# --- AI job type mapping ---

AI_PATTERNS = [
    (re.compile(r"machine learning engineer|ml engineer", re.I), "ML Engineer"),
    (re.compile(r"genai|llm engineer|large language model", re.I), "GenAI / LLM"),
    (re.compile(r"computer vision", re.I), "Computer Vision"),
    (re.compile(r"nlp engineer|natural language processing", re.I), "NLP Engineer"),
    (re.compile(r"mlops|ai infra|ai platform|ml platform", re.I), "MLOps / AI Infra"),
    (re.compile(r"ai product manager|ai pm", re.I), "AI Product Manager"),
    (re.compile(r"prompt engineer", re.I), "Prompt Engineer"),
    (re.compile(r"data scientist", re.I), "Data Scientist"),
    (re.compile(r"ai engineer|artificial intelligence engineer", re.I), "AI Engineer"),
]


def detect_job_type(title: str, field: str) -> str:
    if field == "Cybersecurity":
        for pattern, label in CYBER_PATTERNS:
            if pattern.search(title):
                return label
        return "Other Cybersecurity"
    else:
        for pattern, label in AI_PATTERNS:
            if pattern.search(title):
                return label
        return "Other AI"


# --- Key requirements extraction ---

REQUIREMENT_PATTERNS = [
    re.compile(r"\d+\+?\s*years?\s+(?:of\s+)?(?:experience|exp)", re.I),
    re.compile(r"\b(?:CISSP|CISM|CEH|OSCP|OSWE|OSEP|CCNA|CCNP|CompTIA|CySA\+|CASP\+|Security\+|AWS|GCP|Azure|CISA|CRISC|CDPSE)\b"),
    re.compile(r"\b(?:NV1|NV2|baseline clearance|AGSVA|security clearance|PV clearance)\b", re.I),
    re.compile(r"\b(?:Python|Java|Go|Golang|Rust|TypeScript|JavaScript|C\+\+|C#|Kotlin|Scala)\b"),
    re.compile(r"\b(?:TensorFlow|PyTorch|Keras|scikit-learn|Kubernetes|Docker|Terraform|Ansible|Splunk|Elastic|CrowdStrike|Palo Alto)\b"),
]


def extract_key_requirements(description: str) -> str:
    found: list[str] = []
    seen: set[str] = set()

    for pattern in REQUIREMENT_PATTERNS:
        matches = pattern.findall(description)
        for match in matches:
            normalized = match.strip()
            if normalized.lower() not in seen:
                seen.add(normalized.lower())
                found.append(normalized)

    result = ", ".join(found)
    if len(result) > 200:
        result = result[:197] + "..."
    return result if result else "See listing"


# --- Main categorization ---

def categorize(job: dict) -> dict:
    title = job.get("title", "")
    description = job.get("description", "")
    location = job.get("location", "")
    field = job.get("field", "")

    job["level"] = detect_level(title, description)
    job["remote_flag"] = detect_remote_flag(location, description)
    job["job_type"] = detect_job_type(title, field)
    job["key_requirements"] = extract_key_requirements(description)
    job["date_added"] = datetime.now(timezone.utc).isoformat()

    return job


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

    enriched = categorize(job)
    print(json.dumps(enriched))


if __name__ == "__main__":
    main()
