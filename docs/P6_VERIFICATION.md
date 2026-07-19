# P6 Hardening Verification Record

Date: 2026-07-19  
Status: Complete

## Security and account recovery

- Authenticated password change verifies the current password, revokes all browser Sessions, and clears client business caches.
- Host-local interactive password reset revokes all Sessions and never echoes the password.
- Password changes and resets create security audit entries without storing passwords or hashes.
- Backend and Nginx responses apply CSP, clickjacking, MIME-sniffing, referrer, and permissions controls; forwarded HTTPS responses add HSTS.
- Login and general API limits are independently configurable. Structured 429 responses include `Retry-After`, request ID, and limit metadata; health probes are excluded.

## Backup, restore, and deployment

- PostgreSQL custom-format backups include SHA-256 sidecars and default seven-day retention.
- Restore verification checks the hash, restores into an empty volume, runs migrations, requires Backend ready status, validates required tables and Alembic revision, and performs a core subscription query.
- Restore passed against the local database with three subscriptions and an isolated seeded database. Temporary validation volumes were removed.
- Production Compose definitions cover bundled and external PostgreSQL without publishing Backend or database ports. Traefik labels require an explicit domain, TLS entrypoint, certificate resolver, and external proxy network.
- systemd units manage application lifecycle and a persistent daily backup timer. The runbook covers install, health, logs, upgrade, rollback, password recovery, Token rotation, notifications, the single-Scheduler rule, and restore sequencing.
- The bundled production topology passed migration, Backend health, Frontend health, and Frontend-to-Backend ready-proxy checks on an isolated network and empty volume.

## 10,000-subscription performance gate

The isolated PostgreSQL gate seeded 10,000 subscriptions, 10,000 current plans, and 10,000 planned billing events, then measured 20 HTTP samples after three warmups with a real scoped Token:

| API | P95 | Limit | Response size |
| --- | ---: | ---: | ---: |
| Subscription list | 49.16 ms | 500 ms | 82,051 bytes |
| Subscription search | 77.34 ms | 500 ms | 867 bytes |
| Analytics summary | 64.09 ms | 500 ms | 8,210 bytes |
| Upcoming events, 30 days | 472.76 ms | 1,000 ms | 4,095,501 bytes |

CI runs the same threshold gate and removes the test volume afterward.

## Complete acceptance and browser matrix

- Backend Ruff, format, and mypy passed. All 31 backend tests passed; domain/service coverage was 81.23% against an 80% gate.
- All 9 frontend unit tests, ESLint, TypeScript checking, and the production PWA build passed.
- The complete authenticated workflow passed at desktop, 768 px, and 360 px in Microsoft Edge 150.0.4078.65, and at the same three viewports in Chrome for Testing 149.0.7827.55. Firefox 151.0 passed the same workflow in both isolated runs.
- The workflow covers login, non-renewing creation, plan/date editing, payment schedule advancement, two reminders, archive/restore, offline stale-data warning and write blocking, logout cache clearing, and password-change Session revocation.
- It records `pending_cancel`, verifies the service-expiry date and absence of later planned billing events, withdraws cancellation, and verifies active status, auto-renewal, and regenerated events.
- It verifies one-time Token reveal and revocation, and proves a read-only Token receives 403 from audit and Token-management APIs.
- Hermes now exposes a confirmation-required cancellation transition Tool with optimistic locking, mandatory reason, mandatory expiry for `pending_cancel`, local-only wording, real scoped-Token API coverage, and Hermes actor audit evidence.

## Migration and release-candidate evidence

- On a disposable PostgreSQL database, `alembic check` reported no drift; downgrade to base and upgrade to head both completed successfully.
- Before updating the existing local instance, a hashed backup was created. `alembic upgrade head` preserved all three subscriptions, left revision `ae17e2c0f9f8`, and the upgraded stack returned ready 200.
- The current local instance was rebuilt from the release-candidate source and is healthy at `http://localhost:8080`; direct Backend OpenAPI and docs returned 200 at port 8000.
- CI includes backend lint/type/coverage/migration checks, frontend lint/type/unit/build checks, Compose validation, the full Chromium/Firefox acceptance suite, backup/restore, and the 10k performance gate.

All P6 deliverables and the specification chapter 12/15 release-candidate gates have implementation and repeatable evidence. P6 is closed.
