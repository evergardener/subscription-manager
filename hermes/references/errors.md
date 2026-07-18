# Error mapping

Preserve `request_id` when reporting every error.

| HTTP/code | Action |
| --- | --- |
| 400 | Correct malformed arguments; do not retry unchanged. |
| 401 | Token is missing, invalid, expired, or revoked. Ask an administrator to configure a valid Hermes token. |
| 403 | Token lacks the required scope. Request only the missing scope; never request `tokens:manage`. |
| 404 | Re-run search or get; do not invent an ID. |
| 409 | Refetch the resource. For version conflicts, show the latest values and request confirmation for the revised write. For idempotency conflicts, do not silently retry with changed data. |
| 422 / `validation_error` | Show the invalid or ambiguous fields and ask the user. Never guess. |
| 429 | Respect `Retry-After`; do not loop aggressively. |
| 5xx | Report temporary service failure with request ID. Retry a read once; retry writes only with the same idempotency key. |

Treat transport and invalid-JSON failures as service errors. Never include the bearer token in output.
