"""Tests for emoekg._lib.evidence_picker.

`pick_evidence` chooses up to ``target`` danmakus to attach to a turnpoint as
supporting evidence. The selection policy has three tiers:

  1. Keyword match (from :data:`emoekg._lib.plutchik.KEYWORDS`) for the
     dimension in question — these carry the strongest signal.
  2. Length — longer danmakus tend to carry more context than 2-char reactions.
  3. Time — earlier danmakus win ties, so evidence reads chronologically.

Deduplication runs before ranking: same-text duplicates collapse, even across
different users (otherwise a viral "666" floods every turnpoint).
"""
from __future__ import annotations

from emoekg._lib.evidence_picker import pick_evidence


def _dm(t: float, text: str, user: str = "u") -> dict:
    return {
        "time": t, "text": text, "mode": 1,
        "color": 0xFFFFFF, "fontsize": 25, "user_hash": user,
    }


# ---------------------------------------------------------------------------
# Keyword priority
# ---------------------------------------------------------------------------


def test_prefers_keyword_matches_for_dimension():
    danmakus = [
        _dm(1.0, "666", "u1"),
        _dm(2.0, "我直接退游", "u2"),
        _dm(3.0, "策划死妈", "u3"),
        _dm(4.0, "辣鸡游戏", "u4"),
        _dm(5.0, "真的气死了", "u5"),
        _dm(6.0, "好的", "u6"),
        _dm(7.0, "垃圾策划", "u7"),
    ]
    picked = pick_evidence(danmakus, dimension="anger", target=5)
    texts = [d["text"] for d in picked]

    assert "666" not in texts
    assert "好的" not in texts
    assert len(picked) == 5


def test_keyword_tier_beats_length_tier():
    # A long non-matching danmaku vs a short keyword-matching one.
    danmakus = [
        _dm(1.0, "这段剧情铺垫得真的很细腻节奏也刚刚好", "u1"),
        _dm(2.0, "退游", "u2"),  # short but keyword-matches anger
    ]
    picked = pick_evidence(danmakus, dimension="anger", target=1)
    assert picked[0]["text"] == "退游"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_dedups_exact_text_across_users():
    danmakus = [
        _dm(1.0, "退游", "u1"),
        _dm(2.0, "退游", "u1"),  # same user, same text
        _dm(3.0, "退游", "u2"),  # different user, same text
        _dm(4.0, "气死", "u3"),
    ]
    picked = pick_evidence(danmakus, dimension="anger", target=5)
    texts = [d["text"] for d in picked]
    assert texts.count("退游") == 1
    assert "气死" in texts


# ---------------------------------------------------------------------------
# Length fallback when no keyword hits
# ---------------------------------------------------------------------------


def test_falls_back_to_longest_when_no_keyword_hits():
    danmakus = [
        _dm(1.0, "a", "u1"),
        _dm(2.0, "这条弹幕很长描述了很多东西", "u2"),
        _dm(3.0, "短", "u3"),
        _dm(4.0, "也还行吧", "u4"),
    ]
    picked = pick_evidence(danmakus, dimension="anger", target=2)
    # None match "anger" keywords → order purely by length (desc), then time.
    assert picked[0]["text"].startswith("这条弹幕")
    assert picked[1]["text"] == "也还行吧"


# ---------------------------------------------------------------------------
# Target bounds
# ---------------------------------------------------------------------------


def test_returns_at_most_target_items():
    danmakus = [_dm(float(i), f"退游 x{i}", f"u{i}") for i in range(10)]
    picked = pick_evidence(danmakus, dimension="anger", target=3)
    assert len(picked) == 3


def test_returns_fewer_if_not_enough_unique():
    danmakus = [_dm(1.0, "退游", "u1"), _dm(2.0, "退游", "u2")]
    picked = pick_evidence(danmakus, dimension="anger", target=5)
    assert len(picked) == 1  # second "退游" is a text-dup


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


def test_empty_danmakus_returns_empty():
    assert pick_evidence([], dimension="joy", target=5) == []


def test_unknown_dimension_falls_back_to_length_ordering():
    # No keyword list for this name → tier 1 always yields 0 → length wins.
    danmakus = [
        _dm(1.0, "short", "u1"),
        _dm(2.0, "a much longer danmaku here", "u2"),
    ]
    picked = pick_evidence(danmakus, dimension="nonexistent", target=1)
    assert picked[0]["text"].startswith("a much longer")


def test_time_breaks_tie_within_same_tier():
    # Same keyword hits, same length → earlier time wins.
    danmakus = [
        _dm(5.0, "退游", "u1"),
        _dm(1.0, "退游", "u2"),  # earlier but text-dup
    ]
    # After dedup only one survives — the first occurrence (t=5.0).
    picked = pick_evidence(danmakus, dimension="anger", target=1)
    assert picked[0]["time"] == 5.0


def test_preserves_full_danmaku_dicts():
    # The picker returns the original dicts (not a subset) so downstream
    # renderers can access user_hash / color / etc.
    dm = _dm(1.0, "退游", "u1")
    picked = pick_evidence([dm], dimension="anger", target=1)
    assert picked[0] is dm
