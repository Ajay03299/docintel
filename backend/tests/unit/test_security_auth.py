import pytest
from fastapi import HTTPException

from app.core import security


def test_auth_disabled_when_no_keys(monkeypatch):
    monkeypatch.setattr(security, "_valid_keys", lambda: set())
    assert security.require_api_key(x_api_key=None) == "anonymous"


def test_missing_key_rejected_when_auth_on(monkeypatch):
    monkeypatch.setattr(security, "_valid_keys", lambda: {"secret1"})
    with pytest.raises(HTTPException) as exc:
        security.require_api_key(x_api_key=None)
    assert exc.value.status_code == 401


def test_wrong_key_rejected(monkeypatch):
    monkeypatch.setattr(security, "_valid_keys", lambda: {"secret1"})
    with pytest.raises(HTTPException) as exc:
        security.require_api_key(x_api_key="wrong")
    assert exc.value.status_code == 403


def test_correct_key_accepted(monkeypatch):
    monkeypatch.setattr(security, "_valid_keys", lambda: {"secret1"})
    assert security.require_api_key(x_api_key="secret1") == "secret1"
