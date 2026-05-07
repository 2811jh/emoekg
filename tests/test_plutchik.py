"""Tests for emoekg._lib.plutchik.

Locks down:
  - DIMENSIONS is exactly the 8 Plutchik primitives, in a stable order
  - every dimension has a color (hex) and at least 3 Bilibili keywords
  - validate_score_entry is strict: range [0,10], all 8 dims present, all meta
    fields present, no silent coercion of floats/strings into int scores
  - get_dominant_dimension picks the max, ties resolved by DIMENSIONS order
"""
from __future__ import annotations

import pytest

from emoekg._lib.plutchik import (
    COLORS,
    DIMENSIONS,
    KEYWORDS,
    get_dominant_dimension,
    validate_score_entry,
)


# ---------------------------------------------------------------------------
# Schema shape
# ---------------------------------------------------------------------------


def test_dimensions_is_list_of_8():
    # The report pipeline relies on a *stable order* (first = "joy"), not just
    # set membership — that's the order used for radar plots and color legend.
    assert isinstance(DIMENSIONS, list)
    assert len(DIMENSIONS) == 8
    assert DIMENSIONS[0] == "joy"


def test_dimensions_match_plutchik_primitives():
    assert set(DIMENSIONS) == {
        "joy", "trust", "fear", "surprise",
        "sadness", "disgust", "anger", "anticipation",
    }


def test_dimensions_has_no_duplicates():
    assert len(set(DIMENSIONS)) == len(DIMENSIONS)


# ---------------------------------------------------------------------------
# COLORS
# ---------------------------------------------------------------------------


def test_colors_cover_all_dimensions():
    for d in DIMENSIONS:
        assert d in COLORS, f"missing color for dimension {d!r}"


def test_colors_are_hex_triplets():
    for d, hexv in COLORS.items():
        assert isinstance(hexv, str)
        assert hexv.startswith("#"), f"{d}: color must start with # (got {hexv!r})"
        assert len(hexv) == 7, f"{d}: expected #RRGGBB (got {hexv!r})"
        int(hexv[1:], 16)  # raises ValueError if not valid hex


def test_colors_are_unique():
    # Chart readability breaks if two dimensions share a hue.
    assert len(set(COLORS.values())) == len(COLORS)


# ---------------------------------------------------------------------------
# KEYWORDS
# ---------------------------------------------------------------------------


def test_keywords_cover_all_dimensions():
    for d in DIMENSIONS:
        assert d in KEYWORDS, f"missing keywords for dimension {d!r}"


def test_keywords_have_at_least_three_entries():
    for d, words in KEYWORDS.items():
        assert len(words) >= 3, f"{d}: need >=3 keywords, got {words!r}"


def test_keywords_are_nonempty_strings():
    for d, words in KEYWORDS.items():
        for w in words:
            assert isinstance(w, str) and w, f"{d}: empty/non-str keyword: {w!r}"


# ---------------------------------------------------------------------------
# validate_score_entry
# ---------------------------------------------------------------------------


def _ok_entry(**overrides):
    base = {
        "chunk_id": "C001",
        "time_start": 0,
        "time_end": 15,
        "n_danmaku": 42,
        "joy": 7, "trust": 2, "fear": 0, "surprise": 4,
        "sadness": 0, "disgust": 0, "anger": 0, "anticipation": 8,
        "note": "ok",
    }
    base.update(overrides)
    return base


def test_validate_score_entry_ok():
    validate_score_entry(_ok_entry())  # must not raise


def test_validate_score_entry_allows_all_zero():
    # A "SPARSE" / silent chunk is a valid outcome.
    validate_score_entry(_ok_entry(**{d: 0 for d in DIMENSIONS}, note="SPARSE"))


def test_validate_score_entry_missing_dim():
    entry = _ok_entry()
    del entry["anger"]
    with pytest.raises(ValueError) as ei:
        validate_score_entry(entry)
    assert "missing" in str(ei.value).lower()


def test_validate_score_entry_missing_meta_field():
    entry = _ok_entry()
    del entry["n_danmaku"]
    with pytest.raises(ValueError) as ei:
        validate_score_entry(entry)
    assert "missing" in str(ei.value).lower()


@pytest.mark.parametrize("bad_value", [-1, 11, 100])
def test_validate_score_entry_out_of_range(bad_value):
    entry = _ok_entry(joy=bad_value)
    with pytest.raises(ValueError) as ei:
        validate_score_entry(entry)
    msg = str(ei.value).lower()
    assert "range" in msg or "0" in msg or "10" in msg


@pytest.mark.parametrize("bad_value", [3.5, "7", True, None])
def test_validate_score_entry_rejects_non_int(bad_value):
    # JSON "7" from a sloppy agent response must NOT be silently accepted.
    # bool is rejected even though it's an int subclass (0/1 would pass range
    # check but semantically a True score is nonsense).
    entry = _ok_entry(joy=bad_value)
    with pytest.raises(ValueError):
        validate_score_entry(entry)


# ---------------------------------------------------------------------------
# get_dominant_dimension
# ---------------------------------------------------------------------------


def test_dominant_dimension_unique_max():
    entry = {
        "joy": 2, "trust": 1, "fear": 0, "surprise": 3,
        "sadness": 0, "disgust": 0, "anger": 8, "anticipation": 1,
    }
    assert get_dominant_dimension(entry) == "anger"


def test_dominant_dimension_tie_resolves_by_dimensions_order():
    # joy and trust both 5 → joy wins because it appears earlier in DIMENSIONS.
    entry = {d: 0 for d in DIMENSIONS}
    entry["joy"] = 5
    entry["trust"] = 5
    assert get_dominant_dimension(entry) == "joy"


def test_dominant_dimension_all_zero_still_returns_first():
    entry = {d: 0 for d in DIMENSIONS}
    assert get_dominant_dimension(entry) == DIMENSIONS[0]
