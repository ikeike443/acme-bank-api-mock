"""Money transfers between accounts.

This is the most business-critical module in the service: every rule here
exists to protect the bank or its customers from a bad transfer (moving
money that shouldn't move, or not being able to move money that should).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.accounts.service import AccountNotFoundError, AccountService
from app.auth.service import AuthService
from app.database import get_connection
from app.notifications.service import NotificationService

# Default daily transfer limit, in JPY, for accounts that don't override it.
DAILY_TRANSFER_LIMIT_DEFAULT = 1_000_000

# Transfers at or above this amount require step-up authentication.
STEP_UP_AUTH_THRESHOLD = 500_000


class TransferError(Exception):
    """Base class for all transfer validation/failure errors."""


class InvalidAmountError(TransferError):
    """Raised when the transfer amount is not greater than zero."""


class SelfTransferError(TransferError):
    """Raised when the source and destination accounts are the same."""


class SourceAccountFrozenError(TransferError):
    """Raised when the source account is frozen."""


class DestinationAccountNotFoundError(TransferError):
    """Raised when the destination account does not exist."""


class InsufficientBalanceError(TransferError):
    """Raised when the source account does not have enough available balance."""


class DailyLimitExceededError(TransferError):
    """Raised when a transfer would push the source account over its daily limit."""


class StepUpAuthenticationRequiredError(TransferError):
    """Raised when a large transfer is missing a valid step-up code."""


@dataclass
class Transfer:
    id: int
    source_account_id: int
    destination_account_id: int
    amount: int
    status: str
    created_at: str


class TransferService:
    def __init__(
        self,
        account_service: AccountService | None = None,
        auth_service: AuthService | None = None,
        notification_service: NotificationService | None = None,
        connection=None,
    ):
        self._conn = connection or get_connection()
        self.accounts = account_service or AccountService(self._conn)
        self.auth = auth_service or AuthService(self._conn)
        self.notifications = notification_service or NotificationService()

    def create_transfer(
        self,
        source_account_id: int,
        destination_account_id: int,
        amount: int,
        step_up_code: str | None = None,
    ) -> Transfer:
        if amount <= 0:
            raise InvalidAmountError("transfer amount must be greater than zero")

        if source_account_id == destination_account_id:
            raise SelfTransferError("an account cannot transfer to itself")

        source = self.accounts.get_account(source_account_id)

        if source.is_frozen:
            raise SourceAccountFrozenError(
                f"account {source_account_id} is frozen and cannot send transfers"
            )

        try:
            self.accounts.get_account(destination_account_id)
        except AccountNotFoundError as exc:
            raise DestinationAccountNotFoundError(
                f"destination account {destination_account_id} does not exist"
            ) from exc

        if amount > source.balance:
            raise InsufficientBalanceError(
                f"account {source_account_id} has insufficient balance"
            )

        already_transferred_today = self._transferred_today(source_account_id)
        if already_transferred_today + amount > source.daily_limit:
            raise DailyLimitExceededError(
                f"transfer would exceed the daily limit of {source.daily_limit}"
            )

        if amount >= STEP_UP_AUTH_THRESHOLD:
            if not step_up_code or not self.auth.verify_step_up_code(
                source_account_id, step_up_code
            ):
                raise StepUpAuthenticationRequiredError(
                    "transfers at or above the step-up threshold require "
                    "additional authentication"
                )

        self.accounts.adjust_balance(source_account_id, -amount)
        self.accounts.adjust_balance(destination_account_id, amount)

        created_at = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            "INSERT INTO transfers "
            "(source_account_id, destination_account_id, amount, status, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                source_account_id,
                destination_account_id,
                amount,
                "completed",
                created_at,
            ),
        )
        self._conn.commit()

        self.notifications.notify(
            source_account_id,
            f"Transfer of {amount} to account {destination_account_id} completed.",
        )
        self.notifications.notify(
            destination_account_id,
            f"Received transfer of {amount} from account {source_account_id}.",
        )

        return Transfer(
            id=cursor.lastrowid,
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            amount=amount,
            status="completed",
            created_at=created_at,
        )

    def _transferred_today(self, account_id: int) -> int:
        """Sum of completed transfers sent from this account since UTC midnight."""
        today_prefix = datetime.now(timezone.utc).date().isoformat()
        row = self._conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM transfers "
            "WHERE source_account_id = ? AND status = 'completed' "
            "AND created_at LIKE ?",
            (account_id, f"{today_prefix}%"),
        ).fetchone()
        return row["total"]
