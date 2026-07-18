# P5 Hermes Verification Record

Date: 2026-07-19  
Milestone: P5 Hermes

## Delivered scope

- Repository-native `hermes` Skill with machine-readable schemas for eight MVP tools.
- Environment-only bearer authentication; no token persistence or database access.
- Deterministic caller with argument allowlists, idempotency keys, client-side result filters, request IDs, and explicit confirmation for all writes.
- Error mapping for authentication, scope, validation, optimistic locking, idempotency, throttling, and service failures.
- Server-side prevention of privileged Hermes scopes, including `tokens:manage` and `reminders:scan`.

## Automated evidence

- Skill frontmatter and structure: `quick_validate.py` passed.
- Tool schema JSON and caller Python compilation: passed.
- Backend Ruff, format, mypy: passed.
- Backend pytest: 28 passed, including Hermes confirmation, real API Token scopes, actor audit identity, and forged Actor Header rejection.
- `scripts/verify-hermes.ps1`: isolated Compose database, real bearer token, `subscription_create`, `subscription_get`, and audit actor verification passed; temporary volume removed afterward.

## Security result

The service derives `actor_type=hermes` and `actor_id` from the hashed API Token record. Client-supplied Actor headers do not affect authorization or audit data. Hermes tokens cannot receive `tokens:manage`.
