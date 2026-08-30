def test_get_account_returns_account_details(client, auth_headers):
    response = client.get("/accounts/1", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["owner_name"] == "Alice Tanaka"
    assert body["balance"] == 2_000_000
    assert body["is_frozen"] is False


def test_get_account_that_does_not_exist_returns_404(client, auth_headers):
    response = client.get("/accounts/999", headers=auth_headers)

    assert response.status_code == 404


def test_get_account_requires_authentication(client):
    response = client.get("/accounts/1")

    assert response.status_code == 401


def test_account_cannot_be_viewed_by_another_user(client, auth_headers):
    response = client.get("/accounts/2", headers=auth_headers)

    assert response.status_code == 403
