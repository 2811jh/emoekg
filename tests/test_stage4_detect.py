"""Tests for emoekg.stages.detect_turnpoints (Stage 4).

Reads ``meta.json + scores.json + danmaku.json``, runs both detectors,
merges overlapping detections, attaches up to 5 evidence danmakus per
turnpoint, and writes ``turnpoints.json``. Points pinned down:

  * happy path: clear peaks surface, each carries ``turnpoint_id`` + evidence
  * schema validation: if the Agent's ``scores.json`` has missing dims, bad
    ranges, or the wrong number of chunks, Stage 4 aborts with exit code 2
  * idempotent skip + --force
  * evidence fallback: when the turnpoint chunk has fewer than 5 danmakus
    we broaden the pool to adjacent chunks
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from emoekg._lib.adaptive_window import compute_window_size
from emoekg._lib.plutchik import DIMENSIONS
from emoekg.stages import detect_turnpoints


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _score(i: int, window: int, **dims) -> dict:
    entry = {
        "chunk_id": f"C{i + 1:03d}",
        "time_start": i * window,
        "time_end": (i + 1) * window,
        "n_danmaku": 20,
        "note": "",
    }
    for d in DIMENSIONS:
        entry[d] = dims.get(d, 0)
    return entry


def _write_full_fixture(wd: Path, joy_series: list[int]):
    """Write a fixture whose chunk count matches ``compute_window_size``.

    We pick a duration that divides cleanly by len(joy_series) AND gives the
    adaptive window we want. For 10 chunks at 15s each we need duration=1350s
    (1350/90=15s friendly window, 1350/15=90... wait that's 90 chunks). Let's
    compute both ways and assert consistency.
    """
    n = len(joy_series)
    # Goal: pick `window` such that compute_window_size(n*window) == window.
    # For n=10, that's window=15s → duration 150s → compute returns 5. Hmm.
    # Concretely: we iterate over friendly windows and find one where the
    # math lines up.
    for w in (5, 10, 15, 30, 45, 60, 90, 120, 180):
        dur = n * w
        if compute_window_size(dur) == w:
            window, duration = w, dur
            break
    else:
        raise AssertionError(f"no window fits {n} chunks")

    (wd / "meta.json").write_text(
        json.dumps({
            "bvid": "BVTEST",
            "title": "测试",
            "up": "UP",
            "duration_sec": duration,
            "view_count": 0,
            "cid": 1,
            "fetched_at": "2026-05-07T00:00:00",
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    scores = [_score(i, window, joy=j) for i, j in enumerate(joy_series)]
    (wd / "scores.json").write_text(
        json.dumps(scores, ensure_ascii=False), encoding="utf-8"
    )

    # Dense danmaku stream spread evenly over the video.
    step = max(1, duration // 50)
    dms = [
        {
            "time": float(i * step), "text": f"好好笑{i}", "mode": 1,
            "color": 0xFFFFFF, "fontsize": 25, "user_hash": f"u{i}",
        }
        for i in range(50)
        if i * step < duration
    ]
    (wd / "danmaku.json").write_text(
        json.dumps(dms, ensure_ascii=False), encoding="utf-8"
    )

    return window, duration


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_run_produces_turnpoints_with_evidence(tmp_path):
    # Two clear joy peaks at index 3 and 7.
    _write_full_fixture(tmp_path, [1, 2, 3, 9, 4, 2, 2, 9, 3, 1])

    detect_turnpoints.run(tmp_path)

    tps = json.loads((tmp_path / "turnpoints.json").read_text(encoding="utf-8"))
    assert len(tps) >= 1
    for tp in tps:
        assert tp["turnpoint_id"].startswith("TP")
        assert tp["type"] in ("peak", "valley", "shift")
        assert "evidence_danmakus" in tp
        # time_start / time_end should be populated from the score row.
        assert "time_start" in tp
        assert "time_end" in tp


def test_run_turnpoint_ids_are_sequential_from_TP01(tmp_path):
    _write_full_fixture(tmp_path, [1, 2, 3, 9, 4, 2, 2, 9, 3, 1])

    detect_turnpoints.run(tmp_path)

    tps = json.loads((tmp_path / "turnpoints.json").read_text(encoding="utf-8"))
    ids = [t["turnpoint_id"] for t in tps]
    assert ids == [f"TP{i:02d}" for i in range(1, len(tps) + 1)]


def test_run_evidence_is_serializable_subset(tmp_path):
    _write_full_fixture(tmp_path, [1, 2, 3, 9, 4, 2, 2, 9, 3, 1])

    detect_turnpoints.run(tmp_path)

    tps = json.loads((tmp_path / "turnpoints.json").read_text(encoding="utf-8"))
    # We intentionally trim to {time, text, color} — evidence is for the HTML
    # report, not for downstream algorithms, so dropping user_hash is fine.
    for tp in tps:
        for ev in tp["evidence_danmakus"]:
            assert set(ev.keys()) <= {"time", "text", "color"}


# ---------------------------------------------------------------------------
# Score schema validation
# ---------------------------------------------------------------------------


def test_run_fails_when_score_count_mismatches_expected(tmp_path, capsys):
    _write_full_fixture(tmp_path, [1, 2, 3, 9, 4, 2, 2, 9, 3, 1])
    # Drop the last score row → now 9 when 10 were expected.
    scores = json.loads((tmp_path / "scores.json").read_text(encoding="utf-8"))
    scores.pop()
    (tmp_path / "scores.json").write_text(
        json.dumps(scores, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(SystemExit) as ei:
        detect_turnpoints.run(tmp_path, force=True)
    assert ei.value.code != 0


def test_run_fails_on_malformed_score_row(tmp_path):
    _write_full_fixture(tmp_path, [1, 2, 3, 9, 4, 2, 2, 9, 3, 1])
    scores = json.loads((tmp_path / "scores.json").read_text(encoding="utf-8"))
    # Break one row — joy out of [0, 10].
    scores[0]["joy"] = 99
    (tmp_path / "scores.json").write_text(
        json.dumps(scores, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises((SystemExit, ValueError)):
        detect_turnpoints.run(tmp_path, force=True)


# ---------------------------------------------------------------------------
# Idempotency & --force
# ---------------------------------------------------------------------------


def test_run_skips_when_turnpoints_exist(tmp_path):
    _write_full_fixture(tmp_path, [1, 2, 3, 9, 4, 2, 2, 9, 3, 1])
    (tmp_path / "turnpoints.json").write_text(
        '[{"marker": "keep"}]', encoding="utf-8"
    )

    detect_turnpoints.run(tmp_path, force=False)

    preserved = json.loads((tmp_path / "turnpoints.json").read_text(encoding="utf-8"))
    assert preserved == [{"marker": "keep"}]


def test_run_force_regenerates(tmp_path):
    _write_full_fixture(tmp_path, [1, 2, 3, 9, 4, 2, 2, 9, 3, 1])
    (tmp_path / "turnpoints.json").write_text(
        '[{"marker": "stale"}]', encoding="utf-8"
    )

    detect_turnpoints.run(tmp_path, force=True)

    tps = json.loads((tmp_path / "turnpoints.json").read_text(encoding="utf-8"))
    assert tps != [{"marker": "stale"}]
    assert any("turnpoint_id" in tp for tp in tps)


# ---------------------------------------------------------------------------
# Evidence fallback to adjacent chunks
# ---------------------------------------------------------------------------


def test_run_broadens_evidence_pool_to_adjacent_chunks(tmp_path):
    window, duration = _write_full_fixture(tmp_path, [1, 2, 3, 9, 4, 2, 2, 9, 3, 1])
    # Peak chunk_index = 3 spans [3*w, 4*w). Place danmakus ONLY in the
    # adjacent chunk 2, so the turnpoint must broaden its pool to find
    # evidence.
    neighbour_time = 2 * window + 0.5  # firmly inside chunk 2
    dms = [
        {"time": neighbour_time, "text": "乐死了 a", "mode": 1, "color": 0,
         "fontsize": 25, "user_hash": "u1"},
        {"time": neighbour_time + 1.0, "text": "笑死了 b", "mode": 1, "color": 0,
         "fontsize": 25, "user_hash": "u2"},
    ]
    (tmp_path / "danmaku.json").write_text(
        json.dumps(dms, ensure_ascii=False), encoding="utf-8"
    )

    detect_turnpoints.run(tmp_path, force=True)

    tps = json.loads((tmp_path / "turnpoints.json").read_text(encoding="utf-8"))
    # The peak at chunk_index 3 should still find evidence from chunk 2.
    peak_tps = [t for t in tps if t["chunk_index"] == 3]
    assert peak_tps
    assert peak_tps[0]["evidence_danmakus"], (
        "expected adjacent-chunk fallback to surface evidence"
    )
