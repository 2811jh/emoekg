"""Tests for emoekg.stages.fetch_danmaku (Stage 1).

Stage 1 glue is fully exercised with the upstream library mocked out. We
verify:
  * both output files are written with the expected shape
  * `fetched_at` timestamp is injected
  * idempotent skip on second run (no network calls, no file clobber)
  * --force flag bypasses the skip
  * URL → BV id extraction is done by the script itself (so `url` arg
    can be any of the supported forms)
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from emoekg.stages import fetch_danmaku


@pytest.fixture
def fake_meta():
    return {
        "bvid": "BV18acMz4ELL",
        "title": "测试",
        "up": "UP",
        "duration_sec": 60,
        "view_count": 0,
        "cid": 1,
    }


@pytest.fixture
def fake_danmakus():
    return [
        {
            "time": 1.0, "text": "a", "mode": 1,
            "color": 0xFFFFFF, "fontsize": 25, "user_hash": "h1",
        }
    ]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@patch("emoekg.stages.fetch_danmaku.fetch_all_danmakus")
@patch("emoekg.stages.fetch_danmaku.fetch_video_meta")
def test_run_writes_meta_and_danmaku_json(
    mock_meta, mock_dms, fake_meta, fake_danmakus, tmp_path
):
    mock_meta.return_value = fake_meta
    mock_dms.return_value = fake_danmakus

    fetch_danmaku.run(
        "https://www.bilibili.com/video/BV18acMz4ELL/?share_source=copy_web",
        tmp_path,
    )

    meta_path = tmp_path / "meta.json"
    dm_path = tmp_path / "danmaku.json"
    assert meta_path.exists()
    assert dm_path.exists()

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    # Core fields preserved from upstream + fetched_at injected.
    assert meta["bvid"] == "BV18acMz4ELL"
    assert meta["title"] == "测试"
    assert "fetched_at" in meta and meta["fetched_at"]

    dms = json.loads(dm_path.read_text(encoding="utf-8"))
    assert dms == fake_danmakus


@patch("emoekg.stages.fetch_danmaku.fetch_all_danmakus")
@patch("emoekg.stages.fetch_danmaku.fetch_video_meta")
def test_run_accepts_bare_bvid(
    mock_meta, mock_dms, fake_meta, fake_danmakus, tmp_path
):
    mock_meta.return_value = fake_meta
    mock_dms.return_value = fake_danmakus

    fetch_danmaku.run("BV18acMz4ELL", tmp_path)

    # Downstream clients get the canonical BV id, not the raw URL string.
    mock_meta.assert_called_once_with("BV18acMz4ELL")
    mock_dms.assert_called_once_with("BV18acMz4ELL", 60, pubdate=0, allow_login=True)


# ---------------------------------------------------------------------------
# Idempotency & --force
# ---------------------------------------------------------------------------


@patch("emoekg.stages.fetch_danmaku.fetch_all_danmakus")
@patch("emoekg.stages.fetch_danmaku.fetch_video_meta")
def test_run_skips_when_both_files_exist(mock_meta, mock_dms, tmp_path):
    (tmp_path / "meta.json").write_text('{"bvid":"cached"}', encoding="utf-8")
    (tmp_path / "danmaku.json").write_text("[]", encoding="utf-8")

    fetch_danmaku.run("BV18acMz4ELL", tmp_path, force=False)

    # No network calls at all.
    mock_meta.assert_not_called()
    mock_dms.assert_not_called()
    # Cache preserved verbatim.
    assert (
        json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))["bvid"]
        == "cached"
    )


@patch("emoekg.stages.fetch_danmaku.fetch_all_danmakus")
@patch("emoekg.stages.fetch_danmaku.fetch_video_meta")
def test_run_force_flag_overwrites_cache(
    mock_meta, mock_dms, fake_meta, fake_danmakus, tmp_path
):
    (tmp_path / "meta.json").write_text('{"bvid":"stale"}', encoding="utf-8")
    (tmp_path / "danmaku.json").write_text("[]", encoding="utf-8")
    mock_meta.return_value = fake_meta
    mock_dms.return_value = fake_danmakus

    fetch_danmaku.run("BV18acMz4ELL", tmp_path, force=True)

    mock_meta.assert_called_once()
    mock_dms.assert_called_once()
    assert (
        json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))["bvid"]
        == "BV18acMz4ELL"
    )


@patch("emoekg.stages.fetch_danmaku.fetch_all_danmakus")
@patch("emoekg.stages.fetch_danmaku.fetch_video_meta")
def test_run_partial_cache_triggers_refetch(
    mock_meta, mock_dms, fake_meta, fake_danmakus, tmp_path
):
    # Only meta.json exists (say last run died mid-way). Should NOT skip.
    (tmp_path / "meta.json").write_text('{"bvid":"partial"}', encoding="utf-8")
    mock_meta.return_value = fake_meta
    mock_dms.return_value = fake_danmakus

    fetch_danmaku.run("BV18acMz4ELL", tmp_path, force=False)

    mock_meta.assert_called_once()
    mock_dms.assert_called_once()


# ---------------------------------------------------------------------------
# Working dir creation
# ---------------------------------------------------------------------------


@patch("emoekg.stages.fetch_danmaku.fetch_all_danmakus")
@patch("emoekg.stages.fetch_danmaku.fetch_video_meta")
def test_run_creates_missing_working_dir(
    mock_meta, mock_dms, fake_meta, fake_danmakus, tmp_path
):
    target = tmp_path / "nested" / "out"  # does not exist yet
    mock_meta.return_value = fake_meta
    mock_dms.return_value = fake_danmakus

    fetch_danmaku.run("BV18acMz4ELL", target)

    assert target.is_dir()
    assert (target / "meta.json").exists()
