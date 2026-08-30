"""Account lookups and balance mutation.

Balance mutation lives here so the transfer service has a single place to
go through when moving money between accounts, rather than writing SQL of
its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.database import get_connection


class AccountNotFoundError(Exception):
    """Raised when an account_id does not correspond to any known account."""


@dataclass
class Account:
    id: int
    owner_name: str
    balance: int
    is_frozen: bool
    daily_limit: int


class AccountService:
    """Read/write access to account records."""

    def __init__(self, connection=None):
        self._conn = connection or get_connection()

    def get_account(self, account_id: int) -> Account:
        row = self._conn.execute(
            "SELECT id, owner_name, balance, is_frozen, daily_limit "
            "FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if row is None:
            raise AccountNotFoundError(f"account {account_id} not found")
        return Account(
            id=row["id"],
            owner_name=row["owner_name"],
            balance=row["balance"],
            is_frozen=bool(row["is_frozen"]),
            daily_limit=row["daily_limit"],
        )

    def account_exists(self, account_id: int) -> bool:
        try:
            self.get_account(account_id)
        except AccountNotFoundError:
            return False
        return True

    def adjust_balance(self, account_id: int, delta: int, *, commit: bool = True) -> None:
        """Apply a signed delta to an account's balance.

        This does not re-check that the resulting balance is valid; callers
        (e.g. the transfer service) are expected to have already validated
        the transfer before adjusting balances.
        """
        self._conn.execute(
            "UPDATE accounts SET balance = balance + ? WHERE id = ?",
            (delta, account_id),
        )
        if commit:
            self._conn.commit()
