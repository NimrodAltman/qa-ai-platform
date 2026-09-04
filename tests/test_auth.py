"""Tests for password hashing and default-admin seeding."""

import pytest

from qa_agents.web import auth, store


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "runs.db")


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


def test_ensure_default_admin_is_idempotent():
    auth.ensure_default_admin()
    auth.ensure_default_admin()
    assert store.user_count() == 1


def test_ensure_default_admin_skipped_once_a_user_exists():
    password_hash, salt = auth.hash_password("x")
    store.create_user("someone", password_hash, salt, "user")
    auth.ensure_default_admin()
    assert store.user_count() == 1  # did not add the default admin on top
