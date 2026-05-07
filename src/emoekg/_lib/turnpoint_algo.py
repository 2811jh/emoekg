"""Turnpoint detection for the emotional ECG.

Two orthogonal detectors run on the per-chunk 8-dim scores:

* :func:`find_peaks_valleys` — scipy ``find_peaks`` on each dimension. A peak
  needs ``height >= 6``, ``distance >= 3``, ``prominence >= 2``. Valleys are
  only reported when the dimension had a sustained high baseline (otherwise a
  dimension that's near-zero the whole video would produce endless "valleys").
* :func:`find_shifts` — Jensen-Shannon divergence between the distribution of
  the last ``SHIFT_WINDOW`` chunks and the next ``SHIFT_WINDOW`` chunks. High
  divergence means the emotion *mix* reshaped itself here, even if no single
  dimension hit an absolute peak.

:func:`merge_turnpoints` fuses both detectors' output: clusters nearby
detections, keeps the highest-magnitude one per cluster, caps the total
count, and assigns ``TPnn`` ids in chronological order.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from emoekg._lib.plutchik import DIMENSIONS

__all__ = ["find_peaks_valleys", "find_shifts", "merge_turnpoints"]


# ---------------------------------------------------------------------------
# Peak / valley detection (per dimension)
# ---------------------------------------------------------------------------

# Require the peak to be at least this tall on the 0..10 scale.
_PEAK_HEIGHT = 6
# Minimum chunk-distance between consecutive peaks (in chunk units).
_PEAK_DISTANCE = 3
# Prominence: the peak must rise this much above the surrounding baseline.
_PEAK_PROMINENCE = 2
# A valley is only meaningful if the immediate neighbours (within 2 chunks)
# were at or above this level — otherwise the dimension is basically silent.
_VALLEY_NEIGHBOR_MIN = _PEAK_HEIGHT


def _peak_record(idx: int, dim: str, magnitude: float,
                 scores: list[dict]) -> dict:
    return {
        "chunk_id": scores[idx]["chunk_id"],
        "chunk_index": idx,
        "type": "peak",
        "main_dimension": dim,
        "direction": "up",
        "magnitude": magnitude,
        # `description` = hero line (what happened, in one breath);
        # `detail` = the supporting technical readout (optional).
        # Renderers that don't know about `detail` still show something
        # sensible via `description` alone.
        "description": f"{dim} 达到 {magnitude:.0f}/10",
        "detail": "局部峰值",
    }


def _valley_record(idx: int, dim: str, magnitude: float,
                   scores: list[dict]) -> dict:
    return {
        "chunk_id": scores[idx]["chunk_id"],
        "chunk_index": idx,
        "type": "valley",
        "main_dimension": dim,
        "direction": "down",
        "magnitude": magnitude,
        "description": f"{dim} 跌至 {magnitude:.0f}/10",
        "detail": "局部低谷",
    }


def find_peaks_valleys(scores: list[dict]) -> list[dict]:
    """Detect per-dimension peaks and valleys in ``scores``.

    Empty input → empty output.

    Valleys are filtered: a dip in dimension ``D`` is only recorded if ``D``
    reached at least :data:`_VALLEY_NEIGHBOR_MIN` in *some* chunk within 2
    chunks on either side. This keeps the detector from firing on dimensions
    that were silent throughout the video.
    """
    if not scores:
        return []

    results: list[dict] = []
    for dim in DIMENSIONS:
        series = np.array([s.get(dim, 0) for s in scores], dtype=float)

        peak_idx, _ = find_peaks(
            series,
            height=_PEAK_HEIGHT,
            distance=_PEAK_DISTANCE,
            prominence=_PEAK_PROMINENCE,
        )
        for i in peak_idx:
            results.append(_peak_record(int(i), dim, float(series[i]), scores))

        # Valleys: find peaks on the negated series. We still require the same
        # prominence/distance constraints so random noise isn't a "valley".
        valley_idx, _ = find_peaks(
            -series,
            distance=_PEAK_DISTANCE,
            prominence=_PEAK_PROMINENCE,
        )
        for i in valley_idx:
            # `initial=0` on empty slices (endpoints) returns 0 instead of
            # raising on empty `.max()` — that's what we want.
            lo = max(0, i - 2)
            hi = min(len(series), i + 3)
            neighbor_max = max(
                series[lo:i].max(initial=0.0),
                series[i + 1:hi].max(initial=0.0),
            )
            if neighbor_max >= _VALLEY_NEIGHBOR_MIN:
                results.append(
                    _valley_record(int(i), dim, float(series[i]), scores)
                )

    return results


# ---------------------------------------------------------------------------
# Jensen-Shannon divergence shift detection
# ---------------------------------------------------------------------------

_JS_THRESHOLD = 0.15
_SHIFT_WINDOW = 3
_EPS = 1e-12  # floor for log(0) protection


def _normalize_dist(vec: np.ndarray) -> np.ndarray:
    """Turn a raw score vector into a probability distribution over dimensions."""
    s = vec.sum()
    if s <= 0:
        # All-zero chunk: fall back to uniform so JS of two all-zero windows
        # is 0 (rather than undefined).
        return np.full_like(vec, 1.0 / len(vec))
    return vec / s


def _js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen-Shannon divergence (base-2, bits)."""
    m = 0.5 * (p + q)

    def _kl(a: np.ndarray, b: np.ndarray) -> float:
        a = np.where(a == 0, _EPS, a)
        b = np.where(b == 0, _EPS, b)
        return float(np.sum(a * np.log2(a / b)))

    return 0.5 * _kl(p, m) + 0.5 * _kl(q, m)


def find_shifts(scores: list[dict]) -> list[dict]:
    """Detect chunks where the emotion distribution shifts sharply.

    For each candidate index ``i`` with at least ``SHIFT_WINDOW`` chunks on
    both sides, compute the JS divergence between the prior window's
    distribution and the next window's distribution. If it exceeds
    :data:`_JS_THRESHOLD`, mark ``i`` as a shift whose ``main_dimension`` is
    the one with the largest signed change.
    """
    n = len(scores)
    if n < 2 * _SHIFT_WINDOW:
        return []

    matrix = np.array(
        [[s.get(d, 0) for d in DIMENSIONS] for s in scores],
        dtype=float,
    )

    results: list[dict] = []
    for i in range(_SHIFT_WINDOW, n - _SHIFT_WINDOW):
        prev = _normalize_dist(matrix[i - _SHIFT_WINDOW:i].sum(axis=0))
        nxt = _normalize_dist(matrix[i:i + _SHIFT_WINDOW].sum(axis=0))
        js = _js_divergence(prev, nxt)
        if js < _JS_THRESHOLD:
            continue

        diff = (
            matrix[i:i + _SHIFT_WINDOW].mean(axis=0)
            - matrix[i - _SHIFT_WINDOW:i].mean(axis=0)
        )
        top = int(np.argmax(np.abs(diff)))
        dim = DIMENSIONS[top]
        direction = "up" if diff[top] > 0 else "down"
        delta = diff[top]
        adjective = "情绪升温" if direction == "up" else "情绪转冷"
        # Hero line gets the human verb; the arithmetic/JS details drop
        # into `detail` so the renderer can give them a smaller weight.
        results.append({
            "chunk_id": scores[i]["chunk_id"],
            "chunk_index": i,
            "type": "shift",
            "main_dimension": dim,
            "direction": direction,
            "magnitude": float(abs(delta)),
            "description": f"{dim} {adjective}",
            "detail": f"变化 {delta:+.1f} 分 / 10 · 分布差异 JS={js:.2f}",
        })

    return results


# ---------------------------------------------------------------------------
# Merge / dedup / cap
# ---------------------------------------------------------------------------

# Turnpoints within this many chunks of each other are considered one event.
_CLUSTER_GAP = 2


def merge_turnpoints(
    turnpoints: list[dict],
    window_size: int,  # noqa: ARG001 — reserved for future time-based gap tuning
    max_total: int = 15,
) -> list[dict]:
    """Cluster nearby turnpoints, keep the strongest, cap the total.

    Two detections whose ``chunk_index`` differ by ``<= _CLUSTER_GAP`` are
    folded into one event; the winner is the one with the largest magnitude.
    After deduplication the final list is truncated to the ``max_total`` most
    intense turnpoints, then re-sorted chronologically and stamped with
    ``TP01 … TPnn`` ids.

    ``window_size`` is accepted (and ignored today) so that callers can hand
    us the Stage 2 window size and we can later swap the chunk-count gap for
    a time-based threshold without changing the signature.
    """
    if not turnpoints:
        return []

    sorted_tps = sorted(turnpoints, key=lambda t: t["chunk_index"])

    clusters: list[list[dict]] = []
    for tp in sorted_tps:
        if clusters and tp["chunk_index"] - clusters[-1][-1]["chunk_index"] <= _CLUSTER_GAP:
            clusters[-1].append(tp)
        else:
            clusters.append([tp])

    winners = [max(c, key=lambda t: t["magnitude"]) for c in clusters]

    if len(winners) > max_total:
        winners = sorted(
            winners, key=lambda t: t["magnitude"], reverse=True
        )[:max_total]

    winners.sort(key=lambda t: t["chunk_index"])
    for i, tp in enumerate(winners, 1):
        tp["turnpoint_id"] = f"TP{i:02d}"
    return winners
