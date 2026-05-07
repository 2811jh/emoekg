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

    # Brand marker — "emoekg" plus the video title must both appear somewhere
    # in the rendered page. We don't pin a specific headline string here
    # because the UI copy evolves; the invariant is "this is recognizably
    # an emoekg report for this specific video".
    assert "emoekg" in html.lower()
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


# ---------------------------------------------------------------------------
# Insights protocol (Agent-produced Executive Summary)
# ---------------------------------------------------------------------------


class TestInsightsRendering:
    """``insights.json`` is the Agent's TL;DR + three headline findings.

    It is optional: a missing file, a malformed file, or the empty skeleton
    that Stage 2 writes all degrade gracefully — the report still renders,
    it just omits the Executive Summary block.
    """

    def test_missing_insights_json_is_not_fatal(self, tmp_path):
        _populate(tmp_path)
        # deliberately no insights.json

        render_report.run(tmp_path)

        html = (tmp_path / "emoekg_report.html").read_text(encoding="utf-8")
        # Empty summary ⇒ the `{% if insights.summary %}` guard suppresses the block.
        assert 'class="tldr"' not in html
        assert "BVTEST" in html  # report still valid

    def test_skeleton_insights_json_is_not_rendered(self, tmp_path):
        _populate(tmp_path)
        (tmp_path / "insights.json").write_text(
            '{"summary":"","insights":[]}', encoding="utf-8",
        )

        render_report.run(tmp_path)
        html = (tmp_path / "emoekg_report.html").read_text(encoding="utf-8")
        assert 'class="tldr"' not in html

    def test_populated_insights_appear_in_hero(self, tmp_path):
        _populate(tmp_path)
        (tmp_path / "insights.json").write_text(
            json.dumps({
                "summary": "观众的情绪核心是信任与期待的双峰结构。",
                "insights": [
                    {"title": "期待先行", "body": "弹幕在开场 30 秒迅速锁定转化。"},
                    {"title": "梗触发",   "body": "跨 IP 识别引发集体共鸣。"},
                    {"title": "流畅背书", "body": "手机党反馈是第二个信任高点。"},
                ]
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        render_report.run(tmp_path)
        html = (tmp_path / "emoekg_report.html").read_text(encoding="utf-8")

        assert 'class="tldr"' in html
        assert "信任与期待的双峰结构" in html
        assert "期待先行" in html
        assert "跨 IP 识别" in html
        assert "流畅背书" in html
        # All three insights enumerate in the template loop.
        assert html.count('class="insight"') == 3

    def test_malformed_insights_json_is_swallowed(self, tmp_path):
        _populate(tmp_path)
        (tmp_path / "insights.json").write_text("not json {{{", encoding="utf-8")

        # Should not raise.
        render_report.run(tmp_path)
        html = (tmp_path / "emoekg_report.html").read_text(encoding="utf-8")
        assert 'class="tldr"' not in html

    def test_partially_shaped_insights_fills_defaults(self, tmp_path):
        _populate(tmp_path)
        # Missing `body` on one insight and extraneous `junk` key.
        (tmp_path / "insights.json").write_text(
            json.dumps({
                "summary": "s",
                "insights": [
                    {"title": "A"},  # no body
                    {"title": "B", "body": "b2", "junk": 1},
                    "not a dict",   # filtered out
                ],
                "extra": "ignored",
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        render_report.run(tmp_path)
        html = (tmp_path / "emoekg_report.html").read_text(encoding="utf-8")
        # 2 well-shaped insights after filtering.
        assert html.count('class="insight"') == 2
        assert "A" in html and "B" in html and "b2" in html
