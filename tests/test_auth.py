import json
import time
import importlib

import pytest


@pytest.fixture
def auth(tmp_path, monkeypatch):
    """Import auth with HOME redirected so the cache lives under tmp_path."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))   # Windows home
    monkeypatch.setenv("HOME", str(tmp_path))          # POSIX home
    import emoekg._lib.auth as a
    importlib.reload(a)
    return a


def test_cache_path_under_home(auth, tmp_path):
    p = auth._cache_path()
    assert p.parent.name == ".emoekg"
    assert p.name == "credential.json"
    assert p.parent.exists()  # directory auto-created


def test_save_then_load_roundtrip(auth):
    class FakeCred:
        sessdata = "S"; bili_jct = "J"; buvid3 = "B"; dedeuserid = "U"
    auth.save_credential(FakeCred())
    cred = auth.load_cached_credential()
    assert cred is not None
    assert cred.sessdata == "S"
    assert cred.bili_jct == "J"


def test_load_returns_none_when_missing(auth):
    assert auth.load_cached_credential() is None


def test_load_returns_none_when_expired(auth):
    p = auth._cache_path()
    old = time.time() - (auth._MAX_AGE_DAYS + 1) * 86400
    p.write_text(json.dumps({"sessdata": "S", "saved_at": old}), encoding="utf-8")
    assert auth.load_cached_credential() is None


def test_load_returns_none_on_bad_json(auth):
    auth._cache_path().write_text("{not json", encoding="utf-8")
    assert auth.load_cached_credential() is None


def test_load_returns_none_when_sessdata_missing(auth):
    p = auth._cache_path()
    p.write_text(json.dumps({"saved_at": time.time()}), encoding="utf-8")
    assert auth.load_cached_credential() is None


def test_clear_cache_removes_file(auth):
    class FakeCred:
        sessdata = "S"; bili_jct = "J"; buvid3 = "B"; dedeuserid = "U"
    auth.save_credential(FakeCred())
    assert auth._cache_path().exists()
    auth.clear_cache()
    assert not auth._cache_path().exists()
    auth.clear_cache()  # idempotent — no error on missing


def _install_fake_qr(auth, monkeypatch, states):
    """Inject a fake QrCodeLogin whose check_state yields `states` in order."""
    class FakeEvents:
        SCAN = "SCAN"; CONF = "CONF"; DONE = "DONE"; TIMEOUT = "TIMEOUT"

    class FakeCred:
        sessdata = "S"; bili_jct = "J"; buvid3 = "B"; dedeuserid = "U"

    seq = list(states)

    class FakeLogin:
        async def generate_qrcode(self):
            return None
        def get_qrcode_terminal(self):
            return "[QR-ASCII]"
        async def check_state(self):
            return seq.pop(0)
        def get_credential(self):
            return FakeCred()

    monkeypatch.setattr(auth, "_make_qrcode_login", lambda: FakeLogin())
    monkeypatch.setattr(auth, "_QrEvents", FakeEvents)
    monkeypatch.setattr(auth.time, "sleep", lambda s: None)
    monkeypatch.setattr(auth, "_run", _sync_run)


def _sync_run(coro):
    import asyncio as _a
    loop = _a.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_qrcode_login_done_saves_and_returns(auth, monkeypatch):
    _install_fake_qr(auth, monkeypatch, ["SCAN", "CONF", "DONE"])
    cred = auth.qrcode_login(timeout=10)
    assert cred is not None
    assert cred.sessdata == "S"
    assert auth.load_cached_credential() is not None


def test_qrcode_login_timeout_returns_none(auth, monkeypatch):
    _install_fake_qr(auth, monkeypatch, ["SCAN", "TIMEOUT"])
    cred = auth.qrcode_login(timeout=10)
    assert cred is None
