"""FastAPI application entrypoint for the Acme Bank API."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.accounts.service import AccountNotFoundError, AccountService
from app.auth.service import AuthService, InvalidCredentialsError
from app.database import get_connection
from app.notifications.service import NotificationService
from app.schemas import (
    AccountResponse,
    LoginRequest,
    LoginResponse,
    StepUpRequest,
    StepUpResponse,
    TransferRequest,
    TransferResponse,
)
from app.transfers.service import (
    DailyLimitExceededError,
    DestinationAccountNotFoundError,
    InsufficientBalanceError,
    InvalidAmountError,
    SelfTransferError,
    SourceAccountFrozenError,
    StepUpAuthenticationRequiredError,
    TransferService,
)

app = FastAPI(title="Acme Bank API", version="0.1.0")

# Maps transfer-service errors to the HTTP status code they should surface
# as. Note this does not cover every exception create_transfer can raise
# (e.g. the source account not existing) -- those fall through to a
# generic 500.
_TRANSFER_ERROR_STATUS = {
    InvalidAmountError: 422,
    SelfTransferError: 422,
    SourceAccountFrozenError: 403,
    DestinationAccountNotFoundError: 404,
    InsufficientBalanceError: 422,
    DailyLimitExceededError: 422,
    StepUpAuthenticationRequiredError: 401,
}


def _build_services() -> None:
    """(Re)build the service singletons against the current DB connection.

    Called once at import time, and again by tests that need a fresh
    in-memory database between test cases.
    """
    global account_service, auth_service, notification_service, transfer_service
    connection = get_connection()
    account_service = AccountService(connection)
    auth_service = AuthService(connection)
    notification_service = NotificationService()
    transfer_service = TransferService(
        account_service=account_service,
        auth_service=auth_service,
        notification_service=notification_service,
        connection=connection,
    )


_build_services()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    try:
        token = auth_service.login(payload.account_id, payload.pin)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return LoginResponse(token=token, account_id=payload.account_id)


@app.post("/auth/step-up", response_model=StepUpResponse)
def request_step_up(payload: StepUpRequest) -> StepUpResponse:
    code = auth_service.request_step_up_code(payload.account_id)
    return StepUpResponse(account_id=payload.account_id, code=code)


@app.get("/accounts/{account_id}", response_model=AccountResponse)
def get_account(account_id: int) -> AccountResponse:
    try:
        account = account_service.get_account(account_id)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AccountResponse(
        id=account.id,
        owner_name=account.owner_name,
        balance=account.balance,
        is_frozen=account.is_frozen,
        daily_limit=account.daily_limit,
    )


@app.post("/transfers", response_model=TransferResponse)
def create_transfer(payload: TransferRequest) -> TransferResponse:
    try:
        transfer = transfer_service.create_transfer(
            source_account_id=payload.source_account_id,
            destination_account_id=payload.destination_account_id,
            amount=payload.amount,
            step_up_code=payload.step_up_code,
        )
    except tuple(_TRANSFER_ERROR_STATUS) as exc:
        status_code = _TRANSFER_ERROR_STATUS[type(exc)]
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return TransferResponse(
        id=transfer.id,
        source_account_id=transfer.source_account_id,
        destination_account_id=transfer.destination_account_id,
        amount=transfer.amount,
        status=transfer.status,
        created_at=transfer.created_at,
    )
