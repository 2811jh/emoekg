"""Thin sync wrapper over ``bilibili-api-python``.

This module is the **only** place in emoekg that talks to Bilibili. The rest
of the pipeline consumes our normalized dicts, not the upstream library's
protobuf-flavoured objects, so the rest of the code stays library-agnostic.

Two public entry points:

* :func:`fetch_video_meta` — returns ``{bvid, title, up, duration_sec,
  view_count, cid}``.
* :func:`fetch_all_danmakus` — walks 6-minute Protobuf segments until
  exhausted, returns ``list[{time, text, mode, color, fontsize, user_hash}]``
  with exact duplicates removed.

Both wrap the upstream library's coroutines in ``asyncio.run``. Both retry
transient failures with exponential backoff. The ``_get_video`` factory is
exposed as a private hook purely so tests can patch it out — no real
network is needed for unit tests.
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import date, datetime, timedelta
from typing import Any

__all__ = ["fetch_video_meta", "fetch_all_danmakus"]


# One Protobuf segment on Bilibili covers 6 minutes of playback.
_SEGMENT_SEC = 360

# Retry backoff base: sleep(1.5 ** attempt) before retry #attempt.
_BACKOFF_BASE = 1.5


# ---------------------------------------------------------------------------
# Credential — read B站 login cookie from environment (never hard-coded)
# ---------------------------------------------------------------------------


def _build_credential(allow_login: bool = True) -> Any | None:
    """Resolve a B站 Credential via emoekg._lib.auth.

    Delegates to the 4-layer resolver (cache → BILI_SESSDATA env → QR-code
    login → None). Returns None to signal the caller to use the guest pool.
    """
    from emoekg._lib.auth import resolve_credential

    return resolve_credential(allow_login=allow_login)


# ---------------------------------------------------------------------------
# Factory hook (patched by tests) + async→sync bridge
# ---------------------------------------------------------------------------


def _get_video(bvid: str, credential: Any | None = None) -> Any:
    """Return a live :class:`bilibili_api.video.Video` handle.

    Import is deferred to call-time so that unit tests which monkey-patch this
    symbol don't have to install ``bilibili-api-python`` at all.
    """
    from bilibili_api import video  # local import: optional at test time

    return video.Video(bvid=bvid, credential=credential)


def _run(coro):
    """Run ``coro`` in a fresh event loop from sync context.

    emoekg's CLI is synchronous, so we never have a pre-existing running loop
    to worry about. Keep this simple: one ``asyncio.run`` per call.
    """
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def _validate_bvid(bvid: str) -> None:
    if not isinstance(bvid, str):
        raise TypeError(f"bvid must be str, got {type(bvid).__name__}")
    if not bvid.strip():
        raise ValueError("bvid must not be empty")


# ---------------------------------------------------------------------------
# fetch_video_meta
# ---------------------------------------------------------------------------


def fetch_video_meta(bvid: str, retries: int = 3) -> dict:
    """Fetch and normalize a Bilibili video's metadata.

    Args:
        bvid: Canonical BV id (see :mod:`emoekg._lib.bv_parser`).
        retries: Total attempts on transient failures. Exponential backoff
            (1.0s, 1.5s, 2.25s, ...). Defaults to 3.

    Returns:
        ``{bvid, title, up, duration_sec, view_count, cid}``. Missing optional
        fields in the upstream payload fall back to sensible defaults
        (``""`` or ``0``) rather than raising.

    Raises:
        TypeError: if ``bvid`` is not a string.
        ValueError: if ``bvid`` is empty.
        RuntimeError: if all retry attempts fail; the original exception is
            chained via ``__cause__``.
    """
    _validate_bvid(bvid)

    last_exc: BaseException | None = None
    for attempt in range(retries):
        try:
            v = _get_video(bvid)
            info = _run(v.get_info())
            return {
                "bvid": bvid,
                "title": info.get("title", ""),
                "up": info.get("owner", {}).get("name", ""),
                "duration_sec": int(info.get("duration", 0)),
                "view_count": int(info.get("stat", {}).get("view", 0)),
                "cid": int(info.get("cid", 0)),
                "pubdate": int(info.get("pubdate", 0)),
            }
        except Exception as e:  # noqa: BLE001 — upstream raises a wide variety
            last_exc = e
            if attempt < retries - 1:
                time.sleep(_BACKOFF_BASE ** attempt)

    raise RuntimeError(
        f"fetch_video_meta({bvid!r}) failed after {retries} attempts"
    ) from last_exc


# ---------------------------------------------------------------------------
# fetch_all_danmakus
# ---------------------------------------------------------------------------


def _normalize_danmaku(dm: Any) -> dict:
    """Flatten an upstream :class:`bilibili_api.utils.danmaku.Danmaku` into our schema.

    The upstream class currently exposes (observed 2026-05 from
    ``bilibili-api-python`` 16.x)::

        dm_time    float seconds  → time
        text       str            → text
        mode       int            → mode
        color      int            → color
        font_size  int            → fontsize
        crc32_id   str            → user_hash (opaque sender bucket)

    A few field names used to differ (``progress`` ms int, ``content``,
    ``fontsize``, ``midHash``). For compatibility with older/alternate shapes
    — and also to let our tests feed in a lightweight :class:`SimpleNamespace`
    faithfully — we fall back to ``getattr`` lookups.
    """
    # Time: prefer `dm_time` (float seconds). Fall back to `progress` (ms int).
    if hasattr(dm, "dm_time"):
        time_sec = float(dm.dm_time)
    elif hasattr(dm, "progress"):
        time_sec = dm.progress / 1000.0
    else:
        raise AttributeError(
            f"Danmaku object has neither 'dm_time' nor 'progress': {type(dm).__name__}"
        )

    text = getattr(dm, "text", None) or getattr(dm, "content", "")
    fontsize = getattr(dm, "font_size", None)
    if fontsize is None:
        fontsize = getattr(dm, "fontsize", 25)
    user_hash = (
        getattr(dm, "crc32_id", None)
        or getattr(dm, "midHash", None)
        or getattr(dm, "crack_uid", "")
    )

    return {
        "time": round(time_sec, 3),
        "text": text,
        "mode": int(getattr(dm, "mode", 1)),
        "color": _coerce_color(getattr(dm, "color", 0xFFFFFF)),
        "fontsize": int(fontsize),
        "user_hash": str(user_hash),
    }


def _coerce_color(value: Any) -> int:
    """Normalize bilibili-api-python's ``color`` field to a plain int.

    The upstream class sometimes returns a bare int (decimal RGB like
    ``16777215``), sometimes a zero-padded hex string (``"e70012"``). Both
    represent the same thing; we want a canonical ``int`` so the front-end
    can render it uniformly.
    """
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return 0xFFFFFF
    # Decimal path first (covers the common case without touching exceptions).
    if s.isdigit():
        return int(s)
    # Fall back to hex; strip optional "0x"/"#" prefixes.
    if s.startswith("0x") or s.startswith("0X"):
        s = s[2:]
    elif s.startswith("#"):
        s = s[1:]
    try:
        return int(s, 16)
    except ValueError:
        return 0xFFFFFF


def _dedup(dms: list[dict]) -> list[dict]:
    """Dedup exact ``(time, text, user_hash)`` triples, preserving order.

    The realtime pool shouldn't return duplicates across protobuf segments,
    but history snapshots taken on consecutive days overlap heavily — the same
    danmaku appears in every day's snapshot from its post date onward. This
    collapses them to one logical event.
    """
    seen: set[tuple] = set()
    unique: list[dict] = []
    for d in dms:
        key = (d["time"], d["text"], d["user_hash"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(d)
    return unique


def _fetch_one_day(v: Any, day: date, retries: int) -> list:
    """Fetch the history danmaku snapshot for a single ``day`` with retries.

    Returns the raw upstream list. Re-raises the last exception if every
    attempt fails — the caller decides whether one bad day is fatal.
    """
    last_exc: BaseException | None = None
    for attempt in range(retries):
        try:
            return _run(v.get_danmakus(page_index=0, date=day))
        except Exception as e:  # noqa: BLE001
            last_exc = e
            if attempt < retries - 1:
                time.sleep(_BACKOFF_BASE ** attempt)
    raise RuntimeError(f"history fetch failed for {day.isoformat()}") from last_exc


def _history_dates(v: Any, start: date, end: date, retries: int) -> list[date]:
    """List every day in ``[start, end]`` that actually has a danmaku snapshot.

    Walks month by month via ``get_history_danmaku_index`` (which returns the
    list of ``YYYY-MM-DD`` strings that have danmakus for the queried month),
    then keeps only those inside the requested window. Months that fail are
    skipped rather than aborting the whole walk.
    """
    days: list[date] = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        try:
            idx = _run(v.get_history_danmaku_index(date=cursor))
        except Exception:  # noqa: BLE001 — a missing month must not kill the walk
            idx = None
        for s in idx or []:
            try:
                d = datetime.strptime(s, "%Y-%m-%d").date()
            except ValueError:
                continue
            if start <= d <= end:
                days.append(d)
        # advance to first day of next month
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return sorted(set(days))


def _fetch_realtime(v: Any, num_segments: int, retries: int) -> list[dict]:
    """Fetch the realtime danmaku pool (no login). Used as the fallback path."""
    last_exc: BaseException | None = None
    raw: list | None = None
    for attempt in range(retries):
        try:
            # page_index=0 targets the (typically only) 分 P. from_seg=0 + no
            # to_seg means "all protobuf segments". bilibili-api-python
            # concatenates them for us.
            raw = _run(v.get_danmakus(page_index=0, from_seg=0))
            break
        except Exception as e:  # noqa: BLE001
            last_exc = e
            if attempt < retries - 1:
                time.sleep(_BACKOFF_BASE ** attempt)

    if raw is None:
        raise RuntimeError(
            f"realtime danmaku fetch failed after {retries} attempts "
            f"(expected {num_segments} protobuf segments)"
        ) from last_exc

    return _dedup([_normalize_danmaku(dm) for dm in raw])


def fetch_all_danmakus(
    bvid: str,
    duration_sec: int,
    retries: int = 3,
    pubdate: int = 0,
    allow_login: bool = True,
) -> list[dict]:
    """Fetch danmakus, preferring the **full historical** archive when possible.

    Two modes, picked automatically:

    * **History mode** (when ``BILI_SESSDATA`` is set in the environment):
      walks every day from the video's post date to today via
      ``get_history_danmaku_index`` + per-day ``get_danmakus(date=...)``
      snapshots, then dedups across days. This recovers danmakus that have
      been pushed out of the realtime pool — i.e. the true full archive.
    * **Realtime mode** (no credential): a single ``get_danmakus`` call over
      all protobuf segments. This is the only option without a login cookie
      and returns just the current rolling pool.

    Args:
        bvid: Canonical BV id.
        duration_sec: Video duration in seconds. ``0`` short-circuits to an
            empty list *without* touching the network.
        retries: Per-request retry budget with exponential backoff.
        pubdate: Video publish time (unix seconds). Marks the start of the
            history walk; ``0`` falls back to a 1-year look-back window.

    Returns:
        Deduped list of normalized danmaku dicts. Dedup key is
        ``(time, text, user_hash)``.

    Raises:
        RuntimeError: if the realtime path fails every retry; the original
            exception is chained via ``__cause__``.
    """
    _validate_bvid(bvid)
    if duration_sec < 0:
        raise ValueError(f"duration_sec must be >= 0, got {duration_sec}")
    if duration_sec == 0:
        return []

    num_segments = (duration_sec + _SEGMENT_SEC - 1) // _SEGMENT_SEC
    credential = _build_credential(allow_login=allow_login)

    # No login → realtime pool only.
    if credential is None:
        print(
            "  [danmaku] BILI_SESSDATA not set → realtime pool only "
            "(set it to unlock full history)"
        )
        return _fetch_realtime(_get_video(bvid), num_segments, retries)

    # History mode: walk day by day from post date to today.
    v = _get_video(bvid, credential=credential)
    today = date.today()
    if pubdate > 0:
        start = datetime.fromtimestamp(pubdate).date()
    else:
        start = today - timedelta(days=365)

    days = _history_dates(v, start, today, retries)
    if not days:
        # Index empty/unavailable — degrade gracefully to the realtime pool.
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
        # Gentle pacing so we don't hammer the history endpoint.
        time.sleep(0.2)

    if not collected:
        print("  [danmaku] history returned nothing → falling back to realtime")
        return _fetch_realtime(v, num_segments, retries)

    if failed_days:
        print(f"  [danmaku] note: {failed_days} day(s) failed and were skipped")

    return _dedup(collected)
