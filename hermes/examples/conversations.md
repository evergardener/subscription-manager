# Conversation examples

## Create

User: Add Claude Max at USD 100 monthly, renewing on 2026-08-21, with auto-renewal.

Hermes: I will create Claude Max at USD 100 every month, next renewal 2026-08-21, with auto-renewal enabled. Please confirm.

After confirmation, call `subscription_create --confirm` with the exact values. Do not derive a different renewal date.

## Payment

User: I paid the current Claude Max bill today.

Search, get details, and list upcoming events. If exactly one current planned billing event matches, reply with the stored amount, currency, payment timestamp, event date/ID, and `advance_schedule=true`. Call `payment_record --confirm` only after confirmation. If the amount or event is unclear, ask.

## Cancellation

User: Cancel Claude Max.

Explain that Hermes cannot cancel on the vendor website. Offer to record a planned cancellation in Subscription Manager and ask for the service expiry date. Never claim the external service is cancelled.
After the user supplies the date, fetch the latest subscription version, repeat the target status, expiry date, reason, and local-only effect, then call `subscription_transition --confirm` only after explicit confirmation.
