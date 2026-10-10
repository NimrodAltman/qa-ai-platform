"""Tests for password hashing and default-admin seeding."""

import pytest

from qa_agents.web import auth, store


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "runs.db")


def test_session_secret_uses_the_configured_value(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "configured-secret")
    assert auth.session_secret() == "configured-secret"


def test_session_secret_is_random_when_unset(monkeypatch):
    """No constant fallback: a secret committed to a public repo would let
    anyone forge a session cookie for any user."""
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    first = auth.session_secret()
    second = auth.session_secret()
    assert first != second
    assert len(first) >= 32


def test_hash_and_verify_round_trip():
    password_hash, salt = auth.hash_password("correct horse battery staple")
    assert auth.verify_password("correct horse battery staple", password_hash, salt)


def test_verify_rejects_wrong_password():
    password_hash, salt = auth.hash_password("right-password")
    assert not auth.verify_password("wrong-password", password_hash, salt)


def test_same_password_gets_different_salts():
    hash1, salt1 = auth.hash_password("same-password")
    hash2, salt2 = auth.hash_password("same-password")
    assert salt1 != salt2
    assert hash1 != hash2


def test_ensure_default_admin_seeds_exactly_one_admin():
    auth.ensure_default_admin()
    users = store.list_users()
    assert len(users) == 1
    assert users[0]["username"] == auth.DEFAULT_ADMIN_USERNAME
    assert users[0]["role"] == "admin"


def test_seeded_admin_password_is_random_not_a_published_default():
    """A known seeded credential takes over any exposed instance, so the
    first-run password must be random and returned for one-time display."""
    password = auth.ensure_default_admin()
    assert password is not None
    assert len(password) >= 12

    user = store.get_user_by_username(auth.DEFAULT_ADMIN_USERNAME)
    assert auth.verify_password(password, user["password_hash"], user["salt"])
    assert not auth.verify_password("admin", user["password_hash"], user["salt"])


def test_seeded_admin_password_differs_between_installs(tmp_path, monkeypatch):
    first = auth.ensure_default_admin()
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "second.db")
    second = auth.ensure_default_admin()
    assert first != second


def test_ensure_default_admin_is_idempotent():
    auth.ensure_default_admin()
    assert auth.ensure_default_admin() is None  # no new password on re-run
    assert store.user_count() == 1


def test_ensure_default_admin_skipped_once_a_user_exists():
    password_hash, salt = auth.hash_password("x")
    store.create_user("someone", password_hash, salt, "user")
    auth.ensure_default_admin()
    assert store.user_count() == 1  # did not add the default admin on top
