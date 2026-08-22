"""Request/response models for the API layer."""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    account_id: int
    pin: str


class LoginResponse(BaseModel):
    token: str
    account_id: int


class StepUpRequest(BaseModel):
    account_id: int


class StepUpResponse(BaseModel):
    account_id: int
    code: str
    expires_in_minutes: int = 5


class AccountResponse(BaseModel):
    id: int
    owner_name: str
    balance: int
    is_frozen: bool
    daily_limit: int


class TransferRequest(BaseModel):
    source_account_id: int
    destination_account_id: int
    amount: int = Field(gt=0)
    step_up_code: str | None = None


class TransferResponse(BaseModel):
    id: int
    source_account_id: int
    destination_account_id: int
    amount: int
    status: str
    created_at: str
