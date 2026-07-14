"""Tests for auth, password strength, and account privacy.

These tests never touch a real MongoDB. The route handlers in app.py use a
module-level ``users`` collection, so each test swaps in an in-memory fake
(see ``FakeCollection``) via monkeypatch. That keeps the suite fast and lets
it run anywhere without a database.
"""

import pytest
from werkzeug.security import generate_password_hash

import app as app_module
from password_strength import evaluate_password


class FakeCollection:
    """Minimal stand-in for a pymongo collection.

    Implements just the operations the routes use: insert_one, find_one, and
    find().sort(). Documents are kept in a plain list.
    """

    def __init__(self):
        self._docs = []
        self._next_id = 1

    def insert_one(self, doc):
        stored = dict(doc)
        stored.setdefault("_id", self._next_id)
        self._next_id += 1
        self._docs.append(stored)
        return type("InsertOneResult", (), {"inserted_id": stored["_id"]})()

    def find_one(self, query):
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def find(self, query=None):
        query = query or {}
        matched = [
            doc
            for doc in self._docs
            if all(doc.get(k) == v for k, v in query.items())
        ]
        return _FakeCursor(matched)


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, key, direction=1):
        self._docs.sort(key=lambda d: d.get(key), reverse=direction < 0)
        return self._docs

    def __iter__(self):
        return iter(self._docs)


@pytest.fixture
def users_col(monkeypatch):
    fake = FakeCollection()
    monkeypatch.setattr(app_module, "users", fake)
    return fake


@pytest.fixture
def client(users_col):
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as test_client:
        yield test_client


# --- password strength rules (pure function) --------------------------------

def test_evaluate_password_rejects_123():
    result = evaluate_password("123")
    assert result["acceptable"] is False
    assert "at least 8 characters" in result["unmet"]


def test_evaluate_password_accepts_strong():
    result = evaluate_password("Str0ng!pass")
    assert result["acceptable"] is True
    assert result["unmet"] == []


# --- registration enforces strength server-side -----------------------------

def test_create_user_rejects_weak_password(client, users_col):
    resp = client.post(
        "/users", data={"email": "weak@example.com", "password": "123"}
    )
    assert resp.status_code == 302
    assert "/users/new" in resp.headers["Location"]
    # A weak password must never reach the database.
    assert users_col.find_one({"email": "weak@example.com"}) is None


def test_create_user_accepts_strong_password(client, users_col):
    resp = client.post(
        "/users",
        data={"email": "good@example.com", "password": "Str0ng!pass"},
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    saved = users_col.find_one({"email": "good@example.com"})
    assert saved is not None
    # Stored as a hash, never the plain password.
    assert "password_hash" in saved
    assert saved["password_hash"] != "Str0ng!pass"


# --- account page privacy ---------------------------------------------------

def test_account_page_requires_login(client):
    resp = client.get("/users")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_account_page_shows_only_own_email(client, users_col):
    users_col.insert_one(
        {"email": "lola@example.com", "password_hash": generate_password_hash("x")}
    )
    users_col.insert_one(
        {"email": "lola1@example.com", "password_hash": generate_password_hash("y")}
    )
    with client.session_transaction() as sess:
        sess["user_email"] = "lola@example.com"

    resp = client.get("/users")
    body = resp.get_data(as_text=True)

    assert "lola@example.com" in body  # the signed-in user's own email
    assert "lola1@example.com" not in body  # another user's email must not leak
