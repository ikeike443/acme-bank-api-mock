def test_login_with_valid_credentials_returns_a_token(client):
    response = client.post("/auth/login", json={"account_id": 1, "pin": "1234"})

    assert response.status_code == 200
    body = response.json()
    assert body["account_id"] == 1
    assert isinstance(body["token"], str)
    assert len(body["token"]) > 0


def test_login_with_wrong_pin_is_rejected(client):
    response = client.post("/auth/login", json={"account_id": 1, "pin": "0000"})

    assert response.status_code == 401


def test_step_up_requires_authentication(client):
    response = client.post("/auth/step-up", json={"account_id": 1})

    assert response.status_code == 401
