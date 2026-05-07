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
import time
from typing import Any

__all__ = ["fetch_video_meta", "fetch_all_danmakus"]


# One Protobuf segment on Bilibili covers 6 minutes of playback.
_SEGMENT_SEC = 360

# Retry backoff base: sleep(1.5 ** attempt) before retry #attempt.
_BACKOFF_BASE = 1.5


# ---------------------------------------------------------------------------
# Factory hook (patched by tests) + async→sync bridge
# ---------------------------------------------------------------------------


def _get_video(bvid: str) -> Any:
    """Return a live :class:`bilibili_api.video.Video` handle.

    Import is deferred to call-time so that unit tests which monkey-patch this
    symbol don't have to install ``bilibili-api-python`` at all.
    """
    from bilibili_api import video  # local import: optional at test time

    return video.Video(bvid=bvid)


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
    """Flatten an upstream protobuf danmaku into our schema.

    Field map:
      * ``progress`` (ms int)  -> ``time`` (float seconds, 3-decimal round)
      * ``content``            -> ``text``
      * ``mode``               -> ``mode``
      * ``color``              -> ``color`` (int)
      * ``fontsize``           -> ``fontsize`` (int)
      * ``midHash``            -> ``user_hash`` (opaque sender id)
    """
    return {
        "time": round(dm.progress / 1000.0, 3),
        "text": dm.content,
        "mode": dm.mode,
        "color": int(dm.color),
        "fontsize": int(dm.fontsize),
        "user_hash": dm.midHash,
    }


def fetch_all_danmakus(
    bvid: str,
    duration_sec: int,
    retries: int = 3,
) -> list[dict]:
    """Fetch all historical danmakus via the Protobuf segmented API.

    Bilibili serves danmakus in 6-minute Protobuf segments. We walk
    ``page_index = 0 .. ceil(duration / 360)``; out-of-range pages silently
    return ``[]`` in the upstream library, so off-by-one is harmless.

    Args:
        bvid: Canonical BV id.
        duration_sec: Video duration in seconds. ``0`` short-circuits to
            an empty list *without* touching the network.
        retries: Per-page retry budget. If any page still fails after all
            retries, the *whole* call raises — we prefer failing loudly over
            silently producing a partial timeline.

    Returns:
        Deduped list of normalized danmaku dicts. Dedup key is
        ``(time, text, user_hash)``.
    """
    _validate_bvid(bvid)
    if duration_sec < 0:
        raise ValueError(f"duration_sec must be >= 0, got {duration_sec}")
    if duration_sec == 0:
        return []

    v = _get_video(bvid)
    # +1 page for the tail segment, +1 again as defensive overshoot (upstream
    # returns [] out of range, so this is free insurance).
    num_pages = (duration_sec // _SEGMENT_SEC) + 1

    all_dms: list[dict] = []
    for page in range(num_pages):
        last_exc: BaseException | None = None
        fetched = False
        for attempt in range(retries):
            try:
                raw = _run(v.get_danmakus(page_index=page))
                for dm in raw:
                    all_dms.append(_normalize_danmaku(dm))
                fetched = True
                break
            except Exception as e:  # noqa: BLE001
                last_exc = e
                if attempt < retries - 1:
                    time.sleep(_BACKOFF_BASE ** attempt)
        if not fetched:
            raise RuntimeError(
                f"fetch_all_danmakus({bvid!r}) page={page} "
                f"failed after {retries} attempts"
            ) from last_exc

    # Dedup exact (time, text, user_hash) triples. A user re-sending the same
    # danmaku across segments shows up as one logical event in the ECG.
    seen: set[tuple] = set()
    unique: list[dict] = []
    for d in all_dms:
        key = (d["time"], d["text"], d["user_hash"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(d)
    return unique
