# Changelog

This file records user-visible changes and deployment-relevant maintenance for Hermes Subscription Manager. Dates use Asia/Shanghai calendar dates.

## 2026-08-16

### Added

- Subscriptions now carry an optional `start_date`, and list/detail responses include a `spend` summary (per-currency totals and payment count) covering every recorded payment since the subscription started.
- The Web UI shows the subscription period and cumulative actual spend on the subscription list and detail pages.
- First-run administrator setup is available directly from the login page; a new unauthenticated `GET /api/v1/auth/bootstrap` endpoint reports whether setup is still required. The API bootstrap path remains available for automation.
- Payments can be corrected after recording through `PATCH /api/v1/subscriptions/{id}/payments/{payment_id}` (optimistic locking via `expected_version`), exposed to Hermes as the new confirmation-gated `payment_update` tool. Corrections can change amount, currency, paid time, tax, and notes, but never rebind billing events or advance the schedule.
- The account username can be changed from the Settings page after verifying the current password; active sessions stay valid.
- The analytics page now reports three figures per currency: annualized expected spend from current billing plans, trailing-twelve-month actual spend, and all-time total spend. Vendor, category, and a current/all scope filter (including expired and archived subscriptions) are available as in-page filters instead of a separate page.

### Fixed

- Money fields in edit and payment dialogs consistently display two decimal places.
- The sidebar menu alignment was corrected, and the offline read-only banner now recovers automatically once connectivity returns instead of sticking.
- The subscription detail hero no longer collapses Chinese titles into vertical text on narrow widths.

### Changed

- Analytics scope defaults to current (non-expired, non-archived) subscriptions; selecting the all scope includes historical spend of expired subscriptions so totals remain visible after a subscription ends.
- Regression coverage added for subscription start dates and spend summaries, payment corrections, analytics scope/filters, username changes, and bootstrap setup; test-suite rate limiting was relaxed so the full suite runs without artificial throttling.

### Validation

- All 38 Backend tests passed; Ruff and mypy checks passed.
- All 13 Frontend unit tests passed; type-check, lint, and the production build passed.

### Deployment notes

- No database migration was added; existing subscription and payment data require no manual conversion.
- After CI publishes the new images, pull the new deployment revision on the Hermes host and run Compose `pull` and `up -d --wait` with `IMAGE_TAG=latest`.

## 2026-07-23

### Added

- Added a gated GitHub Actions publishing job for Backend and Frontend GHCR images on `linux/amd64` and `linux/arm64`.
- Added immutable `sha-<full commit>`, moving `main`, moving `latest`, and SemVer image tags. `latest` updates only after every CI job succeeds on `main`.

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
- Production Compose and systemd now pull prebuilt GHCR images instead of compiling application source on the Hermes host.
- Backend CI and the P0 gate invoke pytest through the active Python interpreter, avoiding console-script import-path differences across development hosts.
- Production Compose and deployment documentation now explicitly identify both GHCR packages as public and require no registry credentials on the Hermes host.

### Validation

- Backend Ruff, format, and strict mypy checks passed.
- All 33 Backend tests passed with 84.64% domain/service coverage.
- Alembic reported no metadata drift; downgrade to base and upgrade to head passed against an isolated PostgreSQL database.
- Frontend audit reported zero vulnerabilities; lint, type-check, all 9 unit tests, and the production PWA build passed.
- The isolated Docker Compose stack rebuilt successfully, migrated to `b6d2c9e41a70`, returned 200 from Backend and Frontend health endpoints, and produced no blocking Backend, Scheduler, Frontend, or migration log errors.
- The GHCR workflow and both image-based production Compose variants passed static validation; the native Docker builds used by the workflow also passed the isolated full-stack smoke test.
- Anonymous manifest inspection succeeded for both `latest` images and confirmed `linux/amd64` and `linux/arm64` variants.

### Deployment notes

- No database migration was added.
- Both GHCR Packages are already Public; do not configure a GitHub PAT or GHCR login on the deployment host.
- Pull the new deployment revision, keep `IMAGE_TAG=latest` for automatic newest-successful deployment or pin the published `sha-*` tag, then run Compose `pull` and `up -d --wait`.
- Existing subscription and payment data require no manual conversion.

## Earlier milestones

P0 through P6.1 implementation and verification history predates this changelog. See the milestone records under [`docs/`](docs/) and the current status in [`README.md`](README.md).
