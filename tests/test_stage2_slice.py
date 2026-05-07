"""Tests for emoekg.stages.slice_chunks (Stage 2).

Stage 2 reads meta.json + danmaku.json (Stage 1 output), slices danmakus into
adaptive windows, renders chunks.md via Jinja2, and writes an empty
scores.json skeleton for the Agent to fill in. We pin down:

  * output files exist and have the expected shape
  * chunks.md renders with the header line + per-chunk block
  * chunks with <3 danmakus are marked SPARSE
  * dense chunks (>150) are down-sampled (head30 + mid90 + tail30)
  * idempotent skip + --force flag match Stage 1 semantics
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from emoekg.stages import slice_chunks


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_meta(wd: Path, duration_sec: int = 60):
    (wd / "meta.json").write_text(
        json.dumps(
            {
                "bvid": "BVTEST",
                "title": "测试视频",
                "up": "UP主",
                "duration_sec": duration_sec,
                "view_count": 1234,
                "cid": 1,
                "fetched_at": "2026-05-07T00:00:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _dm(time: float, text: str, user: str = "u") -> dict:
    return {
        "time": time, "text": text, "mode": 1,
        "color": 0xFFFFFF, "fontsize": 25, "user_hash": user,
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_run_produces_chunks_md_and_scores_skeleton(tmp_path):
    _write_meta(tmp_path, duration_sec=60)
    (tmp_path / "danmaku.json").write_text(
        json.dumps([
            _dm(2.0, "开场", "u1"),
            _dm(3.5, "666", "u2"),
            _dm(20.0, "什么情况", "u3"),
        ], ensure_ascii=False),
        encoding="utf-8",
    )

    slice_chunks.run(tmp_path)

    chunks_text = (tmp_path / "chunks.md").read_text(encoding="utf-8")
    assert "Danmaku Chunks for BVTEST" in chunks_text
    assert "[C001]" in chunks_text
    assert "开场" in chunks_text
    assert "什么情况" in chunks_text

    # The Agent will fill this in during Stage 3.
    scores = json.loads((tmp_path / "scores.json").read_text(encoding="utf-8"))
    assert scores == []


def test_run_header_contains_metadata(tmp_path):
    _write_meta(tmp_path, duration_sec=120)
    (tmp_path / "danmaku.json").write_text("[]", encoding="utf-8")

    slice_chunks.run(tmp_path)

    text = (tmp_path / "chunks.md").read_text(encoding="utf-8")
    assert "《测试视频》" in text
    assert "UP: UP主" in text
    assert "00:02:00" in text  # 120s → 00:02:00
    assert "Total: 0 弹幕" in text


# ---------------------------------------------------------------------------
# SPARSE marking
# ---------------------------------------------------------------------------


def test_run_marks_sparse_chunks(tmp_path):
    # 60s video → adaptive window = 5s → 12 chunks, most empty → SPARSE everywhere.
    _write_meta(tmp_path, duration_sec=60)
    (tmp_path / "danmaku.json").write_text(
        json.dumps([_dm(2.0, "a", "u1"), _dm(3.0, "b", "u2")], ensure_ascii=False),
        encoding="utf-8",
    )

    slice_chunks.run(tmp_path)

    text = (tmp_path / "chunks.md").read_text(encoding="utf-8")
    assert "SPARSE" in text


def test_run_does_not_mark_dense_as_sparse(tmp_path):
    # Pack 10 danmakus into a single 5s window → NOT sparse.
    _write_meta(tmp_path, duration_sec=60)
    dms = [_dm(t, f"dm{t}", f"u{i}") for i, t in enumerate([0.1, 0.5, 1.0, 1.5, 2.0,
                                                             2.5, 3.0, 3.5, 4.0, 4.5])]
    (tmp_path / "danmaku.json").write_text(
        json.dumps(dms, ensure_ascii=False), encoding="utf-8",
    )

    slice_chunks.run(tmp_path)

    text = (tmp_path / "chunks.md").read_text(encoding="utf-8")
    # C001 covers [0,5), has 10 danmakus — must NOT be tagged SPARSE.
    c001_line = [line for line in text.splitlines() if line.startswith("## [C001]")][0]
    assert "SPARSE" not in c001_line
    assert "n=10" in c001_line


# ---------------------------------------------------------------------------
# Dense chunk down-sampling
# ---------------------------------------------------------------------------


def test_run_downsamples_dense_chunk(tmp_path):
    # 200 danmakus all in C001 → display_danmakus should be <= 150 (head30+mid90+tail30).
    _write_meta(tmp_path, duration_sec=60)
    dms = [_dm(t / 100.0, f"dm{t}", f"u{t}") for t in range(200)]
    (tmp_path / "danmaku.json").write_text(
        json.dumps(dms, ensure_ascii=False), encoding="utf-8",
    )

    slice_chunks.run(tmp_path)

    text = (tmp_path / "chunks.md").read_text(encoding="utf-8")
    # Count bullet lines under C001 header until the next chunk header.
    lines = text.splitlines()
    in_c001 = False
    bullet_count = 0
    for line in lines:
        if line.startswith("## [C001]"):
            in_c001 = True
            continue
        if in_c001 and line.startswith("## ["):
            break
        if in_c001 and line.startswith("- "):
            bullet_count += 1
    # head 30 + mid 90 + tail 30 = 150.
    assert bullet_count == 150
    # The chunk header line still records the true total (n=200).
    c001_header = [line for line in lines if line.startswith("## [C001]")][0]
    assert "n=200" in c001_header


# ---------------------------------------------------------------------------
# Idempotency & --force
# ---------------------------------------------------------------------------


def test_run_skips_when_all_three_outputs_exist(tmp_path):
    _write_meta(tmp_path)
    (tmp_path / "danmaku.json").write_text("[]", encoding="utf-8")
    (tmp_path / "chunks.md").write_text("STALE", encoding="utf-8")
    (tmp_path / "scores.json").write_text('[{"marker":"keep"}]', encoding="utf-8")
    # insights.json is a sibling skeleton; its presence is part of the
    # "fully prepared" signal that triggers SKIP.
    (tmp_path / "insights.json").write_text(
        '{"summary":"kept","insights":[]}', encoding="utf-8",
    )

    slice_chunks.run(tmp_path, force=False)

    assert (tmp_path / "chunks.md").read_text(encoding="utf-8") == "STALE"
    assert json.loads((tmp_path / "scores.json").read_text(encoding="utf-8")) == [
        {"marker": "keep"}
    ]
    # Insights must also have been preserved — Stage 2 should not be
    # stomping Agent output on a dirty re-run.
    assert json.loads((tmp_path / "insights.json").read_text(encoding="utf-8")) \
        == {"summary": "kept", "insights": []}


def test_run_rewrites_when_insights_json_missing(tmp_path):
    # An older working dir with only chunks.md + scores.json must NOT be
    # treated as "done" — we need to upgrade it to the insights protocol.
    _write_meta(tmp_path)
    (tmp_path / "danmaku.json").write_text("[]", encoding="utf-8")
    (tmp_path / "chunks.md").write_text("STALE", encoding="utf-8")
    (tmp_path / "scores.json").write_text('[{"marker":"keep"}]', encoding="utf-8")
    # NO insights.json.

    slice_chunks.run(tmp_path, force=False)

    # chunks.md gets rewritten to the real prompt, scores.json reset to [],
    # and a fresh insights.json skeleton appears.
    assert (tmp_path / "chunks.md").read_text(encoding="utf-8") != "STALE"
    assert (tmp_path / "insights.json").exists()
    ins = json.loads((tmp_path / "insights.json").read_text(encoding="utf-8"))
    assert ins == {"summary": "", "insights": []}


def test_run_force_overwrites(tmp_path):
    _write_meta(tmp_path)
    (tmp_path / "danmaku.json").write_text("[]", encoding="utf-8")
    (tmp_path / "chunks.md").write_text("STALE", encoding="utf-8")
    (tmp_path / "scores.json").write_text('[{"marker":"keep"}]', encoding="utf-8")

    slice_chunks.run(tmp_path, force=True)

    assert (tmp_path / "chunks.md").read_text(encoding="utf-8") != "STALE"
    assert json.loads((tmp_path / "scores.json").read_text(encoding="utf-8")) == []


# ---------------------------------------------------------------------------
# Deterministic dense-sampling
# ---------------------------------------------------------------------------


def test_run_dense_sampling_is_deterministic(tmp_path):
    # Same input + same seed → same bullet list.
    _write_meta(tmp_path, duration_sec=60)
    dms = [_dm(t / 100.0, f"dm{t}", f"u{t}") for t in range(200)]
    (tmp_path / "danmaku.json").write_text(
        json.dumps(dms, ensure_ascii=False), encoding="utf-8",
    )

    slice_chunks.run(tmp_path, force=True)
    text_a = (tmp_path / "chunks.md").read_text(encoding="utf-8")

    slice_chunks.run(tmp_path, force=True)
    text_b = (tmp_path / "chunks.md").read_text(encoding="utf-8")

    assert text_a == text_b, "dense sampling must be reproducible across runs"
