def test_get_account_returns_account_details(client):
    response = client.get("/accounts/1")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["owner_name"] == "Alice Tanaka"
    assert body["balance"] == 2_000_000
    assert body["is_frozen"] is False


def test_get_account_that_does_not_exist_returns_404(client):
    response = client.get("/accounts/999")

    assert response.status_code == 404
