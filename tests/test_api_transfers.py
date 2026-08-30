def test_transfer_requires_authentication(client):
    response = client.post(
        "/transfers",
        json={
            "source_account_id": 1,
            "destination_account_id": 2,
            "amount": 10_000,
        },
    )

    assert response.status_code == 401


def test_transfer_cannot_be_started_from_another_account(client, auth_headers):
    response = client.post(
        "/transfers",
        headers=auth_headers,
        json={
            "source_account_id": 2,
            "destination_account_id": 1,
            "amount": 10_000,
        },
    )

    assert response.status_code == 403


def test_transfer_with_unowned_source_is_rejected(client, auth_headers):
    response = client.post(
        "/transfers",
        headers=auth_headers,
        json={
            "source_account_id": 999,
            "destination_account_id": 1,
            "amount": 10_000,
        },
    )

    assert response.status_code == 403
