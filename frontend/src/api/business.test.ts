import { beforeEach, expect, test, vi } from "vitest";

import { analyticsSummary, recordPayment, type Subscription, updateServiceDates, updateSubscription } from "./business";

function parseBody(init: RequestInit | undefined): Record<string, unknown> {
  const body = init?.body;
  expect(typeof body).toBe("string");
  return JSON.parse(body as string) as Record<string, unknown>;
}

beforeEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
});

test("sends the changed auto-renew value when updating a plan", async () => {
  let captured: RequestInit | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
    captured = init;
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });
  const item = {
    id: "subscription-1",
    name: "Example",
    vendor: null,
    status: "active",
    version: 3,
    archived_at: null,
    billing_plan: {
      id: "plan-1",
      amount: "12.00",
      currency: "USD",
      interval_unit: "month",
      interval_count: 1,
      anchor_date: "2026-07-01",
      next_billing_date: "2026-08-01",
      auto_renew: true,
      billing_mode: "fixed",
    },
  } satisfies Subscription;

  await updateSubscription(item, { amount: "12.00", next_billing_date: "2026-08-01", auto_renew: false });

  expect(parseBody(captured)).toMatchObject({ billing_plan: { auto_renew: false } });
});

test("preserves event binding and explicit schedule advancement for payments", async () => {
  let captured: RequestInit | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
    captured = init;
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });

  await recordPayment("subscription-1", {
    amount: "12.00",
    currency: "USD",
    paid_at: "2026-07-18T00:00:00Z",
    billing_event_id: "event-1",
    advance_schedule: true,
  });

  expect(parseBody(captured)).toMatchObject({ billing_event_id: "event-1", advance_schedule: true });
});

test("sends start_date alongside service dates when editing subscription dates", async () => {
  let captured: RequestInit | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
    captured = init;
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });
  const item = {
    id: "subscription-1",
    name: "Example",
    vendor: null,
    status: "active",
    version: 2,
    archived_at: null,
    start_date: "2026-01-10",
  } satisfies Subscription;

  await updateServiceDates(item, {
    trial_end_date: null,
    service_expiry_date: "2027-01-10",
    cancellation_deadline: null,
    contract_end_date: null,
  }, "2026-01-15");

  expect(parseBody(captured)).toMatchObject({
    expected_version: 2,
    start_date: "2026-01-15",
    service_dates: { service_expiry_date: "2027-01-10" },
  });
});

test("omits start_date when it is not being edited", async () => {
  let captured: RequestInit | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
    captured = init;
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });
  const item = {
    id: "subscription-1",
    name: "Example",
    vendor: null,
    status: "active",
    version: 2,
    archived_at: null,
  } satisfies Subscription;

  await updateServiceDates(item, {
    trial_end_date: null,
    service_expiry_date: null,
    cancellation_deadline: null,
    contract_end_date: null,
  });

  expect(parseBody(captured)).not.toHaveProperty("start_date");
});

test("passes vendor and category filters to the analytics summary", async () => {
  let capturedUrl: string | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    capturedUrl = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });

  await analyticsSummary({ vendor: "OpenAI", categoryId: "category-1" });

  expect(capturedUrl).toContain("vendor=OpenAI");
  expect(capturedUrl).toContain("category_id=category-1");
});
