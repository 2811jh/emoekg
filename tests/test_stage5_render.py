"""Tests for emoekg.stages.render_report (Stage 5).

This stage emits a single-file HTML. We verify structural contents rather than
pixel-level rendering:

  * file exists, is large (> 100 KB, because ECharts alone is ~1 MB inlined)
  * contains the page title, BV id, and all five JSON data blobs
  * contains the ECharts library (its Apache license header is distinctive)
  * in `--with-video` mode, the embedded config points at the local MP4
  * in default (iframe) mode, the embedded config names the iframe mode
  * idempotent skip + --force semantics match earlier stages
"""
from __future__ import annotations

import json
from pathlib import Path

from emoekg.stages import render_report


def _populate(wd: Path):
    (wd / "meta.json").write_text(
        json.dumps({
            "bvid": "BVTEST", "title": "测试视频", "up": "UP",
            "duration_sec": 60, "view_count": 0, "cid": 1,
            "fetched_at": "2026-05-07T00:00:00",
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    (wd / "danmaku.json").write_text(
        json.dumps([{
            "time": 1.0, "text": "666", "mode": 1,
            "color": 16777215, "fontsize": 25, "user_hash": "h",
        }], ensure_ascii=False),
        encoding="utf-8",
    )
    (wd / "scores.json").write_text(
        json.dumps([{
            "chunk_id": "C001", "time_start": 0, "time_end": 60,
            "n_danmaku": 1,
            "joy": 5, "trust": 0, "fear": 0, "surprise": 0,
            "sadness": 0, "disgust": 0, "anger": 0, "anticipation": 0,
            "note": "x",
        }], ensure_ascii=False),
        encoding="utf-8",
    )
    (wd / "turnpoints.json").write_text("[]", encoding="utf-8")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_run_produces_single_html_file(tmp_path):
    _populate(tmp_path)

    render_report.run(tmp_path)

    html_path = tmp_path / "emoekg_report.html"
    assert html_path.exists()
    html = html_path.read_text(encoding="utf-8")

    # Header + title
    assert "emoekg · 情绪心电图" in html
    assert "测试视频" in html
    assert "BVTEST" in html

    # All five JSON blobs present.
    for sid in (
        "data-meta", "data-scores", "data-turnpoints",
        "data-danmakus", "data-config",
    ):
        assert f'id="{sid}"' in html

    # ECharts inlined: Apache license blurb is distinctive.
    assert "Licensed to the Apache Software Foundation" in html

    # Sanity lower-bound on size (ECharts alone is ~1MB).
    assert len(html) > 500_000


def test_run_default_mode_is_iframe(tmp_path):
    _populate(tmp_path)

    render_report.run(tmp_path)

    html = (tmp_path / "emoekg_report.html").read_text(encoding="utf-8")
    assert '"video_mode": "iframe"' in html
    assert '"video_path": null' in html


def test_run_with_video_mode_points_at_local_mp4(tmp_path):
    _populate(tmp_path)
    (tmp_path / "video.mp4").write_bytes(b"fake-mp4")

    render_report.run(tmp_path, with_video=True)

    html = (tmp_path / "emoekg_report.html").read_text(encoding="utf-8")
    assert '"video_mode": "local"' in html
    assert '"video_path": "./video.mp4"' in html


# ---------------------------------------------------------------------------
# Idempotency & --force
# ---------------------------------------------------------------------------


def test_run_skips_when_html_exists(tmp_path):
    _populate(tmp_path)
    (tmp_path / "emoekg_report.html").write_text("STALE", encoding="utf-8")

    render_report.run(tmp_path, force=False)

    assert (tmp_path / "emoekg_report.html").read_text(encoding="utf-8") == "STALE"


def test_run_force_overwrites(tmp_path):
    _populate(tmp_path)
    (tmp_path / "emoekg_report.html").write_text("STALE", encoding="utf-8")

    render_report.run(tmp_path, force=True)

    html = (tmp_path / "emoekg_report.html").read_text(encoding="utf-8")
    assert html != "STALE"
    assert "BVTEST" in html


# ---------------------------------------------------------------------------
# HTML structure sanity
# ---------------------------------------------------------------------------


def test_run_html_includes_known_panels(tmp_path):
    _populate(tmp_path)

    render_report.run(tmp_path)

    html = (tmp_path / "emoekg_report.html").read_text(encoding="utf-8")
    for panel_id in ("overview", "video-wrapper", "ecg-chart",
                     "danmaku-list", "turnpoints", "legend"):
        assert f'id="{panel_id}"' in html, f"missing #{panel_id}"


def test_run_data_json_contains_score_fields(tmp_path):
    _populate(tmp_path)

    render_report.run(tmp_path)

    html = (tmp_path / "emoekg_report.html").read_text(encoding="utf-8")
    # Score blob contains the embedded chunk row.
    assert '"chunk_id": "C001"' in html
    assert '"joy": 5' in html
