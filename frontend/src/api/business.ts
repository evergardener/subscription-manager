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
  service_dates?: {
    trial_end_date: string | null;
    service_expiry_date: string | null;
    cancellation_deadline: string | null;
    contract_end_date: string | null;
  };
};

export type SubscriptionPage = { items: Subscription[]; page: number; page_size: number; total: number };
export type EventItem = { id: string; subscription_id: string; event_type: string; event_date: string; amount: string | null; currency: string | null; status: string };
export type AnalyticsBreakdown = { label: string; currency: string; expected: string; actual: string };
export type Analytics = { expected: Record<string, string>; actual: Record<string, string>; by_vendor: AnalyticsBreakdown[]; by_category: AnalyticsBreakdown[] };
export type Payment = { id: string; amount: string; currency: string; paid_at: string; tax_amount: string; source: string; notes: string | null };
export type ReminderRule = { id: string; event_type: string; offset_days: number; channel: string; enabled: boolean };
export type AuditLog = { id: string; action: string; entity_type: string; entity_id: string; actor_type: string; actor_id: string; occurred_at: string };

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

export function listSubscriptions(query = "", signal?: AbortSignal, includeArchived = false) {
  const params = new URLSearchParams({ page_size: "100" });
  if (query.trim()) params.set("query", query.trim());
  if (includeArchived) params.set("include_archived", "true");
  return apiRequest<SubscriptionPage>(`/api/v1/subscriptions?${params}`, { signal });
}

export function createSubscription(payload: SubscriptionCreate) {
  return apiRequest<Subscription>("/api/v1/subscriptions", {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify(payload),
  });
}

export function getSubscription(id: string, signal?: AbortSignal) {
  return apiRequest<Subscription>(`/api/v1/subscriptions/${id}`, { signal });
}

export function updateSubscription(item: Subscription, changes: { amount: string; next_billing_date: string; auto_renew: boolean }) {
  if (!item.billing_plan) throw new Error("订阅没有当前计费计划");
  return apiRequest<Subscription>(`/api/v1/subscriptions/${item.id}`, {
    method: "PATCH",
    body: JSON.stringify({
      expected_version: item.version,
      billing_plan: { ...item.billing_plan, amount: changes.amount, next_billing_date: changes.next_billing_date },
    }),
  });
}

export function setSubscriptionArchived(id: string, archived: boolean) {
  return apiRequest<Subscription>(`/api/v1/subscriptions/${id}/${archived ? "archive" : "restore"}`, { method: "POST" });
}

export function listPayments(id: string, signal?: AbortSignal) {
  return apiRequest<Payment[]>(`/api/v1/subscriptions/${id}/payments`, { signal });
}

export function recordPayment(id: string, payload: { amount: string; currency: string; paid_at: string; notes?: string }) {
  return apiRequest<Payment>(`/api/v1/subscriptions/${id}/payments`, {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({ ...payload, tax_amount: "0", source: "manual", advance_schedule: false }),
  });
}

export function getReminderRules(id: string, signal?: AbortSignal) {
  return apiRequest<ReminderRule[]>(`/api/v1/subscriptions/${id}/reminder-rules`, { signal });
}

export function saveReminderRules(id: string, offsets: number[]) {
  return apiRequest<ReminderRule[]>(`/api/v1/subscriptions/${id}/reminder-rules`, {
    method: "PUT",
    body: JSON.stringify(offsets.map((offset_days) => ({ event_type: "billing", offset_days, channel: "ntfy", enabled: true }))),
  });
}

export function listAuditLogs(signal?: AbortSignal) {
  return apiRequest<{ items: AuditLog[] }>("/api/v1/audit-logs?page_size=100", { signal });
}

export function upcomingEvents(days = 30, signal?: AbortSignal) {
  return apiRequest<EventItem[]>(`/api/v1/events/upcoming?days=${days}`, { signal });
}

export function analyticsSummary(signal?: AbortSignal) {
  return apiRequest<Analytics>("/api/v1/analytics/summary", { signal });
}
