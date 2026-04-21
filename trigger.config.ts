import { defineConfig } from "@trigger.dev/sdk/v3";

export default defineConfig({
  project: process.env.TRIGGER_PROJECT_ID ?? "proj_placeholder",
  dirs: ["./trigger"],
});
