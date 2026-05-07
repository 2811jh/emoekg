"""Tests for emoekg._lib.bv_parser.

Covers UX-research hand-off scenarios: researchers paste in whatever copy they
got from a coworker — Bilibili app share (b23.tv), desktop URL with query
params, mobile URL, bare BV id, or a slightly corrupted form. The parser must
either return a canonical BV id or fail loudly.
"""
from __future__ import annotations

import pytest

from emoekg._lib.bv_parser import extract_bvid


# ---------------------------------------------------------------------------
# Valid inputs — all must return the canonical BV id.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Desktop web
        ("https://www.bilibili.com/video/BV18acMz4ELL", "BV18acMz4ELL"),
        ("https://www.bilibili.com/video/BV18acMz4ELL/", "BV18acMz4ELL"),
        (
            "https://www.bilibili.com/video/BV18acMz4ELL/?share_source=copy_web",
            "BV18acMz4ELL",
        ),
        # Short link
        ("https://b23.tv/BV18acMz4ELL", "BV18acMz4ELL"),
        # Mobile
        ("https://m.bilibili.com/video/BV18acMz4ELL", "BV18acMz4ELL"),
        # Bare id
        ("BV18acMz4ELL", "BV18acMz4ELL"),
        # Prefix-only case normalization (body case is *not* altered, since
        # BV body is case-sensitive and we have no way to recover it).
        ("bv18acMz4ELL", "BV18acMz4ELL"),
        # Embedded in surrounding text (chat forwards)
        ("快看这个 BV18acMz4ELL 有意思", "BV18acMz4ELL"),
        # With hash fragment
        ("https://www.bilibili.com/video/BV18acMz4ELL#reply123", "BV18acMz4ELL"),
    ],
)
def test_valid_inputs(raw, expected):
    assert extract_bvid(raw) == expected


# ---------------------------------------------------------------------------
# Invalid / ambiguous inputs — must raise ValueError.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid",
    [
        "",
        "   ",
        "not-a-url",
        "https://youtube.com/watch?v=abc",
        "BV",            # too short
        "BV12",          # too short
        "BV123456789",   # 9 chars body (needs 10)
        "AV1234567",     # legacy av id, we only accept BV
    ],
)
def test_invalid_raises(invalid):
    with pytest.raises(ValueError):
        extract_bvid(invalid)


def test_non_string_raises_type_error():
    with pytest.raises(TypeError):
        extract_bvid(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        extract_bvid(12345)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# First-match semantics: if a chat message contains multiple BV ids, we return
# the first one encountered. This is the least-surprising policy for a UX
# researcher pasting a single line with a primary link and a reply link.
# ---------------------------------------------------------------------------


def test_multiple_bvids_returns_first():
    text = "主视频 BV18acMz4ELL 对比 BV1234567890"
    assert extract_bvid(text) == "BV18acMz4ELL"


# ---------------------------------------------------------------------------
# Canonical form is idempotent: extract_bvid(extract_bvid(x)) == extract_bvid(x)
# ---------------------------------------------------------------------------


def test_idempotent_on_canonical_id():
    once = extract_bvid("https://www.bilibili.com/video/BV18acMz4ELL/")
    twice = extract_bvid(once)
    assert once == twice == "BV18acMz4ELL"
