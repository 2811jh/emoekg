"""Credential acquisition for emoekg — QR-code login + local cache.

This module is the single source of B站 login credentials. Resolution order
(see resolve_credential): local cache → BILI_SESSDATA env → QR-code login →
None (caller falls back to the guest realtime pool).

Secrets live only in ``~/.emoekg/credential.json`` (run-time dir, git-ignored)
and are never logged. asyncio coroutines from bilibili-api are bridged to the
synchronous CLI via the same one-shot ``asyncio.run`` used elsewhere.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

__all__ = [
    "load_cached_credential",
    "save_credential",
    "clear_cache",
    "qrcode_login",
    "resolve_credential",
]

# Cached SESSDATA older than this is treated as expired → re-login.
_MAX_AGE_DAYS = 25


def _cache_path() -> Path:
    """Return ~/.emoekg/credential.json, creating the parent dir if needed."""
    d = Path.home() / ".emoekg"
    d.mkdir(parents=True, exist_ok=True)
    return d / "credential.json"


def _make_credential(sessdata, bili_jct, buvid3, dedeuserid):
    """Build a bilibili_api Credential. Deferred import keeps tests light."""
    from bilibili_api import Credential

    return Credential(
        sessdata=sessdata or None,
        bili_jct=bili_jct or None,
        buvid3=buvid3 or None,
        dedeuserid=dedeuserid or None,
    )


def load_cached_credential() -> Any | None:
    """Return a Credential from the cache, or None if absent/expired/invalid."""
    path = _cache_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    sessdata = (data.get("sessdata") or "").strip()
    if not sessdata:
        return None
    saved_at = data.get("saved_at", 0)
    try:
        if time.time() - float(saved_at) > _MAX_AGE_DAYS * 86400:
            return None
    except (TypeError, ValueError):
        return None
    return _make_credential(
        sessdata, data.get("bili_jct"), data.get("buvid3"), data.get("dedeuserid")
    )


def save_credential(cred: Any) -> None:
    """Persist a Credential to the cache with a save timestamp."""
    path = _cache_path()
    payload = {
        "sessdata": getattr(cred, "sessdata", "") or "",
        "bili_jct": getattr(cred, "bili_jct", "") or "",
        "buvid3": getattr(cred, "buvid3", "") or "",
        "dedeuserid": getattr(cred, "dedeuserid", "") or "",
        "saved_at": time.time(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    # Best-effort tighten perms; harmless/no-op on platforms that ignore it.
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def clear_cache() -> None:
    """Delete the cached credential file. No error if it doesn't exist."""
    try:
        _cache_path().unlink()
    except FileNotFoundError:
        pass


# --- QR-code login -------------------------------------------------------
# These two indirections exist purely so unit tests can monkeypatch the
# upstream login state machine without touching the network.

def _make_qrcode_login():
    from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginChannel

    return QrCodeLogin(platform=QrCodeLoginChannel.WEB)


def _qr_events():
    from bilibili_api.login_v2 import QrCodeLoginEvents

    return QrCodeLoginEvents


# Tests replace this symbol with a fake enum; production reads the real one
# lazily via _qr_events(). Keeping a module attribute makes patching trivial.
_QrEvents = None


def _run(coro):
    """Bridge an async coroutine to sync context (one-shot event loop)."""
    return asyncio.run(coro)


def qrcode_login(timeout: int = 120) -> Any | None:
    """Drive QR-code login. Print an ASCII QR; poll until DONE/TIMEOUT.

    Returns a Credential on success (also written to cache), else None.
    Blocks up to ``timeout`` seconds. Never raises on a failed/expired login.
    """
    events = _QrEvents or _qr_events()
    login = _make_qrcode_login()
    try:
        _run(login.generate_qrcode())
    except Exception:  # noqa: BLE001 — network/login failures degrade to None
        return None

    print(login.get_qrcode_terminal())
    print("[emoekg] 请用 Bilibili App 扫描上方二维码登录（约 2 分钟内有效）…")

    notified = False
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            state = _run(login.check_state())
        except Exception:  # noqa: BLE001
            return None
        if state == events.DONE:
            cred = login.get_credential()
            save_credential(cred)
            print("[emoekg] ✓ 登录成功，凭证已缓存，后续无需再扫。")
            return cred
        if state == events.TIMEOUT:
            print("[emoekg] 二维码已过期，请重试。")
            return None
        if state in (events.SCAN, events.CONF) and not notified:
            print("[emoekg] 已检测到扫描，请在手机上确认…")
            notified = True
        time.sleep(2)
    print("[emoekg] 登录超时，本次将使用游客弹幕池。")
    return None


def _env_credential() -> Any | None:
    """Build a Credential from BILI_* env vars, or None if BILI_SESSDATA unset."""
    sessdata = os.environ.get("BILI_SESSDATA", "").strip()
    if not sessdata:
        return None
    return _make_credential(
        sessdata,
        os.environ.get("BILI_BILI_JCT", "").strip(),
        os.environ.get("BILI_BUVID3", "").strip(),
        os.environ.get("BILI_DEDEUSERID", "").strip(),
    )


def resolve_credential(allow_login: bool = True) -> Any | None:
    """Resolve a Credential: cache → env → QR login → None.

    A credential found via env is also written to cache so subsequent runs
    skip straight to layer 1. When allow_login is False (CI / unattended),
    the QR step is skipped and we fall through to None (guest pool).
    """
    cred = load_cached_credential()
    if cred is not None:
        return cred

    cred = _env_credential()
    if cred is not None:
        save_credential(cred)
        return cred

    if allow_login:
        return qrcode_login()

    return None
