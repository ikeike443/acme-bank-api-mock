import pytest

from app import database
from app.accounts.service import AccountNotFoundError, AccountService
from app.auth.service import AuthService
from app.notifications.service import NotificationService
from app.transfers.service import (
    STEP_UP_AUTH_THRESHOLD,
    DailyLimitExceededError,
    DestinationAccountNotFoundError,
    InsufficientBalanceError,
    InvalidAmountError,
    SelfTransferError,
    SourceAccountFrozenError,
    SourceAccountNotFoundError,
    StepUpAuthenticationRequiredError,
    TransferService,
)


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


def _transfer_rows(service):
    return service._conn.execute("SELECT * FROM transfers").fetchall()


def _fund_account_2(service):
    """Top up account 2 from account 1 so its balance exceeds its daily limit."""
    service.create_transfer(1, 2, STEP_UP_AUTH_THRESHOLD - 1)
    service.create_transfer(1, 2, STEP_UP_AUTH_THRESHOLD - 1)


# --- Amount validation ---


def test_zero_amount_raises_invalid_amount(transfer_service):
    with pytest.raises(InvalidAmountError):
        transfer_service.create_transfer(1, 2, 0)


def test_negative_amount_raises_invalid_amount(transfer_service):
    with pytest.raises(InvalidAmountError):
        transfer_service.create_transfer(1, 2, -1)


# --- Self transfer ---


def test_self_transfer_raises_self_transfer_error(transfer_service):
    with pytest.raises(SelfTransferError):
        transfer_service.create_transfer(1, 1, 10_000)


def test_zero_amount_self_transfer_raises_invalid_amount(transfer_service):
    # Amount validation runs before the self-transfer check.
    with pytest.raises(InvalidAmountError):
        transfer_service.create_transfer(1, 1, 0)


# --- Frozen accounts ---


def test_frozen_source_account_cannot_send(transfer_service):
    with pytest.raises(SourceAccountFrozenError):
        transfer_service.create_transfer(3, 1, 10_000)


def test_frozen_account_can_receive(transfer_service):
    transfer = transfer_service.create_transfer(1, 3, 10_000)

    assert transfer.status == "completed"
    assert transfer_service.accounts.get_account(3).balance == 100_000 + 10_000


# --- Missing accounts ---


def test_nonexistent_destination_raises_destination_not_found(transfer_service):
    with pytest.raises(DestinationAccountNotFoundError):
        transfer_service.create_transfer(1, 999, 10_000)


def test_nonexistent_source_raises_source_not_found(transfer_service):
    with pytest.raises(SourceAccountNotFoundError):
        transfer_service.create_transfer(999, 1, 10_000)


# --- Balance boundaries ---


def test_transfer_of_entire_balance_succeeds(transfer_service):
    # Drain account 2 to exactly zero in two sub-threshold transfers.
    transfer_service.create_transfer(2, 1, 450_000)
    transfer = transfer_service.create_transfer(2, 1, 50_000)

    assert transfer.status == "completed"
    assert transfer_service.accounts.get_account(2).balance == 0


def test_transfer_of_balance_plus_one_fails(transfer_service):
    with pytest.raises(InsufficientBalanceError):
        transfer_service.create_transfer(2, 1, 500_000 + 1)

    assert transfer_service.accounts.get_account(2).balance == 500_000


# --- Step-up authentication ---


def test_transfer_just_below_threshold_needs_no_code(transfer_service):
    transfer = transfer_service.create_transfer(1, 2, STEP_UP_AUTH_THRESHOLD - 1)

    assert transfer.status == "completed"


def test_transfer_at_threshold_without_code_fails(transfer_service):
    with pytest.raises(StepUpAuthenticationRequiredError):
        transfer_service.create_transfer(1, 2, STEP_UP_AUTH_THRESHOLD)


def test_transfer_at_threshold_with_wrong_code_fails(transfer_service):
    transfer_service.auth.request_step_up_code(1)

    with pytest.raises(StepUpAuthenticationRequiredError):
        transfer_service.create_transfer(
            1, 2, STEP_UP_AUTH_THRESHOLD, step_up_code="000000-wrong"
        )


def test_transfer_at_threshold_with_valid_code_succeeds(transfer_service):
    code = transfer_service.auth.request_step_up_code(1)

    transfer = transfer_service.create_transfer(
        1, 2, STEP_UP_AUTH_THRESHOLD, step_up_code=code
    )

    assert transfer.status == "completed"


def test_step_up_code_is_single_use(transfer_service):
    code = transfer_service.auth.request_step_up_code(1)
    transfer_service.create_transfer(1, 2, STEP_UP_AUTH_THRESHOLD, step_up_code=code)

    with pytest.raises(StepUpAuthenticationRequiredError):
        transfer_service.create_transfer(
            1, 2, STEP_UP_AUTH_THRESHOLD, step_up_code=code
        )


# --- Daily limit ---


def test_cumulative_transfers_over_daily_limit_fail(transfer_service):
    _fund_account_2(transfer_service)
    transfer_service.create_transfer(2, 1, 499_999)
    transfer_service.create_transfer(2, 1, 499_999)

    # Running total is 999_998; three more yen would exceed the 1_000_000 limit.
    with pytest.raises(DailyLimitExceededError):
        transfer_service.create_transfer(2, 1, 3)


def test_cumulative_transfers_exactly_at_daily_limit_succeed(transfer_service):
    _fund_account_2(transfer_service)
    transfer_service.create_transfer(2, 1, 499_999)
    transfer_service.create_transfer(2, 1, 499_999)

    transfer = transfer_service.create_transfer(2, 1, 2)

    assert transfer.status == "completed"


def test_failed_transfers_do_not_count_toward_daily_limit(transfer_service):
    _fund_account_2(transfer_service)

    with pytest.raises(DestinationAccountNotFoundError):
        transfer_service.create_transfer(2, 999, 400_000)

    # If the failed 400_000 counted, these would exceed the daily limit.
    transfer_service.create_transfer(2, 1, 499_999)
    transfer_service.create_transfer(2, 1, 499_999)
    transfer = transfer_service.create_transfer(2, 1, 2)

    assert transfer.status == "completed"


# --- Side effects ---


def test_successful_transfer_records_row_and_notifies_both_parties(transfer_service):
    transfer = transfer_service.create_transfer(1, 2, 10_000)

    rows = _transfer_rows(transfer_service)
    assert len(rows) == 1
    assert rows[0]["id"] == transfer.id
    assert rows[0]["source_account_id"] == 1
    assert rows[0]["destination_account_id"] == 2
    assert rows[0]["amount"] == 10_000
    assert rows[0]["status"] == "completed"

    source_notifications = transfer_service.notifications.list_for_account(1)
    destination_notifications = transfer_service.notifications.list_for_account(2)
    assert len(source_notifications) == 1
    assert "Transfer of 10000 to account 2" in source_notifications[0].message
    assert len(destination_notifications) == 1
    assert (
        "Received transfer of 10000 from account 1"
        in destination_notifications[0].message
    )


def test_failed_transfer_has_no_side_effects(transfer_service):
    with pytest.raises(InsufficientBalanceError):
        transfer_service.create_transfer(2, 1, 500_000 + 1)

    assert transfer_service.accounts.get_account(1).balance == 2_000_000
    assert transfer_service.accounts.get_account(2).balance == 500_000
    assert _transfer_rows(transfer_service) == []
    assert transfer_service.notifications.list_for_account(1) == []
    assert transfer_service.notifications.list_for_account(2) == []
