import pytest
from fastapi.testclient import TestClient

from app import database, main


def _login_headers(client, account_id: int, pin: str) -> dict[str, str]:
    """Log in and return Authorization headers for the given seeded account."""
    response = client.post(
        "/auth/login", json={"account_id": account_id, "pin": pin}
    )
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def client():
    """A TestClient backed by a fresh, isolated in-memory database."""
    database.reset_database()
    main._build_services()
    return TestClient(main.app)


@pytest.fixture
def auth_headers(client):
    """Headers for the seeded Alice account (account 1)."""
    return _login_headers(client, 1, "1234")


@pytest.fixture
def make_auth_headers(client):
    """Factory returning auth headers for any seeded account.

    Used by HTTP integration tests that need to act as a non-Alice account
    (e.g. Bob for the insufficient-balance rule, Carol for the frozen rule).
    """

    def _make(account_id: int, pin: str = "1234") -> dict[str, str]:
        return _login_headers(client, account_id, pin)

    return _make
