"""Tests for auth, password strength, and account privacy.

No real MongoDB is used: each test swaps the module-level ``users``
collection for an in-memory ``FakeCollection`` via monkeypatch.
"""

import pytest
from werkzeug.security import generate_password_hash

import app as app_module
from password_strength import evaluate_password


class FakeCollection:
    """In-memory stand-in for the pymongo operations the routes use."""

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


def test_evaluate_password_rejects_123():
    result = evaluate_password("123")
    assert result["acceptable"] is False
    assert "at least 8 characters" in result["unmet"]


def test_evaluate_password_accepts_strong():
    result = evaluate_password("Str0ng!pass")
    assert result["acceptable"] is True
    assert result["unmet"] == []


def test_create_user_rejects_weak_password(client, users_col):
    """A weak password must never reach the database."""
    resp = client.post(
        "/users", data={"email": "weak@example.com", "password": "123"}
    )
    assert resp.status_code == 302
    assert "/users/new" in resp.headers["Location"]
    assert users_col.find_one({"email": "weak@example.com"}) is None


def test_create_user_accepts_strong_password(client, users_col):
    """A strong password is accepted and stored only as a hash."""
    resp = client.post(
        "/users",
        data={"email": "good@example.com", "password": "Str0ng!pass"},
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    saved = users_col.find_one({"email": "good@example.com"})
    assert saved is not None
    assert "password_hash" in saved
    assert saved["password_hash"] != "Str0ng!pass"


def test_account_page_requires_login(client):
    resp = client.get("/users")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_account_page_shows_only_own_email(client, users_col):
    """The account page must never leak other users' emails."""
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

    assert "You are signed in as:" in body
    assert "lola@example.com" in body
    assert "lola1@example.com" not in body


def test_deploy_banner_hidden_when_not_on_render(client, monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    resp = client.get("/login")
    assert "Render.com" not in resp.get_data(as_text=True)


def test_deploy_banner_shown_on_render(client, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    resp = client.get("/login")
    assert "Render.com" in resp.get_data(as_text=True)
