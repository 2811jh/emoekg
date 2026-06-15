"""Adaptive window sizing + danmaku slicing.

Two responsibilities:

* :func:`compute_window_size` — given a video's total duration, pick a
  "human-friendly" window length (5s, 10s, 15s, ...) so that the timeline
  ends up with roughly :data:`_TARGET_CHUNKS` data points. This keeps the
  ECG chart readable at any video length: short videos use fine windows,
  long compilations use coarse windows, capped at 3 minutes per chunk so
  that a single chunk's semantic summary stays meaningful.
* :func:`slice_by_window` — bucket a flat list of danmakus (each with a
  ``time`` field in seconds) into sequential time chunks. Boundary policy:
  ``[t, t+window)`` left-closed / right-open for all chunks *except the
  last*, whose right edge is closed (``[t, total_duration]``) so the last
  danmaku at the very end of the video isn't silently dropped — Bilibili's
  protobuf ``progress`` field can equal the video duration exactly.
"""
from __future__ import annotations

from typing import Iterable, Mapping

__all__ = ["compute_window_size", "slice_by_window"]


# Human-friendly window sizes (seconds). Ordered ascending. The snap rule is
# "smallest friendly window >= raw/target". Anything above the largest entry
# gets capped to that largest entry.
_FRIENDLY_WINDOWS: tuple[int, ...] = (5, 10, 15, 30, 45, 60, 90, 120, 180)

# We aim for roughly this many chunks on an "average" video. Short videos
# will have fewer (because window is clamped to 5s min) and >4.5h
# compilations will have more (because window is capped at 180s max).
_TARGET_CHUNKS: int = 90


def compute_window_size(duration_sec: int) -> int:
    """Pick a friendly window size (seconds) for a video of ``duration_sec``.

    The chosen window is the smallest value in :data:`_FRIENDLY_WINDOWS` that
    is ``>= duration_sec / 90``. Degenerate or negative durations return the
    minimum window (5s) so the caller doesn't have to special-case them.

    >>> compute_window_size(18 * 60)
    15
    >>> compute_window_size(3 * 3600)
    120
    >>> compute_window_size(0)
    5
    """
    if duration_sec <= 0:
        return _FRIENDLY_WINDOWS[0]

    raw = duration_sec / _TARGET_CHUNKS
    for w in _FRIENDLY_WINDOWS:
        if w >= raw:
            return w
    return _FRIENDLY_WINDOWS[-1]


def slice_by_window(
    danmakus: Iterable[Mapping],
    window_size: int,
    total_duration: int,
) -> list[dict]:
    """Bucket ``danmakus`` into sequential time chunks of ``window_size``.

    Each input item is expected to be a mapping with a ``time`` field
    (``float`` or ``int``, in seconds). Items with ``time < 0`` or
    ``time > total_duration`` are dropped defensively — corrupt upstream
    data must never raise.

    Boundary policy:

    * chunks 1 … n-1 cover ``[t, t+window)`` — left-closed, right-open.
    * chunk n (the last one) covers ``[t, total_duration]`` — *both* edges
      closed, so a danmaku at the very last frame (``time == duration``) is
      preserved.

    Returned chunks preserve the original danmaku objects (no copy). Inside
    each chunk the danmakus are sorted ascending by ``time`` regardless of
    input order.

    Args:
        danmakus: iterable of danmaku dicts with at least a ``time`` key.
        window_size: seconds per chunk. Must be > 0.
        total_duration: total video duration in seconds. ``0`` returns
            an empty chunk list.

    Returns:
        A list of ``{chunk_id, time_start, time_end, danmakus}`` dicts.
    """
    if window_size <= 0:
        raise ValueError(f"window_size must be > 0, got {window_size}")
    if total_duration < 0:
        raise ValueError(f"total_duration must be >= 0, got {total_duration}")
    if total_duration == 0:
        return []

    # Filter + sort once. Dropping out-of-range items here keeps the main
    # loop branch-free.
    clean = sorted(
        (d for d in danmakus if 0 <= d["time"] <= total_duration),
        key=lambda d: d["time"],
    )

    chunks: list[dict] = []
    idx = 0
    chunk_num = 1
    t = 0
    while t < total_duration:
        end = min(t + window_size, total_duration)
        is_final = end >= total_duration

        # Right-open for all but the final chunk; the final chunk closes the
        # right edge so `time == total_duration` isn't dropped.
        bucket: list[Mapping] = []
        while idx < len(clean):
            dm_time = clean[idx]["time"]
            in_chunk = (dm_time < end) or (is_final and dm_time == end)
            if not in_chunk:
                break
            bucket.append(clean[idx])
            idx += 1

        chunks.append(
            {
                "chunk_id": f"C{chunk_num:03d}",
                "time_start": t,
                "time_end": end,
                "danmakus": bucket,
            }
        )
        t = end
        chunk_num += 1

    return chunks
