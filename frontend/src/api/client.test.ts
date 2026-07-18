import { afterEach, expect, test, vi } from "vitest";

import { apiRequest } from "./client";

afterEach(() => {
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  vi.restoreAllMocks();
});

test("blocks writes before fetch while offline", async () => {
  Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
  const fetchMock = vi.spyOn(globalThis, "fetch");
  await expect(apiRequest("/api/v1/subscriptions", { method: "POST", body: "{}" })).rejects.toMatchObject({
    status: 503,
    body: { code: "offline_write_blocked" },
  });
  expect(fetchMock).not.toHaveBeenCalled();
});
