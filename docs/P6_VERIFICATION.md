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

## Remaining P6 work

- PostgreSQL backup creation and actual restore into an empty database.
- Traefik and systemd examples plus long-running operations guide.
- 10,000-subscription performance checks and remaining release-candidate evidence.
