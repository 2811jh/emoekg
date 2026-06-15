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
