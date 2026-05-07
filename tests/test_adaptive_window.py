"""Tests for emoekg._lib.adaptive_window.

Pinned down:
  - compute_window_size: friendly snapping + monotonicity + sane edge cases
    (zero, negative, cap at 180s for very long VODs).
  - slice_by_window:
      * [t, t+window) left-closed, right-open for all *except* the final chunk,
        which is [t, total_duration] (closed) so the last danmaku at the very
        end of the video isn't silently dropped.
      * handles unsorted input, stray danmakus past total_duration, and
        zero-length videos.
      * chunk_ids are C001, C002, ... zero-padded to 3 digits.
"""
from __future__ import annotations

import pytest

from emoekg._lib.adaptive_window import compute_window_size, slice_by_window


# ---------------------------------------------------------------------------
# compute_window_size — friendly snapping
# ---------------------------------------------------------------------------


def test_short_video_3min_snaps_to_5s():
    # 180s / 90 target = 2s raw → snap up to friendly 5s.
    assert compute_window_size(180) == 5


def test_medium_video_18min_snaps_to_15s():
    # 1080 / 90 = 12 → friendly 15.
    assert compute_window_size(18 * 60) == 15


def test_long_video_1h_snaps_to_45s():
    # 3600 / 90 = 40 → friendly 45.
    assert compute_window_size(3600) == 45


def test_very_long_3h_snaps_to_120s():
    # 10800 / 90 = 120 → friendly 120 (exact).
    assert compute_window_size(3 * 3600) == 120


def test_caps_at_180s_for_10h_compilation():
    # 10h compilation: 36000 / 90 = 400 (> 180), cap at 180.
    assert compute_window_size(10 * 3600) == 180


def test_zero_duration_returns_minimum_window():
    # Degenerate video — still return the smallest friendly window so the
    # caller doesn't have to special-case it.
    assert compute_window_size(0) == 5


def test_negative_duration_treated_as_zero():
    # Defensive: if upstream hands us a corrupt duration, don't raise.
    assert compute_window_size(-100) == 5


def test_window_size_monotonic_nondecreasing():
    # Longer video → never a smaller window. Sanity check that snapping
    # doesn't accidentally go backwards.
    durations = [60, 180, 600, 1800, 3600, 7200, 36000]
    sizes = [compute_window_size(d) for d in durations]
    assert sizes == sorted(sizes)


# ---------------------------------------------------------------------------
# slice_by_window — structural shape
# ---------------------------------------------------------------------------


def test_slice_empty_danmakus_still_produces_chunks():
    # No danmakus but a 60s video should yield 4 empty 15s chunks.
    result = slice_by_window([], window_size=15, total_duration=60)
    assert result == [
        {"chunk_id": "C001", "time_start": 0, "time_end": 15, "danmakus": []},
        {"chunk_id": "C002", "time_start": 15, "time_end": 30, "danmakus": []},
        {"chunk_id": "C003", "time_start": 30, "time_end": 45, "danmakus": []},
        {"chunk_id": "C004", "time_start": 45, "time_end": 60, "danmakus": []},
    ]


def test_slice_chunk_ids_are_zero_padded_three_digits():
    # Need >= 100 chunks to confirm zero-pad width.
    result = slice_by_window([], window_size=1, total_duration=150)
    assert result[0]["chunk_id"] == "C001"
    assert result[9]["chunk_id"] == "C010"
    assert result[99]["chunk_id"] == "C100"


def test_slice_zero_duration_returns_empty_list():
    assert slice_by_window([], window_size=10, total_duration=0) == []


def test_slice_partial_tail_chunk():
    # 25s video, 10s window → [0,10), [10,20), [20,25].
    result = slice_by_window([], window_size=10, total_duration=25)
    assert len(result) == 3
    assert (result[-1]["time_start"], result[-1]["time_end"]) == (20, 25)


# ---------------------------------------------------------------------------
# slice_by_window — danmaku bucketing
# ---------------------------------------------------------------------------


def test_slice_basic_bucketing():
    danmakus = [
        {"time": 2.1, "text": "a"},
        {"time": 7.5, "text": "b"},
        {"time": 16.0, "text": "c"},
    ]
    result = slice_by_window(danmakus, window_size=10, total_duration=30)
    assert len(result) == 3
    assert [d["text"] for d in result[0]["danmakus"]] == ["a", "b"]
    assert [d["text"] for d in result[1]["danmakus"]] == ["c"]
    assert result[2]["danmakus"] == []


def test_slice_left_closed_right_open_on_window_boundary():
    # time == window_size is NOT in C001; it's in C002. [0,10) / [10,20).
    danmakus = [
        {"time": 10.0, "text": "boundary"},
        {"time": 9.999, "text": "just_before"},
    ]
    result = slice_by_window(danmakus, window_size=10, total_duration=20)
    assert [d["text"] for d in result[0]["danmakus"]] == ["just_before"]
    assert [d["text"] for d in result[1]["danmakus"]] == ["boundary"]


def test_slice_final_chunk_is_closed_on_the_right():
    # A danmaku exactly at total_duration (Bilibili's `progress` max) must
    # land in the LAST chunk, not get silently dropped.
    danmakus = [{"time": 30.0, "text": "final_frame"}]
    result = slice_by_window(danmakus, window_size=10, total_duration=30)
    assert result[-1]["time_end"] == 30
    assert [d["text"] for d in result[-1]["danmakus"]] == ["final_frame"]


def test_slice_drops_danmakus_beyond_total_duration():
    # Corrupt upstream data: a danmaku with time past the reported video
    # duration. Drop it silently; don't raise.
    danmakus = [
        {"time": 5.0, "text": "ok"},
        {"time": 999.0, "text": "stray"},
    ]
    result = slice_by_window(danmakus, window_size=10, total_duration=30)
    all_texts = [d["text"] for c in result for d in c["danmakus"]]
    assert all_texts == ["ok"]


def test_slice_drops_danmakus_with_negative_time():
    # Defensive: negative `time` is nonsense. Drop it.
    danmakus = [
        {"time": -1.0, "text": "bad"},
        {"time": 5.0, "text": "ok"},
    ]
    result = slice_by_window(danmakus, window_size=10, total_duration=30)
    all_texts = [d["text"] for c in result for d in c["danmakus"]]
    assert all_texts == ["ok"]


def test_slice_sorts_input_defensively():
    # Input deliberately unsorted; danmakus inside each chunk come out in
    # ascending time order.
    danmakus = [
        {"time": 7.5, "text": "b"},
        {"time": 16.0, "text": "c"},
        {"time": 2.1, "text": "a"},
    ]
    result = slice_by_window(danmakus, window_size=10, total_duration=30)
    assert [d["text"] for d in result[0]["danmakus"]] == ["a", "b"]
    assert [d["text"] for d in result[1]["danmakus"]] == ["c"]


def test_slice_preserves_all_danmaku_fields():
    # We should pass the original danmaku dicts through untouched (same
    # identity — the pipeline needs `mode`, `color`, etc. later).
    dm = {"time": 5.0, "text": "hi", "mode": 1, "color": 0xFFFFFF, "uid": "abc"}
    result = slice_by_window([dm], window_size=10, total_duration=30)
    assert result[0]["danmakus"][0] is dm
