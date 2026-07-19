# Hermes-first interaction and notification architecture

Date: 2026-07-19  
Status: Accepted for implementation

## Goal

Subscription Manager is an independent subscription lifecycle service and Hermes is its primary interaction and notification client. Routine reading, editing, payment recording, cancellation, reminder configuration, and due-reminder consumption must work through scoped Hermes Tools. The Web UI remains a fallback console for bootstrap, credential rotation, recovery, and diagnostics.

## Responsibility boundary

Subscription Manager owns durable business state and timing correctness:

- subscriptions, plans, payments, lifecycle dates, and audit history;
- rolling generation of future billing and lifecycle events;
- reminder rules, due calculation, deduplication, leases, retry state, and outage catch-up;
- scoped REST APIs and optimistic locking.

Hermes owns user interaction and final notification delivery:

- natural-language intent resolution and explicit confirmation for important writes;
- periodic claiming of due reminder Outbox entries;
- notification through channels managed by Hermes;
- acknowledgement or failure reporting back to Subscription Manager.

Installing the Skill alone does not create a background schedule. The Hermes deployment must run one recurring job that claims due reminders. Subscription Manager remains correct if Hermes is temporarily offline: unacknowledged leases expire and eligible reminders can be claimed again within the configured grace and retry policy.

## Notification mode

The first production mode is configured with:

```dotenv
NOTIFICATION_MODE=external
```

Supported values in the first version:

- `external`: maintain events and the reminder Outbox; Hermes or another scoped consumer delivers notifications.
- `disabled`: maintain future events but do not create or deliver reminder Outbox entries.

The ntfy adapter and `NTFY_BASE_URL`/`NTFY_TOPIC` configuration are removed. A later `webhook` mode may add a standard signed JSON contract; provider-specific WxPusher or DingTalk adapters must not be simulated by a generic payload.

## Scheduler split

The Scheduler always runs event maintenance, regardless of notification mode:

1. roll every active billing plan forward to the 366-day horizon;
2. when mode is `external`, generate idempotent Reminder Delivery Outbox entries;
3. never contact a notification provider.

Only one Scheduler instance may run. Database uniqueness and leasing still protect against duplicate Outbox entries and concurrent consumers.

## External reminder protocol

Hermes uses a dedicated Token with `reminders:consume` in addition to its ordinary business scopes.

1. `POST /api/v1/reminders/claim` atomically leases due entries to the authenticated actor and returns subscription, event, schedule, amount, currency, and stable event-key data.
2. Hermes sends the user-facing notification through its own channel.
3. `POST /api/v1/reminders/deliveries/{id}/ack` records successful delivery.
4. `POST /api/v1/reminders/deliveries/{id}/fail` records a bounded error and schedules retry/backoff or marks the entry dead after the attempt limit.

Only the actor that owns a live lease may acknowledge or fail it. Expired leases are reclaimable. Invalid ownership or state returns a conflict.

## Hermes-first Tool baseline

Routine operation requires Tools for:

- subscription search, detail, create, update, archive, restore, and cancellation transitions;
- payment history and payment recording;
- upcoming events and analytics;
- reminder-rule reading and confirmed replacement;
- due-reminder claim, acknowledgement, and failure;
- recent audit lookup.

Token management, administrator bootstrap/password recovery, database restore, and deployment remain outside Hermes. Hermes never receives `tokens:manage` or host/database credentials.

## Reverse-proxy boundary

The production Compose stack contains only PostgreSQL (or an external database), migration, Backend, Scheduler, and Frontend. It does not configure Traefik, DNS, domains, or certificates.

Frontend is the only published service and defaults to the host loopback interface:

```dotenv
SERVICE_BIND_ADDRESS=127.0.0.1
SERVICE_PORT=8080
```

Users provide Nginx, Caddy, Traefik, Cloudflare Tunnel, Tailscale, or another proxy. The proxy must preserve HTTPS scheme and client forwarding headers, allow Bearer-token access to `/api/v1`, and must not redirect machine API requests to an interactive login. Containerized proxies can attach Frontend through a user-owned Compose override network.

## Database naming

New installations use `subscription_manager` for the bundled PostgreSQL database and role. Existing volumes keep their initialized names unless an explicit database migration is performed; changing Compose defaults alone does not rename a PostgreSQL role or database.

## Acceptance

- Event rolling continues in both `external` and `disabled` notification modes.
- Claim is atomic under concurrent consumers; lease expiry allows recovery.
- Ack/fail enforce actor ownership, retry limits, audit identity, and bounded errors.
- Hermes can complete the documented routine read/edit/reminder scenarios without the Web UI.
- Backend/database remain unpublished and Frontend defaults to loopback-only exposure.
- Existing local data survives the upgrade and a pre-upgrade backup is verified.
