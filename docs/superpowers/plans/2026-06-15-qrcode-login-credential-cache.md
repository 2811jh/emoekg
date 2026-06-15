# 扫码登录 + 凭证缓存 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户首次手机扫码即可解锁登录态弹幕，凭证本地缓存长期复用，之后零操作。

**Architecture:** 新增 `_lib/auth.py` 封装凭证的「缓存读写 + 扫码登录 + 四层回退解析」；`danmaku_client._build_credential` 改为委托 `auth.resolve_credential`；CLI 加 `--no-login` flag 与 `login` 子命令。全程同步接口（用已有 `_run` 桥接 async）。

**Tech Stack:** Python 3.14, `bilibili_api.login_v2.QrCodeLogin`（WEB 渠道，扫码登录），pytest。

参考 spec：`docs/superpowers/specs/2026-06-15-qrcode-login-credential-cache-design.md`

**已核实的上游 API 事实（写代码时据此）：**
- `QrCodeLogin(platform=QrCodeLoginChannel.WEB)`；`generate_qrcode()` 和 `check_state()` 都是 **async**；`get_qrcode_terminal() -> str`（同步）；`get_credential() -> Credential`（同步）。
- `QrCodeLoginEvents` 有成员：`SCAN` / `CONF` / `DONE` / `TIMEOUT`。
- `Credential` 暴露属性 `sessdata` / `bili_jct` / `buvid3` / `dedeuserid`。
- `danmaku_client._run(coro)` = `asyncio.run(coro)`，可复用为 async→sync 桥。
- 现 `_build_credential() -> Any|None` 读 4 个环境变量构造 `Credential`。
- `fetch_all_danmakus(bvid, duration_sec, retries=3, pubdate=0)`；其中调用 `_build_credential()`（无参）。
- `fetch_danmaku.run(url_or_bvid, working_dir, force=False)` 调 `fetch_all_danmakus(...)`。

---

### Task 1: `auth.py` — 缓存读写 + clear

**Files:**
- Create: `src/emoekg/_lib/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_auth.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_auth.py -v`
Expected: FAIL — `No module named 'emoekg._lib.auth'`。

- [ ] **Step 3: 实现 auth.py（本任务只到 clear_cache）**

创建 `src/emoekg/_lib/auth.py`：

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_auth.py -v`
Expected: PASS（7 个测试全过）。

- [ ] **Step 5: 提交**

```bash
git add src/emoekg/_lib/auth.py tests/test_auth.py
git commit -m "feat(auth): credential cache read/write/clear under ~/.emoekg"
```

---

### Task 2: `auth.py` — 扫码登录 `qrcode_login`

**Files:**
- Modify: `src/emoekg/_lib/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_auth.py`。用假的 `QrCodeLogin` 状态机注入，避免真实网络。关键：测试替换 `auth._make_qrcode_login` 工厂（Task 2 会引入）以返回假对象，并替换 `auth._run` 为直接执行协程的同步函数。

```python
def _install_fake_qr(auth, monkeypatch, states):
    """Inject a fake QrCodeLogin whose check_state yields `states` in order."""
    # Fake event enum with the 4 members the code compares against.
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
    # Make polling instant: no real sleeping, no real event loop needed.
    monkeypatch.setattr(auth.time, "sleep", lambda s: None)
    monkeypatch.setattr(auth, "_run", lambda coro: asyncio.get_event_loop().run_until_complete(coro)
                        if False else _sync_run(coro))


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
    # cache written
    assert auth.load_cached_credential() is not None


def test_qrcode_login_timeout_returns_none(auth, monkeypatch):
    _install_fake_qr(auth, monkeypatch, ["SCAN", "TIMEOUT"])
    cred = auth.qrcode_login(timeout=10)
    assert cred is None
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_auth.py::test_qrcode_login_done_saves_and_returns tests/test_auth.py::test_qrcode_login_timeout_returns_none -v`
Expected: FAIL — `auth` 无 `_make_qrcode_login` / `qrcode_login`。

- [ ] **Step 3: 实现 qrcode_login**

在 `auth.py` 顶部 `import` 区后加入工厂与事件钩子（便于测试注入），并实现 `qrcode_login`。把以下加到 `clear_cache` 之后：

```python
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
```

> 说明：测试通过 `monkeypatch.setattr(auth, "_make_qrcode_login", ...)`、`auth._QrEvents = FakeEvents`、`auth._run = _sync_run` 注入，不触网。生产路径 `_QrEvents is None` → 走 `_qr_events()` 取真枚举。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_auth.py -v`
Expected: PASS（含新增 2 个）。

- [ ] **Step 5: 提交**

```bash
git add src/emoekg/_lib/auth.py tests/test_auth.py
git commit -m "feat(auth): QR-code login via bilibili-api with ASCII terminal QR"
```

---

### Task 3: `auth.py` — 四层回退 `resolve_credential`

**Files:**
- Modify: `src/emoekg/_lib/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_auth.py`：

```python
def test_resolve_prefers_cache(auth, monkeypatch):
    class FakeCred:
        sessdata = "CACHE"; bili_jct = "J"; buvid3 = "B"; dedeuserid = "U"
    auth.save_credential(FakeCred())
    # env set too, but cache must win
    monkeypatch.setenv("BILI_SESSDATA", "ENV")
    monkeypatch.setattr(auth, "qrcode_login", lambda timeout=120: pytest.fail("should not login"))
    cred = auth.resolve_credential(allow_login=True)
    assert cred.sessdata == "CACHE"


def test_resolve_falls_back_to_env(auth, monkeypatch):
    auth.clear_cache()
    monkeypatch.setenv("BILI_SESSDATA", "ENV")
    monkeypatch.setenv("BILI_BILI_JCT", "JCT")
    called = {"login": False}
    monkeypatch.setattr(auth, "qrcode_login", lambda timeout=120: called.__setitem__("login", True))
    cred = auth.resolve_credential(allow_login=True)
    assert cred.sessdata == "ENV"
    assert called["login"] is False
    # env credential should also be cached for next time
    assert auth.load_cached_credential() is not None


def test_resolve_triggers_login_when_no_cache_no_env(auth, monkeypatch):
    auth.clear_cache()
    monkeypatch.delenv("BILI_SESSDATA", raising=False)

    class FakeCred:
        sessdata = "QR"; bili_jct = "J"; buvid3 = "B"; dedeuserid = "U"
    monkeypatch.setattr(auth, "qrcode_login", lambda timeout=120: FakeCred())
    cred = auth.resolve_credential(allow_login=True)
    assert cred.sessdata == "QR"


def test_resolve_no_login_returns_none(auth, monkeypatch):
    auth.clear_cache()
    monkeypatch.delenv("BILI_SESSDATA", raising=False)
    monkeypatch.setattr(auth, "qrcode_login", lambda timeout=120: pytest.fail("no_login must skip"))
    cred = auth.resolve_credential(allow_login=False)
    assert cred is None
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_auth.py -k resolve -v`
Expected: FAIL — `auth` 无 `resolve_credential`。

- [ ] **Step 3: 实现 resolve_credential + env helper**

在 `auth.py` 末尾追加：

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_auth.py -v`
Expected: PASS（全部）。

- [ ] **Step 5: 提交**

```bash
git add src/emoekg/_lib/auth.py tests/test_auth.py
git commit -m "feat(auth): resolve_credential 4-layer fallback (cache>env>QR>none)"
```

---

### Task 4: `danmaku_client` 委托 auth + `allow_login` 透传 + 失效兜底

**Files:**
- Modify: `src/emoekg/_lib/danmaku_client.py:43-70`（`_build_credential`）
- Modify: `src/emoekg/_lib/danmaku_client.py`（`fetch_all_danmakus` 签名 + 调用）
- Test: `tests/test_danmaku_client.py`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_danmaku_client.py`（文件已存在，沿用其 import 风格）：

```python
def test_build_credential_delegates_to_resolve(monkeypatch):
    import emoekg._lib.danmaku_client as dc

    sentinel = object()
    captured = {}
    def fake_resolve(allow_login=True):
        captured["allow_login"] = allow_login
        return sentinel
    monkeypatch.setattr("emoekg._lib.auth.resolve_credential", fake_resolve)

    out = dc._build_credential(allow_login=False)
    assert out is sentinel
    assert captured["allow_login"] is False
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_danmaku_client.py::test_build_credential_delegates_to_resolve -v`
Expected: FAIL — `_build_credential` 不接受 `allow_login` 且仍读 env。

- [ ] **Step 3: 改 `_build_credential` 委托 auth**

把 `danmaku_client.py` 的 `_build_credential`（43-70 行整段）替换为：

```python
def _build_credential(allow_login: bool = True) -> Any | None:
    """Resolve a B站 Credential via emoekg._lib.auth.

    Delegates to the 4-layer resolver (cache → BILI_SESSDATA env → QR-code
    login → None). Returns None to signal the caller to use the guest pool.
    """
    from emoekg._lib.auth import resolve_credential

    return resolve_credential(allow_login=allow_login)
```

（保留文件顶部的 `import os`；它仍被其它代码使用。若 lint 报未使用再删。）

- [ ] **Step 4: `fetch_all_danmakus` 加 `allow_login` 透传**

找到 `def fetch_all_danmakus(bvid, duration_sec, retries=3, pubdate=0):`，签名改为：

```python
def fetch_all_danmakus(
    bvid: str,
    duration_sec: int,
    retries: int = 3,
    pubdate: int = 0,
    allow_login: bool = True,
) -> list[dict]:
```

并把函数体里 `credential = _build_credential()` 改为：

```python
    credential = _build_credential(allow_login=allow_login)
```

- [ ] **Step 5: 运行确认通过 + 全量回归**

Run: `python -m pytest tests/test_danmaku_client.py -v`
Expected: PASS。
Run: `python -m pytest -q`
Expected: 全绿（auth 测试 + 既有）。

- [ ] **Step 6: 提交**

```bash
git add src/emoekg/_lib/danmaku_client.py tests/test_danmaku_client.py
git commit -m "feat(danmaku): delegate credential to auth + thread allow_login"
```

---

### Task 5: 运行期失效兜底（鉴权错误清缓存 + 回退）

**Files:**
- Modify: `src/emoekg/_lib/danmaku_client.py`（历史模式拉取处）
- Test: `tests/test_danmaku_client.py`

- [ ] **Step 1: 阅读现有历史模式代码**

`fetch_all_danmakus` 中，`credential is not None` 后进入历史模式：调用 `_history_dates(...)` 和 `_fetch_one_day(...)`。若这些上游调用抛鉴权错误，应清缓存并回退 `_fetch_realtime`。

- [ ] **Step 2: 写失败测试**

追加到 `tests/test_danmaku_client.py`：

```python
def test_history_auth_error_clears_cache_and_falls_back(monkeypatch):
    import emoekg._lib.danmaku_client as dc

    # A non-None credential to enter history mode.
    monkeypatch.setattr(dc, "_build_credential", lambda allow_login=True: object())

    cleared = {"called": False}
    monkeypatch.setattr("emoekg._lib.auth.clear_cache",
                        lambda: cleared.__setitem__("called", True))

    # history date walk raises an auth-like error
    def boom(*a, **k):
        raise RuntimeError("-101 账号未登录")
    monkeypatch.setattr(dc, "_history_dates", boom)

    # realtime fallback returns a sentinel list
    monkeypatch.setattr(dc, "_get_video", lambda bvid, credential=None: object())
    monkeypatch.setattr(dc, "_fetch_realtime",
                        lambda v, n, r: [{"time": 1.0, "text": "x", "user_hash": "h"}])

    out = dc.fetch_all_danmakus("BV1xx", 60, allow_login=True)
    assert cleared["called"] is True
    assert out == [{"time": 1.0, "text": "x", "user_hash": "h"}]
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_danmaku_client.py::test_history_auth_error_clears_cache_and_falls_back -v`
Expected: FAIL —目前历史路径异常不会清缓存、不回退。

- [ ] **Step 4: 包裹历史模式于 try/except**

在 `fetch_all_danmakus` 的历史模式分支（`credential is not None` 之后、`v = _get_video(...)` 起到 `return _dedup(collected)` 为止）外层包一层 try/except。最小改法：把历史逻辑整体放进 `try:`，`except Exception:` 时清缓存并回退实时池。示例结构（按现有变量名对齐）：

```python
    # History mode: walk day by day from post date to today.
    try:
        v = _get_video(bvid, credential=credential)
        today = date.today()
        if pubdate > 0:
            start = datetime.fromtimestamp(pubdate).date()
        else:
            start = today - timedelta(days=365)

        days = _history_dates(v, start, today, retries)
        if not days:
            print("  [danmaku] history index empty → falling back to realtime pool")
            return _fetch_realtime(v, num_segments, retries)

        print(f"  [danmaku] history mode: {len(days)} day-snapshots to fetch")
        collected: list[dict] = []
        failed_days = 0
        for i, day in enumerate(days, 1):
            try:
                raw = _fetch_one_day(v, day, retries)
            except RuntimeError:
                failed_days += 1
                continue
            collected.extend(_normalize_danmaku(dm) for dm in raw)
            if i % 10 == 0 or i == len(days):
                print(f"    …{i}/{len(days)} days, {len(collected):,} raw so far")
            time.sleep(0.2)

        if not collected:
            print("  [danmaku] history returned nothing → falling back to realtime")
            return _fetch_realtime(v, num_segments, retries)
        if failed_days:
            print(f"  [danmaku] note: {failed_days} day(s) failed and were skipped")
        return _dedup(collected)
    except Exception as e:  # noqa: BLE001 — auth/network failure → guest pool
        from emoekg._lib.auth import clear_cache
        print(f"  [danmaku] history mode failed ({e!r}) → clearing cached login, "
              "falling back to realtime pool")
        clear_cache()
        return _fetch_realtime(_get_video(bvid), num_segments, retries)
```

> 注意：保留分支内既有的「index empty / nothing → realtime」**正常回退**逻辑不变（它们是 return，不进 except）。只有真正抛异常才清缓存。`_history_dates` 内部已自吞单月异常；此处兜的是更上层的鉴权/网络异常。

- [ ] **Step 5: 运行确认通过 + 全量**

Run: `python -m pytest tests/test_danmaku_client.py -v`
Expected: PASS。
Run: `python -m pytest -q`
Expected: 全绿。

- [ ] **Step 6: 提交**

```bash
git add src/emoekg/_lib/danmaku_client.py tests/test_danmaku_client.py
git commit -m "feat(danmaku): clear cached login + guest fallback on history auth error"
```

---

### Task 6: CLI — `--no-login` flag + `login` 子命令

**Files:**
- Modify: `src/emoekg/cli.py`
- Modify: `src/emoekg/stages/fetch_danmaku.py`（`run` 透传 `allow_login`）
- Test: `tests/test_cli.py`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_cli.py`：

```python
def test_prepare_parses_no_login_flag():
    from emoekg.cli import build_parser
    ap = build_parser()
    args = ap.parse_args(["prepare", "BV1xx", "-o", "out", "--no-login"])
    assert args.no_login is True
    args2 = ap.parse_args(["prepare", "BV1xx", "-o", "out"])
    assert args2.no_login is False


def test_login_subcommand_invokes_qrcode_login(monkeypatch):
    from emoekg import cli

    called = {"login": False}
    monkeypatch.setattr("emoekg._lib.auth.qrcode_login",
                        lambda timeout=120: called.__setitem__("login", True) or object())
    rc = cli.main(["login"])
    assert rc == 0
    assert called["login"] is True
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_cli.py::test_prepare_parses_no_login_flag tests/test_cli.py::test_login_subcommand_invokes_qrcode_login -v`
Expected: FAIL — 无 `--no-login`，无 `login` 子命令。

- [ ] **Step 3: parser 加 `--no-login`（prepare + run）与 `login` 子命令**

在 `build_parser()` 里，`prepare` 与 `run` 两个 parser 各加：

```python
    ap_prep.add_argument("--no-login", action="store_true",
                         help="跳过扫码登录，仅用缓存/环境变量/游客池")
```
```python
    ap_run.add_argument("--no-login", action="store_true",
                        help="跳过扫码登录，仅用缓存/环境变量/游客池")
```

在 `sub.add_parser("run", ...)` 之后、`return ap` 之前加入 `login` 子命令：

```python
    # login
    sub.add_parser(
        "login",
        help="扫码登录并缓存凭证（一次扫码长期复用，解锁全量弹幕）",
    )
```

- [ ] **Step 4: `main()` 分发 login + 透传 no_login**

`main()` 的 try 块里，把 prepare / run 分发改为透传 `allow_login`，并加 login 分支：

```python
        if args.command == "prepare":
            return run_prepare(args.url, wd, force=args.force,
                               allow_login=not args.no_login)
        if args.command == "finalize":
            return run_finalize(wd, with_video=args.with_video, force=args.force)
        if args.command == "run":
            return run_oneshot(args.url, wd, with_video=args.with_video,
                               force=args.force, allow_login=not args.no_login)
        if args.command == "login":
            from emoekg._lib.auth import qrcode_login
            cred = qrcode_login()
            if cred is None:
                print("[emoekg] 登录未完成。", file=sys.stderr)
                return 1
            return 0
```

> 注意：`login` 子命令没有 `-o`，但 `main()` 顶部有 `wd = Path(args.output)`。需把该行移到只在需要的命令里取，或对 login 容错。最简单：在 `main()` 顶部改为 `wd = Path(args.output) if getattr(args, "output", None) else None`。

- [ ] **Step 5: `run_prepare` / `run_oneshot` 接受并透传 `allow_login`**

`run_prepare` 签名与体：

```python
def run_prepare(url: str, working_dir: Path, force: bool = False,
                allow_login: bool = True) -> int:
    """Execute S1 + S2, then hand off to the Agent."""
    working_dir = Path(working_dir)
    fetch_danmaku.run(url, working_dir, force=force, allow_login=allow_login)
    slice_chunks.run(working_dir, force=force)
    _print_hand_off(working_dir)
    return 0
```

`run_oneshot` 同理，签名加 `allow_login: bool = True`，把 `fetch_danmaku.run(url, working_dir, force=force)` 改为 `fetch_danmaku.run(url, working_dir, force=force, allow_login=allow_login)`。

- [ ] **Step 6: `fetch_danmaku.run` 透传到 `fetch_all_danmakus`**

`fetch_danmaku.py` 的 `run` 签名加参数：

```python
def run(url_or_bvid: str, working_dir: Path | str, force: bool = False,
        allow_login: bool = True) -> None:
```

把 `dms = fetch_all_danmakus(bvid, meta["duration_sec"], pubdate=meta.get("pubdate", 0))` 改为：

```python
    dms = fetch_all_danmakus(
        bvid, meta["duration_sec"], pubdate=meta.get("pubdate", 0),
        allow_login=allow_login,
    )
```

- [ ] **Step 7: 运行确认通过 + 全量**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS。
Run: `python -m pytest -q`
Expected: 全绿。

- [ ] **Step 8: 提交**

```bash
git add src/emoekg/cli.py src/emoekg/stages/fetch_danmaku.py tests/test_cli.py
git commit -m "feat(cli): --no-login flag + login subcommand, thread allow_login"
```

---

### Task 7: 文档更新（SKILL.md）

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: 替换「手动设 SESSDATA」叙述**

在 SKILL.md 中找到关于全量弹幕/SESSDATA 的说明（搜索 `SESSDATA` 或「全量」），替换/补充为扫码登录流程。加入一段：

```markdown
### 解锁全量弹幕（扫码登录，推荐）

游客只能拿到实时弹幕池（量少）。要拿登录态/历史全量弹幕，首次需登录一次：

- **自动**：直接跑 `emoekg prepare <url> -o <dir>`，若无有效凭证会自动在终端打印二维码，用 Bilibili App 扫码即可。凭证缓存在 `~/.emoekg/credential.json`，约 25 天内自动复用，期间无需再扫。
- **手动刷新**：`emoekg login` 单独扫码刷新缓存。
- **跳过登录**：`emoekg prepare <url> -o <dir> --no-login` 仅用缓存/环境变量/游客池（适合无人值守 / CI）。
- **环境变量（兼容旧用法）**：设 `BILI_SESSDATA` 仍然有效，且会被写入缓存供后续复用。

> 凭证仅存本地、不入库、不打印。过期或失效时会自动重新走扫码。
```

- [ ] **Step 2: 提交**

```bash
git add SKILL.md
git commit -m "docs(skill): document QR-code login + credential cache flow"
```

---

### Task 8: 端到端手动验收

**Files:** 无代码改动。

- [ ] **Step 1: 重新安装**

Run: `pip install -e "C:\Users\lijinghui03\.agents\skills\emoekg"`
Expected: Successfully installed emoekg。

- [ ] **Step 2: 清掉缓存与环境变量，验证扫码触发**

```bat
python -c "import emoekg._lib.auth as a; a.clear_cache(); print('cache cleared')"
set BILI_SESSDATA=
emoekg login
```
Expected: 终端打印 ASCII 二维码 + 提示；手机扫码确认后打印「✓ 登录成功，凭证已缓存」；`~/.emoekg/credential.json` 出现。

- [ ] **Step 3: 验证缓存复用（无需再扫）**

```bat
emoekg prepare BV1VUG16nEwX -o "%USERPROFILE%\Desktop\_qrtest" --force
```
Expected: 不再弹二维码；`danmakus: N total` 中 N 为登录态数量（明显多于游客池）。

- [ ] **Step 4: 验证 `--no-login`**

```bat
python -c "import emoekg._lib.auth as a; a.clear_cache()"
set BILI_SESSDATA=
emoekg prepare BV1VUG16nEwX -o "%USERPROFILE%\Desktop\_qrtest2" --force --no-login
```
Expected: 不弹二维码，直接走游客池（日志 `BILI_SESSDATA not set → realtime pool only` 或等价）。

- [ ] **Step 5: 清理测试目录**

```bat
rmdir /s /q "%USERPROFILE%\Desktop\_qrtest" "%USERPROFILE%\Desktop\_qrtest2"
```

- [ ] **Step 6: 推送**

```bash
cd /d "C:\Users\lijinghui03\.agents\skills\emoekg"
git push origin main
```

---

## Self-Review

**Spec coverage:**
- 四层回退 → Task 3（resolve_credential）✅
- `_lib/auth.py` 各函数（_cache_path/load/save/clear/qrcode_login/resolve）→ Task 1+2+3 ✅
- 扫码流程（WEB/terminal QR/轮询/DONE/TIMEOUT）→ Task 2 ✅
- 缓存格式 + 25天过期 → Task 1（`_MAX_AGE_DAYS`）✅
- 运行期失效兜底（清缓存+回退）→ Task 5 ✅
- CLI `--no-login` + `login` 子命令 → Task 6 ✅
- danmaku_client 委托 + allow_login 透传 → Task 4 ✅
- 向后兼容 BILI_SESSDATA → Task 3（_env_credential，且写入缓存）✅
- 文档 → Task 7 ✅
- 测试（auth/danmaku/cli）→ Task 1-6 各含 ✅

**Placeholder scan:** 无 TBD/TODO；所有步骤含完整代码或精确命令。Task 8 的 BV 号与路径为真实可用值。✅

**Type consistency:**
- `resolve_credential(allow_login=True)`、`qrcode_login(timeout=120)`、`_build_credential(allow_login=True)`、`fetch_all_danmakus(..., allow_login=True)`、`fetch_danmaku.run(..., allow_login=True)`、`run_prepare/run_oneshot(..., allow_login=True)` —— 全链路参数名统一为 `allow_login`。✅
- 缓存字段 `sessdata/bili_jct/buvid3/dedeuserid/saved_at` 在 save/load 两端一致。✅
- 测试注入点 `_make_qrcode_login` / `_QrEvents` / `_run` 与实现中定义一致。✅
