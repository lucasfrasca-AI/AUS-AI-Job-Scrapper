import { task } from "@trigger.dev/sdk";
import { checkJobs } from "./check-jobs.js";

/**
 * Manual trigger task — fire from the Trigger.dev dashboard to run a full scrape immediately.
 * Useful for testing or on-demand refresh outside the weekly schedule.
 */
export const triggerNow = task({
  id: "trigger-now",
  run: async () => {
    console.log("Manual trigger initiated — firing check-jobs...");
    await checkJobs.trigger({});
    return { triggered: true };
  },
});
