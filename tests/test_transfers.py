import pytest

from app import database
from app.accounts.service import AccountService
from app.auth.service import AuthService
from app.notifications.service import NotificationService
from app.transfers.service import InsufficientBalanceError, TransferService


@pytest.fixture
def transfer_service():
    connection = database.reset_database()
    return TransferService(
        account_service=AccountService(connection),
        auth_service=AuthService(connection),
        notification_service=NotificationService(),
        connection=connection,
    )


def test_successful_transfer_moves_funds_between_accounts(transfer_service):
    transfer = transfer_service.create_transfer(
        source_account_id=1,
        destination_account_id=2,
        amount=10_000,
    )

    assert transfer.status == "completed"
    assert transfer_service.accounts.get_account(1).balance == 2_000_000 - 10_000
    assert transfer_service.accounts.get_account(2).balance == 500_000 + 10_000


def test_transfer_fails_when_balance_is_insufficient(transfer_service):
    with pytest.raises(InsufficientBalanceError):
        transfer_service.create_transfer(
            source_account_id=2,
            destination_account_id=1,
            amount=999_999_999,
        )

    # The source balance must be unchanged after a failed transfer.
    assert transfer_service.accounts.get_account(2).balance == 500_000
