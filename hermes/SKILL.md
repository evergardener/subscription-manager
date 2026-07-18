---
name: hermes
description: Query and safely manage subscriptions through the Subscription Manager REST API. Use when users ask about subscriptions, renewal dates, upcoming billing events, spending analytics, creating or editing subscriptions, recording payments, or archiving subscriptions through the self-hosted service.
---

# Hermes Subscription Manager

Use only the REST API through `scripts/call_tool.py`. Never access PostgreSQL or infer stored dates, amounts, event IDs, or versions.

## Configure

Require these environment variables:

- `HERMES_SUBSCRIPTION_API_URL`: service origin, for example `http://localhost:8000`.
- `HERMES_SUBSCRIPTION_API_TOKEN`: dedicated token with `actor_type=hermes` and only the scopes needed. Never print or persist it.

Read [references/api.md](references/api.md) when constructing tool arguments or interpreting a response. Read [references/errors.md](references/errors.md) after any non-2xx response.
Read [examples/conversations.md](examples/conversations.md) when handling creation, payment, or cancellation language.

## Execute

1. Resolve names with `subscription_search`; do not guess an ID when multiple records match.
2. Fetch `subscription_get` before an update to obtain the current version and plan.
3. Validate every amount, ISO currency, date, interval, and event ID. Ask for missing or ambiguous values.
4. For a write, state the exact proposed change and wait for explicit user confirmation when the operation creates a subscription, changes price/period/dates, records payment, changes cancellation state, or archives data.
5. After confirmation, call the script with `--confirm`. Do not reuse confirmation after arguments change.
6. Report the API result and request ID. Never claim an external subscription was cancelled; this service only records lifecycle state.

Example invocation:

```powershell
python hermes/scripts/call_tool.py upcoming_events --arguments '{"days":30}'
```

Critical write after explicit confirmation:

```powershell
python hermes/scripts/call_tool.py subscription_archive --arguments '{"subscription_id":"..."}' --confirm
```

## Payment guardrail

Before `payment_record`, repeat amount, currency, paid time, billing event, and whether the schedule advances. Set `advance_schedule=true` only with the current planned billing event returned by the API. Use false for historical entries. Never choose an event when more than one candidate is plausible.

## Tool contract

Use [tools.json](tools.json) as the machine-readable function schema. The script rejects undeclared fields, missing confirmation, missing credentials, and unsupported tools before sending a request.
