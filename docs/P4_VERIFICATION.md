# P4 Verification Record

Date: 2026-07-18  
Milestone: P4 PWA  
Environment: Windows development host, Docker Linux Engine, PostgreSQL 16.14, Chromium/Edge

## Delivered scope

- Authenticated application shell with session restore, CSRF handling, responsive navigation, and logout.
- Dashboard summaries, upcoming renewals, subscription CRUD workflows, plan changes, payments, reminders, archive/restore, and audit history.
- Upcoming Events, per-currency analytics, settings, theme selection, and create-once/revocable scoped API Tokens.
- Installable PWA shell with IndexedDB-backed recent read cache, explicit offline status, blocked offline writes, and cache clearing on logout.

## Automated evidence

The disposable PostgreSQL quality gate completed with:

- Ruff check and format check: passed.
- mypy: 39 source files, no issues.
- pytest: 23 passed.
- Domain/service coverage: 80.63% (required minimum 80%).
- Alembic metadata drift: none.
- Alembic downgrade to base and upgrade to head: passed.
- Architecture/configuration validation: passed.
- npm audit at high severity: 0 vulnerabilities.
- ESLint and TypeScript project build: passed.
- Vitest: 2 files, 3 tests passed.
- Vite production/PWA build: passed; service worker, manifest, and six-entry precache generated.

Playwright ran the complete authenticated P4 workflow against the rebuilt Compose stack:

| Project | Viewport | Result |
| --- | --- | --- |
| desktop | Desktop default | Passed |
| mobile-360 | 360 px wide | Passed; no horizontal overflow |

Both projects exercised login, non-renewing subscription creation, key-date editing, auto-renew changes, payment recording with schedule advancement, two reminder rules, archive/restore, one-time Token display and revocation, offline write blocking, and logout. The suite is located at `frontend/e2e/p4.spec.ts` and runs through `scripts/verify-e2e.ps1` against a fresh isolated Compose project and database. GitHub Actions runs the same gate with bundled Chromium.

## Regression fixed during verification

Archiving a subscription originally mutated the ORM entity before reading its current plan. PostgreSQL server timestamps combined with autoflush could expire the entity inside the asynchronous request and raise `MissingGreenlet`. The endpoint now reads the current plan first; an integration regression test covers archive and restore.

## Exit criteria

- 360 px layout has no horizontal scrolling: passed.
- Offline mode is read-only and visibly identified: passed.
- Logout clears application IndexedDB cache: implemented and covered by the offline/session behavior tests.

P4 is complete. P5 Hermes is the next implementation milestone.
