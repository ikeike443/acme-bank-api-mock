"""HTTP-level integration tests for transfer and related endpoints."""

from app.transfers.service import STEP_UP_AUTH_THRESHOLD


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_step_up_endpoint_returns_code(client):
    response = client.post("/auth/step-up", json={"account_id": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["account_id"] == 1
    assert len(body["code"]) == 6
    assert body["expires_in_minutes"] == 5


def test_create_transfer_via_api(client):
    response = client.post(
        "/transfers",
        json={
            "source_account_id": 1,
            "destination_account_id": 2,
            "amount": 10_000,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_account_id"] == 1
    assert body["destination_account_id"] == 2
    assert body["amount"] == 10_000
    assert body["status"] == "completed"
    assert body["id"] >= 1

    account_response = client.get("/accounts/1")
    assert account_response.json()["balance"] == 2_000_000 - 10_000


def test_create_transfer_with_missing_source_returns_404(client):
    response = client.post(
        "/transfers",
        json={
            "source_account_id": 999,
            "destination_account_id": 1,
            "amount": 1_000,
        },
    )

    assert response.status_code == 404
    assert "source account 999" in response.json()["detail"]


def test_create_transfer_with_missing_destination_returns_404(client):
    response = client.post(
        "/transfers",
        json={
            "source_account_id": 1,
            "destination_account_id": 999,
            "amount": 1_000,
        },
    )

    assert response.status_code == 404
    assert "destination account 999" in response.json()["detail"]


def test_create_transfer_with_insufficient_balance_returns_422(client):
    response = client.post(
        "/transfers",
        json={
            "source_account_id": 2,
            "destination_account_id": 1,
            "amount": 500_000 + 1,
        },
    )

    assert response.status_code == 422
    assert "insufficient balance" in response.json()["detail"]


def test_create_transfer_from_frozen_account_returns_403(client):
    response = client.post(
        "/transfers",
        json={
            "source_account_id": 3,
            "destination_account_id": 1,
            "amount": 1_000,
        },
    )

    assert response.status_code == 403
    assert "frozen" in response.json()["detail"]


def test_create_transfer_at_threshold_without_code_returns_401(client):
    response = client.post(
        "/transfers",
        json={
            "source_account_id": 1,
            "destination_account_id": 2,
            "amount": STEP_UP_AUTH_THRESHOLD,
        },
    )

    assert response.status_code == 401
    assert "step-up" in response.json()["detail"].lower()


def test_create_transfer_at_threshold_with_valid_code_succeeds(client):
    step_up = client.post("/auth/step-up", json={"account_id": 1})
    code = step_up.json()["code"]

    response = client.post(
        "/transfers",
        json={
            "source_account_id": 1,
            "destination_account_id": 2,
            "amount": STEP_UP_AUTH_THRESHOLD,
            "step_up_code": code,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
