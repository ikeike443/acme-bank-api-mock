"""HTTP-level integration tests for transfer and related endpoints.

These tests exercise the hardened API, which requires a valid Bearer token
on every authenticated endpoint and enforces that a caller may only act on
their own account. Business rules that cannot be reached through the
ownership gate (e.g. a non-existent *source* account) are covered at the
service layer in ``tests/test_transfers.py``.
"""

from app.transfers.service import STEP_UP_AUTH_THRESHOLD


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_step_up_endpoint_returns_code(client, auth_headers):
    response = client.post(
        "/auth/step-up", headers=auth_headers, json={"account_id": 1}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account_id"] == 1
    assert len(body["code"]) == 6
    assert body["expires_in_minutes"] == 5


def test_create_transfer_via_api(client, auth_headers):
    response = client.post(
        "/transfers",
        headers=auth_headers,
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

    account_response = client.get("/accounts/1", headers=auth_headers)
    assert account_response.json()["balance"] == 2_000_000 - 10_000


def test_create_transfer_with_unowned_source_returns_403(client, auth_headers):
    # A non-existent source account is also not owned by the caller, so the
    # hardened API rejects it with 403 before any existence check could leak
    # which account IDs exist. The source-not-found business rule itself is
    # covered at the service layer in tests/test_transfers.py.
    response = client.post(
        "/transfers",
        headers=auth_headers,
        json={
            "source_account_id": 999,
            "destination_account_id": 1,
            "amount": 1_000,
        },
    )

    assert response.status_code == 403


def test_create_transfer_with_missing_destination_returns_404(client, auth_headers):
    response = client.post(
        "/transfers",
        headers=auth_headers,
        json={
            "source_account_id": 1,
            "destination_account_id": 999,
            "amount": 1_000,
        },
    )

    assert response.status_code == 404
    assert "destination account 999" in response.json()["detail"]


def test_create_transfer_with_insufficient_balance_returns_422(
    client, make_auth_headers
):
    # Bob (account 2) has a balance of 500,000; one yen more must be rejected.
    auth = make_auth_headers(2)
    response = client.post(
        "/transfers",
        headers=auth,
        json={
            "source_account_id": 2,
            "destination_account_id": 1,
            "amount": 500_000 + 1,
        },
    )

    assert response.status_code == 422
    assert "insufficient balance" in response.json()["detail"]


def test_create_transfer_from_frozen_account_returns_403(
    client, make_auth_headers
):
    # Carol (account 3) is seeded frozen; she must be rejected when sending.
    auth = make_auth_headers(3)
    response = client.post(
        "/transfers",
        headers=auth,
        json={
            "source_account_id": 3,
            "destination_account_id": 1,
            "amount": 1_000,
        },
    )

    assert response.status_code == 403
    assert "frozen" in response.json()["detail"]


def test_create_transfer_at_threshold_without_code_returns_401(client, auth_headers):
    response = client.post(
        "/transfers",
        headers=auth_headers,
        json={
            "source_account_id": 1,
            "destination_account_id": 2,
            "amount": STEP_UP_AUTH_THRESHOLD,
        },
    )

    assert response.status_code == 401
    assert "step-up" in response.json()["detail"].lower()


def test_create_transfer_at_threshold_with_valid_code_succeeds(client, auth_headers):
    step_up = client.post(
        "/auth/step-up", headers=auth_headers, json={"account_id": 1}
    )
    code = step_up.json()["code"]

    response = client.post(
        "/transfers",
        headers=auth_headers,
        json={
            "source_account_id": 1,
            "destination_account_id": 2,
            "amount": STEP_UP_AUTH_THRESHOLD,
            "step_up_code": code,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
