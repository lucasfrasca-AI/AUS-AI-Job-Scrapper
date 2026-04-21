import { schedules } from "@trigger.dev/sdk";
import { execSync } from "child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";
import { processJob, type RawJob } from "./process-job.js";

const LAST_RUN_PATH = join(process.cwd(), ".tmp", "last_run.json");

export const checkJobs = schedules.task({
  id: "check-jobs",
  cron: "0 9 * * 1", // Every Monday at 9am UTC

  run: async () => {
    // Read last run timestamp for incremental scraping
    let since = "";
    if (existsSync(LAST_RUN_PATH)) {
      try {
        const data = JSON.parse(readFileSync(LAST_RUN_PATH, "utf8"));
        since = data.lastRun ?? "";
      } catch {
        console.warn("Could not read last_run.json — performing full scrape");
      }
    }

    if (since) {
      console.log(`Incremental scrape since: ${since}`);
    } else {
      console.log("No prior run found — performing full scrape");
    }

    // Run all four scrapers via Python orchestrator
    const scraperArgs = since ? `--since "${since}"` : "";
    let jobs: RawJob[];
    try {
      const output = execSync(
        `python tools/run_all_scrapers.py ${scraperArgs}`,
        {
          encoding: "utf8",
          cwd: process.cwd(),
          maxBuffer: 50 * 1024 * 1024, // 50MB buffer for large result sets
        }
      );
      jobs = JSON.parse(output);
    } catch (err) {
      console.error("run_all_scrapers.py failed:", err);
      throw err;
    }

    console.log(`Found ${jobs.length} jobs after dedup and location filter`);

    // Trigger process-job for each job with idempotency key
    let dispatched = 0;
    for (const job of jobs) {
      const source = String(job.source ?? "unknown");
      const jobId = String(job.job_id ?? "");
      const idempotencyKey = `job-${source}-${jobId}`;

      await processJob.trigger(
        { job },
        { idempotencyKey }
      );
      dispatched++;
    }

    // Persist last run timestamp
    mkdirSync(join(process.cwd(), ".tmp"), { recursive: true });
    writeFileSync(
      LAST_RUN_PATH,
      JSON.stringify({ lastRun: new Date().toISOString() })
    );

    console.log(`Dispatched ${dispatched} jobs for processing`);
    return { dispatched };
  },
});
