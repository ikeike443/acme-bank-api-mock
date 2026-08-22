# Transfer business rules

These rules are enforced by `TransferService.create_transfer`
(`app/transfers/service.py`), in the order listed below. The first rule
that fails aborts the transfer; no partial state is written.

## 1. Amount must be positive

The transfer amount must be strictly greater than zero. A zero or negative
amount is rejected.

## 2. No self-transfers

The source and destination account IDs must differ. An account cannot
transfer money to itself.

## 3. Source account must not be frozen

A frozen account cannot initiate a transfer. This check is only applied to
the source account — a frozen account can still receive funds.

## 4. Destination account must exist

The destination account ID must correspond to an existing account.

## 5. Source account must have sufficient balance

The transfer amount must not exceed the source account's current balance.
Balance is checked at the time of the transfer; there is no reservation or
hold mechanism for in-flight transfers.

## 6. Daily transfer limit

Each account has a daily transfer limit (`daily_limit`), defaulting to
¥1,000,000. A transfer is rejected if the sum of that account's completed
outgoing transfers for the current UTC calendar day, plus the new
transfer's amount, would exceed the limit.

The daily total only includes transfers where the account was the source,
and only transfers with `status = "completed"`. The window resets at UTC
midnight.

Boundary condition: a transfer that brings the daily total to exactly the
limit is allowed; a transfer that would push it one unit over the limit is
rejected.

## 7. Step-up authentication for large transfers

Transfers with an amount at or above the step-up threshold (¥500,000)
require a valid step-up code, obtained via `AuthService.request_step_up_code`
and supplied as `step_up_code`. A missing, expired, already-used, or
incorrect code causes the transfer to be rejected.

Boundary condition: a transfer of exactly the threshold amount requires
step-up authentication; a transfer of one unit less does not.

## 8. Notification on success

A successful transfer emits a notification to both the source account (a
confirmation that funds were sent) and the destination account (a
notification that funds were received). Notifications are not emitted for
transfers that fail validation.
