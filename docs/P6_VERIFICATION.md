# P6 Hardening Verification Record

Date: 2026-07-19  
Status: In progress

## Completed: account recovery

- Authenticated password change verifies the current password and revokes all browser Sessions.
- Host-local interactive reset revokes all Sessions and never echoes the password.
- Password change/reset audit snapshots contain timestamps and actor identity, never passwords or hashes.

## Completed: HTTP security boundary

- Backend API success, error, validation, and rate-limit responses include CSP, clickjacking, MIME sniffing, referrer, and browser permissions controls.
- Forwarded HTTPS responses include HSTS.
- Frontend Nginx applies a self-only PWA CSP and the same browser security controls to static and proxied responses.
- API and login limits are independently configurable; health probes are excluded. Rejections return structured HTTP 429 responses with `Retry-After`, request ID, and limit metadata.

## Evidence

- Backend Ruff, format, and mypy: passed.
- Backend pytest: 31 passed, including security headers on success/error, structured throttling, health exclusion, account recovery, authentication, and actor boundaries.
- Isolated Compose Playwright: desktop and 360 px workflows passed; both static and proxied API headers were asserted from the running Nginx container.

## Completed: backup and restore

- Custom-format PostgreSQL backups include SHA-256 sidecars and a default seven-day retention policy.
- A fully isolated gate seeds data, creates a backup, verifies its hash, restores into an empty PostgreSQL volume, runs migrations, starts Backend, requires ready status, verifies required tables/Alembic revision, and performs the core subscription query.
- The gate passed against the current local database (3 subscriptions) and against an isolated seeded source; validation volumes and temporary dumps were removed afterward.

## Remaining P6 work

- 10,000-subscription performance checks and remaining release-candidate evidence.

## Completed: production operations

- Standalone production Compose definitions cover bundled and external PostgreSQL without publishing Backend or database ports.
- Traefik labels require an explicit domain, TLS entrypoint, certificate resolver, and external proxy network.
- systemd units manage application lifecycle and a persistent daily backup timer.
- The operations guide covers install, health, logs, upgrades, rollback, password recovery, Token rotation, notifications, single-Scheduler constraints, and restore sequencing.
- The bundled production topology was started with an isolated Traefik network and empty PostgreSQL volume; migration, Backend health, Frontend health, and the Frontend-to-Backend ready proxy all passed before cleanup.
