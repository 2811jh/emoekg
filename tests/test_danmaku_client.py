"""Tests for emoekg._lib.danmaku_client.

The real bilibili-api-python calls are fully mocked through the
``_get_video`` factory hook. Two public entry points are exercised:

  * :func:`fetch_video_meta` — async → sync wrapper + retry-on-exception,
    returns our normalized metadata schema.
  * :func:`fetch_all_danmakus` — walks 6-minute pages until exhausted,
    converts each protobuf danmaku into our flat dict, drops exact
    duplicates on ``(time, text, user_hash)``.

No real network or real event loop is touched.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from emoekg._lib.danmaku_client import fetch_all_danmakus, fetch_video_meta


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _fake_dm(*, progress_ms: int, content: str, mode: int = 1,
             color: int = 0xFFFFFF, fontsize: int = 25, midhash: str = "u0") -> SimpleNamespace:
    """Build a pseudo-protobuf danmaku attribute bag."""
    return SimpleNamespace(
        progress=progress_ms,
        content=content,
        mode=mode,
        color=color,
        fontsize=fontsize,
        midHash=midhash,
    )


def _fake_video_with_info(info: dict) -> MagicMock:
    v = MagicMock()

    async def _info():
        return info

    v.get_info = _info
    return v


def _fake_video_with_pages(pages: dict[int, list]) -> MagicMock:
    """Wire up `get_danmakus(page_index=N)` to a fixed pages dict.

    Any ``page_index`` not in ``pages`` returns ``[]`` (mimicking
    bilibili-api-python's silent out-of-range behavior).
    """
    v = MagicMock()

    async def _get(page_index: int):
        return pages.get(page_index, [])

    v.get_danmakus = _get
    return v


# ---------------------------------------------------------------------------
# fetch_video_meta — happy path + schema
# ---------------------------------------------------------------------------


@patch("emoekg._lib.danmaku_client._get_video")
def test_fetch_video_meta_happy(mock_get_video):
    mock_get_video.return_value = _fake_video_with_info(
        {
            "title": "测试视频",
            "owner": {"name": "TestUP"},
            "duration": 1080,
            "stat": {"view": 123_456},
            "cid": 999,
        }
    )

    meta = fetch_video_meta("BV18acMz4ELL")

    assert meta["bvid"] == "BV18acMz4ELL"
    assert meta["title"] == "测试视频"
    assert meta["up"] == "TestUP"
    assert meta["duration_sec"] == 1080
    assert meta["view_count"] == 123_456
    assert meta["cid"] == 999


@patch("emoekg._lib.danmaku_client._get_video")
def test_fetch_video_meta_missing_optional_fields_defaults(mock_get_video):
    # A malformed response (missing owner/stat) must NOT crash; defaults apply.
    mock_get_video.return_value = _fake_video_with_info(
        {"title": "bare", "duration": 60, "cid": 1}
    )

    meta = fetch_video_meta("BV18acMz4ELL")

    assert meta["up"] == ""
    assert meta["view_count"] == 0
    assert meta["duration_sec"] == 60


# ---------------------------------------------------------------------------
# fetch_video_meta — input validation
# ---------------------------------------------------------------------------


def test_fetch_video_meta_rejects_empty_bvid():
    with pytest.raises(ValueError):
        fetch_video_meta("")


def test_fetch_video_meta_rejects_non_string():
    with pytest.raises(TypeError):
        fetch_video_meta(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# fetch_video_meta — retry semantics
# ---------------------------------------------------------------------------


@patch("emoekg._lib.danmaku_client.time.sleep", new=lambda *_: None)
@patch("emoekg._lib.danmaku_client._get_video")
def test_fetch_video_meta_retries_until_success(mock_get_video):
    # First two calls blow up; third returns valid data.
    calls = {"n": 0}

    def factory(bvid):
        calls["n"] += 1
        v = MagicMock()

        async def _info():
            if calls["n"] < 3:
                raise ConnectionError("flaky network")
            return {"title": "ok", "duration": 1, "cid": 1}

        v.get_info = _info
        return v

    mock_get_video.side_effect = factory

    meta = fetch_video_meta("BV18acMz4ELL", retries=3)
    assert meta["title"] == "ok"
    assert calls["n"] == 3


@patch("emoekg._lib.danmaku_client.time.sleep", new=lambda *_: None)
@patch("emoekg._lib.danmaku_client._get_video")
def test_fetch_video_meta_raises_after_max_retries(mock_get_video):
    v = MagicMock()

    async def _boom():
        raise ConnectionError("forever flaky")

    v.get_info = _boom
    mock_get_video.return_value = v

    with pytest.raises(RuntimeError) as ei:
        fetch_video_meta("BV18acMz4ELL", retries=2)
    # The original cause must be chained for debuggability.
    assert isinstance(ei.value.__cause__, ConnectionError)


# ---------------------------------------------------------------------------
# fetch_all_danmakus — normalization (ms→s, schema)
# ---------------------------------------------------------------------------


@patch("emoekg._lib.danmaku_client._get_video")
def test_fetch_all_danmakus_single_page_normalization(mock_get_video):
    mock_get_video.return_value = _fake_video_with_pages(
        {0: [_fake_dm(progress_ms=12_340, content="test", mode=1,
                      color=0xFFFFFF, fontsize=25, midhash="u1")]}
    )

    dms = fetch_all_danmakus("BV18acMz4ELL", duration_sec=60)

    assert len(dms) == 1
    dm = dms[0]
    assert dm["time"] == pytest.approx(12.34)
    assert dm["text"] == "test"
    assert dm["mode"] == 1
    assert dm["color"] == 0xFFFFFF
    assert dm["fontsize"] == 25
    assert dm["user_hash"] == "u1"


# ---------------------------------------------------------------------------
# fetch_all_danmakus — multi-page paging
# ---------------------------------------------------------------------------


@patch("emoekg._lib.danmaku_client._get_video")
def test_fetch_all_danmakus_walks_multiple_pages(mock_get_video):
    # 20-min video → 4 pages of 6-min segments (+1 tail page → 5 attempts).
    # Pages 0, 1, 2 have danmakus; 3/4 are empty.
    pages = {
        0: [_fake_dm(progress_ms=10_000, content="p0", midhash="u1")],
        1: [_fake_dm(progress_ms=400_000, content="p1", midhash="u2")],
        2: [_fake_dm(progress_ms=800_000, content="p2", midhash="u3")],
    }
    mock_get_video.return_value = _fake_video_with_pages(pages)

    dms = fetch_all_danmakus("BV18acMz4ELL", duration_sec=20 * 60)

    assert [d["text"] for d in dms] == ["p0", "p1", "p2"]


@patch("emoekg._lib.danmaku_client._get_video")
def test_fetch_all_danmakus_zero_duration_short_circuits(mock_get_video):
    # duration 0 means "no video loaded yet" or "live stream with 0 playback"
    # — don't hit the network at all; return [].
    fake = MagicMock()
    mock_get_video.return_value = fake

    dms = fetch_all_danmakus("BV18acMz4ELL", duration_sec=0)

    assert dms == []
    fake.get_danmakus.assert_not_called()


# ---------------------------------------------------------------------------
# fetch_all_danmakus — dedup semantics
# ---------------------------------------------------------------------------


@patch("emoekg._lib.danmaku_client._get_video")
def test_fetch_all_danmakus_dedups_exact_triples(mock_get_video):
    # Same user, same time, same text across two pages → collapse to one.
    # Different color/mode don't matter — danmaku equality is (time,text,user).
    dup = _fake_dm(progress_ms=5_000, content="哈哈", midhash="userA")
    dup_alt_color = _fake_dm(
        progress_ms=5_000, content="哈哈", midhash="userA", color=0xFF0000
    )
    distinct_text = _fake_dm(progress_ms=5_000, content="嘻嘻", midhash="userA")
    distinct_user = _fake_dm(progress_ms=5_000, content="哈哈", midhash="userB")

    mock_get_video.return_value = _fake_video_with_pages(
        {0: [dup, dup_alt_color, distinct_text, distinct_user]}
    )

    dms = fetch_all_danmakus("BV18acMz4ELL", duration_sec=60)

    # Expect: [dup (哈哈,userA), 嘻嘻/userA, 哈哈/userB] — alt_color folded.
    assert len(dms) == 3
    signatures = {(d["time"], d["text"], d["user_hash"]) for d in dms}
    assert signatures == {
        (5.0, "哈哈", "userA"),
        (5.0, "嘻嘻", "userA"),
        (5.0, "哈哈", "userB"),
    }


# ---------------------------------------------------------------------------
# fetch_all_danmakus — input validation
# ---------------------------------------------------------------------------


def test_fetch_all_danmakus_rejects_empty_bvid():
    with pytest.raises(ValueError):
        fetch_all_danmakus("", duration_sec=60)


def test_fetch_all_danmakus_rejects_negative_duration():
    with pytest.raises(ValueError):
        fetch_all_danmakus("BV18acMz4ELL", duration_sec=-1)


# ---------------------------------------------------------------------------
# fetch_all_danmakus — retry on page failure
# ---------------------------------------------------------------------------


@patch("emoekg._lib.danmaku_client.time.sleep", new=lambda *_: None)
@patch("emoekg._lib.danmaku_client._get_video")
def test_fetch_all_danmakus_retries_single_page(mock_get_video):
    # Page 0 fails twice then succeeds. We must NOT skip the page.
    call_count = {"n": 0}

    v = MagicMock()

    async def _get(page_index: int):
        if page_index != 0:
            return []
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise TimeoutError("slow")
        return [_fake_dm(progress_ms=1_000, content="eventually", midhash="u1")]

    v.get_danmakus = _get
    mock_get_video.return_value = v

    dms = fetch_all_danmakus("BV18acMz4ELL", duration_sec=60, retries=3)
    assert [d["text"] for d in dms] == ["eventually"]
    assert call_count["n"] == 3
