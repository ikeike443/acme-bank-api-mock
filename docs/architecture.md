# Architecture

## Overview

The Acme Bank API is a single FastAPI service backed by an in-memory SQLite
database. It is organized around four domains: accounts, authentication,
transfers, and notifications. Each domain owns a `service.py` module that
holds its business logic; the API layer (`app/main.py`) is a thin
translation between HTTP and those services.
- Account and transfer endpoints require the token in an
  `Authorization: Bearer <token>` header, and only allow the authenticated
  account to view its balance or initiate transfers.

```text
              +-------------------+
  HTTP -----> |   app/main.py     |
              | (FastAPI routes)  |
              +---------+---------+
                        |
      +-----------------+------------------+
      |                 |                  |
      v                 v                  v
+-----------+   +---------------+   +------------------+
| accounts  |   |    auth       |   |    transfers      |
| service   |   |   service     |   |    service        |
+-----------+   +---------------+   +--------+----------+
      ^                 ^                    |
      |                 |                    v
      |                 |          +--------------------+
      +-----------------+--------->|   notifications     |
                |                  |      service         |
                v                  +--------------------+
        +----------------+
        |  SQLite (in-    |
        |  memory) via    |
        |  app/database   |
        +----------------+
```

## API layer

`app/main.py` defines the HTTP routes. It is responsible for request/response
validation (via Pydantic models in `app/schemas.py`), translating
service-layer exceptions into HTTP status codes, and nothing else. It does
not contain business logic.

## Authentication

`app/auth/service.py` provides a mock authentication flow:

- `login(account_id, pin)` issues an opaque session token.
- `request_step_up_code(account_id)` / `verify_step_up_code(account_id, code)`
  implement a simple one-time-code challenge used for step-up
  authentication on large transfers.

There is no integration with a real identity provider, SMS gateway, or
email service — everything is generated and verified in-process.

## Accounts

`app/accounts/service.py` reads account rows from SQLite and exposes a
single mutation method, `adjust_balance`, used to debit and credit accounts
during a transfer.

## Transfers

`app/transfers/service.py` is the most business-critical module in the
service. `TransferService.create_transfer` validates a proposed transfer
against the rules in `docs/business-rules.md`, then debits the source
account, credits the destination account, records the transfer, and emits
notifications. It depends on `AccountService` (to read/mutate balances),
`AuthService` (to verify step-up codes), and `NotificationService` (to emit
transfer events).

## Notifications

`app/notifications/service.py` is an in-memory stand-in for a real
notification provider (push/email/SMS). Successful transfers generate a
notification for both the sender and the recipient.

## Persistence

All data lives in a single in-memory SQLite database (`app/database.py`),
shared via a module-level connection. There are two tables: `accounts` and
`transfers`. The database is seeded with a handful of fictional accounts on
startup.

## Request flow: creating a transfer

1. `POST /transfers` is received by `app/main.py` and validated against
   `TransferRequest`.
2. `TransferService.create_transfer` runs the business rules in sequence
   (amount, self-transfer, frozen account, destination existence, balance,
   daily limit, step-up authentication).
3. On success, `AccountService.adjust_balance` is called twice (debit,
   credit), a row is inserted into `transfers`, and `NotificationService`
   is called for both parties.
4. On failure, a specific exception is raised and translated to an HTTP
   status code by the route handler.
