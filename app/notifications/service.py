"""In-memory stand-in for a real push/email/SMS notification provider."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Notification:
    id: int
    recipient_id: int
    message: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationService:
    def __init__(self):
        self._notifications: list[Notification] = []
        self._next_id = 1

    def notify(self, account_id: int, message: str) -> Notification:
        notification = Notification(
            id=self._next_id,
            recipient_id=account_id,
            message=message,
        )
        self._notifications.append(notification)
        self._next_id += 1
        return notification

    def list_for_account(self, account_id: int) -> list[Notification]:
        return [n for n in self._notifications if n.recipient_id == account_id]
