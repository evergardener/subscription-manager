import { apiRequest } from "./client";

export type BillingPlan = {
  id: string;
  amount: string;
  currency: string;
  interval_unit: "day" | "week" | "month" | "year";
  interval_count: number;
  anchor_date: string;
  next_billing_date: string | null;
  auto_renew: boolean;
  billing_mode: string;
};

export type Subscription = {
  id: string;
  name: string;
  vendor: string | null;
  status: "trial" | "active" | "paused" | "pending_cancel" | "cancelled" | "expired";
  version: number;
  archived_at: string | null;
  billing_plan?: BillingPlan;
};

export type SubscriptionPage = { items: Subscription[]; page: number; page_size: number; total: number };
export type EventItem = { id: string; subscription_id: string; event_type: string; event_date: string; amount: string | null; currency: string | null; status: string };
export type Analytics = { expected: Record<string, string>; actual: Record<string, string> };

export type SubscriptionCreate = {
  name: string;
  vendor?: string;
  status: "trial" | "active";
  billing_plan: {
    amount: string;
    currency: string;
    interval_unit: "day" | "week" | "month" | "year";
    interval_count: number;
    anchor_date: string;
    next_billing_date: string;
    auto_renew: boolean;
    billing_mode: "fixed";
  };
};

export function listSubscriptions(query = "", signal?: AbortSignal) {
  const params = new URLSearchParams({ page_size: "100" });
  if (query.trim()) params.set("query", query.trim());
  return apiRequest<SubscriptionPage>(`/api/v1/subscriptions?${params}`, { signal });
}

export function createSubscription(payload: SubscriptionCreate) {
  return apiRequest<Subscription>("/api/v1/subscriptions", {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify(payload),
  });
}

export function upcomingEvents(days = 30, signal?: AbortSignal) {
  return apiRequest<EventItem[]>(`/api/v1/events/upcoming?days=${days}`, { signal });
}

export function analyticsSummary(signal?: AbortSignal) {
  return apiRequest<Analytics>("/api/v1/analytics/summary", { signal });
}
