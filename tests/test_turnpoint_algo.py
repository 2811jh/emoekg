"""Tests for emoekg._lib.turnpoint_algo.

Two detection modes are covered:

  * :func:`find_peaks_valleys` — per-dimension local extrema filtered by
    height / distance / prominence, plus a "neighbor baseline" guard so a
    dimension that was silent the whole video never yields spurious valleys.
  * :func:`find_shifts` — Jensen-Shannon divergence between the emotion
    distribution of the previous window and the next window; when the two
    probability simplices diverge sharply, mark that chunk as a shift.

Plus :func:`merge_turnpoints`, which dedupes nearby detections, keeps the
strongest one per cluster, caps the total and assigns ``TP01 … TPNN`` ids.
"""
from __future__ import annotations

import pytest

from emoekg._lib.plutchik import DIMENSIONS
from emoekg._lib.turnpoint_algo import (
    find_peaks_valleys,
    find_shifts,
    merge_turnpoints,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_scores(series: dict[str, list[int]]) -> list[dict]:
    """Build per-chunk score entries from per-dimension arrays.

    All unspecified dimensions default to 0. Meta fields are filled with
    throw-away values — detection cares about the score vector only.
    """
    n = len(next(iter(series.values())))
    entries: list[dict] = []
    for i in range(n):
        entry = {
            "chunk_id": f"C{i + 1:03d}",
            "time_start": i * 15,
            "time_end": (i + 1) * 15,
            "n_danmaku": 20,
            "note": "",
        }
        for d in DIMENSIONS:
            entry[d] = series.get(d, [0] * n)[i]
        entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# find_peaks_valleys — peaks
# ---------------------------------------------------------------------------


def test_find_single_joy_peak():
    joy = [1, 2, 3, 9, 3, 2, 1, 1, 1, 1]  # peak at index 3
    result = find_peaks_valleys(_make_scores({"joy": joy}))
    peak_ids = [r["chunk_id"] for r in result
                if r["type"] == "peak" and r["main_dimension"] == "joy"]
    assert "C004" in peak_ids


def test_peak_records_magnitude_and_direction():
    joy = [1, 2, 3, 9, 3, 2, 1, 1, 1, 1]
    result = find_peaks_valleys(_make_scores({"joy": joy}))
    peak = next(r for r in result
                if r["type"] == "peak" and r["main_dimension"] == "joy")
    assert peak["magnitude"] == pytest.approx(9.0)
    assert peak["direction"] == "up"
    assert "joy" in peak["description"]


def test_ignores_small_bumps_below_height_threshold():
    joy = [1, 2, 3, 4, 3, 2, 1] * 3  # max=4, below PEAK_HEIGHT=6
    result = find_peaks_valleys(_make_scores({"joy": joy}))
    assert not any(
        r["type"] == "peak" and r["main_dimension"] == "joy"
        for r in result
    )


def test_ignores_plateau_without_prominence():
    # A flat plateau at 8 doesn't have local maxima above threshold.
    joy = [8, 8, 8, 8, 8, 8, 8, 8, 8, 8]
    result = find_peaks_valleys(_make_scores({"joy": joy}))
    peaks = [r for r in result
             if r["type"] == "peak" and r["main_dimension"] == "joy"]
    assert peaks == []


def test_empty_input_returns_empty():
    assert find_peaks_valleys([]) == []


# ---------------------------------------------------------------------------
# find_peaks_valleys — valleys (only meaningful against a sustained baseline)
# ---------------------------------------------------------------------------


def test_detects_valley_against_high_baseline():
    anger = [8, 8, 8, 8, 8, 1, 8, 8, 8, 8]
    result = find_peaks_valleys(_make_scores({"anger": anger}))
    valleys = [r for r in result
               if r["type"] == "valley" and r["main_dimension"] == "anger"]
    assert len(valleys) >= 1
    v = valleys[0]
    assert v["direction"] == "down"
    assert v["magnitude"] == pytest.approx(1.0)


def test_ignores_dip_when_baseline_is_low():
    # anger was already near-zero, so "dipping" to 0 isn't a meaningful valley.
    anger = [2, 1, 2, 0, 2, 1, 1, 2, 1, 2]
    result = find_peaks_valleys(_make_scores({"anger": anger}))
    valleys = [r for r in result
               if r["type"] == "valley" and r["main_dimension"] == "anger"]
    assert valleys == []


# ---------------------------------------------------------------------------
# find_shifts — JS divergence between sliding distributions
# ---------------------------------------------------------------------------


def test_find_shifts_detects_sharp_emotion_switch():
    # First half is all joy, second half is all anger → clear shift around mid.
    scores = _make_scores({
        "joy":   [8, 8, 8, 8, 8, 0, 0, 0, 0, 0],
        "anger": [0, 0, 0, 0, 0, 8, 8, 8, 8, 8],
    })
    shifts = find_shifts(scores)
    shift_indices = [s["chunk_index"] for s in shifts]
    # The shift should land somewhere in the transition region [3, 7].
    assert any(3 <= i <= 7 for i in shift_indices)


def test_find_shifts_records_dominant_dimension_of_change():
    scores = _make_scores({
        "joy":   [8, 8, 8, 8, 8, 0, 0, 0, 0, 0],
        "anger": [0, 0, 0, 0, 0, 8, 8, 8, 8, 8],
    })
    shifts = find_shifts(scores)
    assert shifts, "expected at least one shift"
    # The dimension most responsible for the shift should be either the one
    # that rose (anger) or the one that fell (joy).
    dims = {s["main_dimension"] for s in shifts}
    assert dims & {"joy", "anger"}


def test_find_shifts_silent_on_stable_series():
    # No change in distribution across time → no shifts.
    scores = _make_scores({"joy": [5] * 10, "trust": [3] * 10})
    shifts = find_shifts(scores)
    assert shifts == []


def test_find_shifts_needs_enough_chunks():
    # Too few chunks for both a prev and next window → return empty, don't crash.
    scores = _make_scores({"joy": [5, 5, 5]})
    assert find_shifts(scores) == []


# ---------------------------------------------------------------------------
# merge_turnpoints
# ---------------------------------------------------------------------------


def _tp(idx: int, *, dim: str = "joy", tp_type: str = "peak",
        mag: float = 1.0) -> dict:
    return {
        "chunk_id": f"C{idx + 1:03d}",
        "chunk_index": idx,
        "type": tp_type,
        "main_dimension": dim,
        "direction": "up",
        "magnitude": mag,
        "description": "x",
    }


def test_merge_deduplicates_adjacent_turnpoints_keeps_strongest():
    a = _tp(9, dim="joy", tp_type="peak", mag=9.0)
    b = _tp(10, dim="joy", tp_type="shift", mag=0.5)
    merged = merge_turnpoints([a, b], window_size=15)
    assert len(merged) == 1
    # Strongest magnitude wins regardless of type.
    assert merged[0]["type"] == "peak"
    assert merged[0]["magnitude"] == pytest.approx(9.0)


def test_merge_keeps_well_separated_turnpoints():
    # Gap > 2 chunks → both survive.
    a = _tp(5, mag=7.0)
    b = _tp(20, mag=6.5)
    merged = merge_turnpoints([a, b], window_size=15)
    assert len(merged) == 2


def test_merge_caps_at_max_total_keeping_highest_magnitude():
    tps = [_tp(i * 5, mag=float(i)) for i in range(30)]
    merged = merge_turnpoints(tps, window_size=15, max_total=15)
    assert len(merged) == 15
    # Kept the top 15 by magnitude: indices 15..29 (mag 15..29).
    mags = {tp["magnitude"] for tp in merged}
    assert min(mags) >= 15.0


def test_merge_assigns_sequential_turnpoint_ids_sorted_by_time():
    tps = [_tp(30, mag=3.0), _tp(10, mag=5.0), _tp(20, mag=1.0)]
    merged = merge_turnpoints(tps, window_size=15)
    assert [m["turnpoint_id"] for m in merged] == ["TP01", "TP02", "TP03"]
    # Time-ordered, not magnitude-ordered.
    assert [m["chunk_index"] for m in merged] == [10, 20, 30]


def test_merge_empty_input_returns_empty():
    assert merge_turnpoints([], window_size=15) == []
