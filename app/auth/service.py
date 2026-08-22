"""Mock authentication for the Acme Bank API.

Sessions are opaque tokens kept in memory, and step-up codes are generated
locally instead of being delivered through a real SMS/email provider. This
is sufficient for the sandbox but is not a real authentication system.
"""
from __future__ import annotations

import random
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.database import get_connection

STEP_UP_CODE_TTL_MINUTES = 5


class InvalidCredentialsError(Exception):
    """Raised when login credentials do not match a known account."""


@dataclass
class StepUpChallenge:
    code: str
    expires_at: datetime


class AuthService:
    def __init__(self, connection=None):
        self._conn = connection or get_connection()
        self._sessions: dict[str, int] = {}
        self._step_up_challenges: dict[int, StepUpChallenge] = {}

    def login(self, account_id: int, pin: str) -> str:
        row = self._conn.execute(
            "SELECT pin FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if row is None or row["pin"] != pin:
            raise InvalidCredentialsError("invalid account_id or pin")
        token = uuid.uuid4().hex
        self._sessions[token] = account_id
        return token

    def account_for_token(self, token: str) -> int | None:
        return self._sessions.get(token)

    def request_step_up_code(self, account_id: int) -> str:
        code = "".join(random.choices(string.digits, k=6))
        self._step_up_challenges[account_id] = StepUpChallenge(
            code=code,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=STEP_UP_CODE_TTL_MINUTES),
        )
        return code

    def verify_step_up_code(self, account_id: int, code: str) -> bool:
        challenge = self._step_up_challenges.get(account_id)
        if challenge is None:
            return False
        if datetime.now(timezone.utc) > challenge.expires_at:
            return False
        if challenge.code != code:
            return False
        # Step-up codes are single use.
        del self._step_up_challenges[account_id]
        return True
