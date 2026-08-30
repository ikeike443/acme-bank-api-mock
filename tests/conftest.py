import pytest
from fastapi.testclient import TestClient

from app import database, main


@pytest.fixture
def client():
    """A TestClient backed by a fresh, isolated in-memory database."""
    database.reset_database()
    main._build_services()
    return TestClient(main.app)


@pytest.fixture
def auth_headers(client):
    """Headers for the seeded Alice account."""
    response = client.post("/auth/login", json={"account_id": 1, "pin": "1234"})
    return {"Authorization": f"Bearer {response.json()['token']}"}
