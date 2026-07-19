INSERT INTO subscriptions (id, name, vendor, status)
SELECT
    md5('subscription-' || value)::uuid,
    'Performance Subscription ' || lpad(value::text, 5, '0'),
    'Vendor ' || (value % 100),
    'active'::subscription_status
FROM generate_series(1, 10000) AS value;

INSERT INTO billing_plans (
    id, subscription_id, amount, currency, interval_unit, interval_count,
    anchor_date, next_billing_date, auto_renew, billing_mode
)
SELECT
    md5('plan-' || value)::uuid,
    md5('subscription-' || value)::uuid,
    (10 + (value % 200))::numeric(18, 6),
    (ARRAY['CNY', 'USD', 'EUR', 'JPY'])[(value % 4) + 1],
    'month', 1, current_date, current_date + (value % 30), true, 'fixed'
FROM generate_series(1, 10000) AS value;

INSERT INTO billing_events (
    id, subscription_id, billing_plan_id, event_type, event_date, amount, currency, status
)
SELECT
    md5('event-' || value)::uuid,
    md5('subscription-' || value)::uuid,
    md5('plan-' || value)::uuid,
    'billing'::event_type,
    current_date + (value % 30),
    (10 + (value % 200))::numeric(18, 6),
    (ARRAY['CNY', 'USD', 'EUR', 'JPY'])[(value % 4) + 1],
    'planned'::event_status
FROM generate_series(1, 10000) AS value;

ANALYZE subscriptions;
ANALYZE billing_plans;
ANALYZE billing_events;
