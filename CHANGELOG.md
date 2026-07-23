# Changelog

This file records user-visible changes and deployment-relevant maintenance for Hermes Subscription Manager. Dates use Asia/Shanghai calendar dates.

## 2026-07-23

### Fixed

- Archived subscriptions no longer contribute future billing events, Upcoming Events, forecast analytics, Dashboard renewal totals, or new and claimable reminder deliveries.
- Historical plans, payments, deliveries, and audit records remain available after archiving; restoring a subscription makes its relevant future schedule eligible again.
- Added `greenlet` as an explicit Backend dependency so SQLAlchemy async database operations work on Apple Silicon as well as the previously covered platforms.
- Updated the Frontend lockfile from vulnerable `fast-uri` 3.1.3 to 3.1.4.
- Updated the P0 architecture validator to recognize and verify all six current CI jobs.

### Changed

- Project documentation now records that the application is connected to Hermes and in real-world use.
- The P0 development-host handoff is explicitly marked as a historical snapshot.
- Added regression coverage for archived-subscription forecasts, event visibility, event generation, reminder generation, and reminder claiming.

### Validation

- Backend Ruff, format, and strict mypy checks passed.
- All 33 Backend tests passed with 84.64% domain/service coverage.
- Alembic reported no metadata drift; downgrade to base and upgrade to head passed against an isolated PostgreSQL database.
- Frontend audit reported zero vulnerabilities; lint, type-check, all 9 unit tests, and the production PWA build passed.
- The isolated Docker Compose stack rebuilt successfully, migrated to `b6d2c9e41a70`, returned 200 from Backend and Frontend health endpoints, and produced no blocking Backend, Scheduler, Frontend, or migration log errors.

### Deployment notes

- No database migration was added.
- Pull the new revision and rebuild the Backend, Scheduler, migration, and Frontend images so both updated lockfiles take effect.
- Existing subscription and payment data require no manual conversion.

## Earlier milestones

P0 through P6.1 implementation and verification history predates this changelog. See the milestone records under [`docs/`](docs/) and the current status in [`README.md`](README.md).
