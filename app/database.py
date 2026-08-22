"""SQLite-backed storage for the Acme Bank API.

The service uses a single in-memory SQLite database. This is enough to give
the rest of the application (accounts, transfers) a realistic persistence
layer without the operational overhead of a real database server.
"""
from __future__ import annotations

import sqlite3

_connection: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    """Return the shared application database connection, creating it if needed."""
    global _connection
    if _connection is None:
        _connection = _create_connection()
    return _connection


def reset_database() -> sqlite3.Connection:
    """Recreate the database from scratch and reseed it.

    Primarily useful for tests, where each test should start from a known,
    isolated state.
    """
    global _connection
    if _connection is not None:
        _connection.close()
    _connection = _create_connection()
    return _connection


def _create_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _create_schema(conn)
    _seed(conn)
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            owner_name TEXT NOT NULL,
            balance INTEGER NOT NULL,
            is_frozen INTEGER NOT NULL DEFAULT 0,
            daily_limit INTEGER NOT NULL,
            pin TEXT NOT NULL
        );

        CREATE TABLE transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_account_id INTEGER NOT NULL,
            destination_account_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def _seed(conn: sqlite3.Connection) -> None:
    # Fictional sample accounts used for local development and tests.
    # Amounts are in JPY. Account 3 is seeded frozen so the frozen-account
    # business rule has something to exercise out of the box.
    accounts = [
        (1, "Alice Tanaka", 2_000_000, 0, 1_000_000, "1234"),
        (2, "Bob Yamada", 500_000, 0, 1_000_000, "1234"),
        (3, "Carol Suzuki", 100_000, 1, 1_000_000, "1234"),
        (4, "Acme Corp Escrow", 10_000_000, 0, 5_000_000, "9999"),
    ]
    conn.executemany(
        "INSERT INTO accounts (id, owner_name, balance, is_frozen, daily_limit, pin) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        accounts,
    )
    conn.commit()
