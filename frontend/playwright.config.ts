import { defineConfig, devices } from "@playwright/test";

const localChannel = process.env.E2E_BROWSER_CHANNEL ?? (process.env.CI ? undefined : "msedge");
const browser = localChannel ? { channel: localChannel } : {};

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], ...browser } },
    { name: "mobile-360", use: { ...devices["Desktop Chrome"], ...browser, viewport: { width: 360, height: 740 } } },
  ],
});
