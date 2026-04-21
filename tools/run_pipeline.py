"""
Full pipeline: scrape → categorize → append to Google Sheet.
Runs all scrapers, processes each job, and writes to the sheet.

Usage: python tools/run_pipeline.py [--since ISO_TIMESTAMP]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).parent


def run_scraper_streaming(since: str | None) -> list[dict]:
    """Run run_all_scrapers.py and stream its progress to stderr in real-time."""
    cmd = [sys.executable, str(TOOLS_DIR / "run_all_scrapers.py")]
    if since:
        cmd += ["--since", since]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Stream stderr live so user sees progress
    import threading

    def stream_stderr():
        for line in proc.stderr:
            print(line, end="", file=sys.stderr, flush=True)

    t = threading.Thread(target=stream_stderr, daemon=True)
    t.start()

    stdout, _ = proc.communicate()
    t.join()

    if proc.returncode != 0:
        raise RuntimeError(f"run_all_scrapers.py exited with code {proc.returncode}")

    return json.loads(stdout)


def run_tool(script: str, input_data: str) -> str:
    """Run a single tool with JSON on stdin, return stdout."""
    result = subprocess.run(
        [sys.executable, str(TOOLS_DIR / script)],
        input=input_data,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"{script} exited {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default=None, help="ISO timestamp for incremental scraping")
    args = parser.parse_args()

    print("Step 1: Scraping all sources (progress below)...", flush=True)
    jobs = run_scraper_streaming(args.since)
    print(f"\nStep 2: Writing {len(jobs)} jobs to sheet...", flush=True)

    added = skipped = errors = 0
    for i, job in enumerate(jobs, 1):
        try:
            categorized_json = run_tool("categorize_job.py", json.dumps(job))
            result_json = run_tool("sheets_append.py", categorized_json)
            status = json.loads(result_json).get("status", "?")
            if status == "added":
                added += 1
                print(f"  [{i}/{len(jobs)}] ADDED: {job.get('title')} @ {job.get('company')}", flush=True)
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            print(f"  [{i}/{len(jobs)}] ERROR: {job.get('title')} @ {job.get('company')}: {e}", file=sys.stderr)

    print(f"\nDone. Added: {added} | Skipped (already in sheet): {skipped} | Errors: {errors}", flush=True)


if __name__ == "__main__":
    main()
