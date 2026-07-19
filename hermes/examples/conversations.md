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

## Reminder rule

User: Remind me five days and one day before Claude Max renews.

Resolve the subscription, read its current rules, and repeat both offsets. After explicit confirmation, call `reminder_rules_set --confirm` with `channel=external`. Explain that Subscription Manager schedules and deduplicates the reminders while Hermes performs final delivery.

## Scheduled due reminder

A recurring Hermes job calls `reminders_claim`. For each result, notify the user using the configured Hermes channel, then call `reminder_ack`. If delivery fails, call `reminder_fail` with a sanitized operational error. This machine workflow does not ask the user for confirmation because it executes a previously confirmed reminder rule.
