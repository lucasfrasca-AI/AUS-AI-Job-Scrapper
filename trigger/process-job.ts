import { task } from "@trigger.dev/sdk";
import { execSync } from "child_process";

export type RawJob = Record<string, unknown>;

export const processJob = task({
  id: "process-job",
  retry: {
    maxAttempts: 3,
    minTimeoutInMs: 5000,
    factor: 2,
  },
  run: async (payload: { job: RawJob }) => {
    const jobJson = JSON.stringify(payload.job);

    // Step 1: Categorize — keyword/rule logic, adds job_type, level, remote_flag, key_requirements, date_added
    let categorized: RawJob;
    try {
      const catOutput = execSync("python tools/categorize_job.py", {
        input: jobJson,
        encoding: "utf8",
        cwd: process.cwd(),
      });
      categorized = JSON.parse(catOutput);
    } catch (err) {
      console.error(`categorize_job.py failed for job: ${payload.job.apply_url}`, err);
      throw err;
    }

    // Step 2: Append to Google Sheet (skips silently if duplicate)
    let result: { status: "added" | "skipped" };
    try {
      const appendOutput = execSync("python tools/sheets_append.py", {
        input: JSON.stringify(categorized),
        encoding: "utf8",
        cwd: process.cwd(),
      });
      result = JSON.parse(appendOutput);
    } catch (err) {
      console.error(`sheets_append.py failed for job: ${payload.job.apply_url}`, err);
      throw err;
    }

    console.log(
      `[${result.status.toUpperCase()}] ${payload.job.title} @ ${payload.job.company} (${payload.job.source})`
    );

    return result;
  },
});
