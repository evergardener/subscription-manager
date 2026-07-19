# API mapping

All calls send `Authorization: Bearer <token>`. Create and payment calls also send a fresh `Idempotency-Key`.

| Tool | Method and path | Required scope | Confirmation |
| --- | --- | --- | --- |
| `subscription_search` | `GET /api/v1/subscriptions` | `subscriptions:read` | No |
| `subscription_get` | `GET /api/v1/subscriptions/{id}` | `subscriptions:read` | No |
| `subscription_create` | `POST /api/v1/subscriptions` | `subscriptions:write` | Yes |
| `subscription_update` | `PATCH /api/v1/subscriptions/{id}` | `subscriptions:write` | Yes |
| `subscription_transition` | `POST /api/v1/subscriptions/{id}/status-transitions` | `subscriptions:write` | Yes |
| `subscription_archive` | `POST /api/v1/subscriptions/{id}/archive` | `subscriptions:write` | Yes |
| `payment_record` | `POST /api/v1/subscriptions/{id}/payments` | `payments:write` | Yes |
| `upcoming_events` | `GET /api/v1/events/upcoming` | `subscriptions:read` | No |
| `analytics_summary` | `GET /api/v1/analytics/summary` | `analytics:read` | No |

`subscription_update` requires the latest `expected_version`. Send the complete replacement `billing_plan` when changing plan fields.
`subscription_transition` also requires the latest `expected_version`, a reason, and explicit confirmation. `pending_cancel` additionally requires `service_expiry_date`; `active` withdraws a planned cancellation. It only records local lifecycle state and never cancels the vendor account.

Dates use `YYYY-MM-DD`; timestamps use ISO 8601 with an offset. Money is a decimal string. Currency is a three-letter ISO 4217 code. `days` is 1–366.

The dedicated Hermes token should normally contain `subscriptions:read`, `subscriptions:write`, `payments:write`, and `analytics:read`. Add `audit:read` only when audit lookup is required. Never grant `tokens:manage` or `reminders:scan`.
