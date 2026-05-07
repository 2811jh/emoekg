"""Tests for emoekg._lib.time_utils.

These utilities normalize Bilibili danmaku progress (milliseconds) into seconds
and convert between HH:MM:SS display strings and numeric seconds. All arithmetic
must be floating-point stable for short videos (seconds) and long streams
(hours), so tests pin down boundary behaviour.
"""
from __future__ import annotations

import math

import pytest


# ---------------------------------------------------------------------------
# parse_timestamp: Bilibili `progress` (ms int) -> seconds (float)
# ---------------------------------------------------------------------------


def test_parse_timestamp_from_milliseconds_int():
    from emoekg._lib.time_utils import parse_timestamp

    assert parse_timestamp(0) == 0.0
    assert parse_timestamp(1000) == 1.0
    assert math.isclose(parse_timestamp(1234), 1.234, rel_tol=0, abs_tol=1e-9)


def test_parse_timestamp_accepts_float_milliseconds():
    from emoekg._lib.time_utils import parse_timestamp

    # Some sources (e.g. offline XML export) expose fractional ms.
    assert math.isclose(parse_timestamp(1500.5), 1.5005, rel_tol=0, abs_tol=1e-9)


def test_parse_timestamp_rejects_negative():
    from emoekg._lib.time_utils import parse_timestamp

    with pytest.raises(ValueError):
        parse_timestamp(-1)


def test_parse_timestamp_rejects_none():
    from emoekg._lib.time_utils import parse_timestamp

    with pytest.raises(TypeError):
        parse_timestamp(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# format_hms: float seconds -> "HH:MM:SS"
# ---------------------------------------------------------------------------


def test_format_hms_zero():
    from emoekg._lib.time_utils import format_hms

    assert format_hms(0) == "00:00:00"


def test_format_hms_sub_minute():
    from emoekg._lib.time_utils import format_hms

    assert format_hms(59) == "00:00:59"


def test_format_hms_basic():
    from emoekg._lib.time_utils import format_hms

    # 1h 2m 3s
    assert format_hms(3723) == "01:02:03"


def test_format_hms_truncates_subseconds():
    from emoekg._lib.time_utils import format_hms

    # Display should floor fractional seconds (no rounding up across second).
    assert format_hms(59.9) == "00:00:59"
    assert format_hms(3723.9) == "01:02:03"


def test_format_hms_hours_above_24_are_kept_verbatim():
    from emoekg._lib.time_utils import format_hms

    # Some VODs (compilations) exceed 24h; we do NOT wrap.
    assert format_hms(25 * 3600 + 1) == "25:00:01"


def test_format_hms_rejects_negative():
    from emoekg._lib.time_utils import format_hms

    with pytest.raises(ValueError):
        format_hms(-0.5)


# ---------------------------------------------------------------------------
# parse_hms: display string -> seconds
# ---------------------------------------------------------------------------


def test_parse_hms_full():
    from emoekg._lib.time_utils import parse_hms

    assert parse_hms("01:02:03") == 3723.0


def test_parse_hms_accepts_single_digit_hour():
    from emoekg._lib.time_utils import parse_hms

    assert parse_hms("1:02:03") == 3723.0


def test_parse_hms_mmss_shorthand():
    from emoekg._lib.time_utils import parse_hms

    # MM:SS treated as 0 hours.
    assert parse_hms("02:03") == 123.0


def test_parse_hms_pure_seconds():
    from emoekg._lib.time_utils import parse_hms

    assert parse_hms("3723") == 3723.0
    assert parse_hms("0") == 0.0


def test_parse_hms_strips_whitespace():
    from emoekg._lib.time_utils import parse_hms

    assert parse_hms("  00:01:30  ") == 90.0


def test_parse_hms_rejects_garbage():
    from emoekg._lib.time_utils import parse_hms

    for bad in ["", "abc", "1:2:3:4", "--:--", "1:2a:3"]:
        with pytest.raises(ValueError):
            parse_hms(bad)


# ---------------------------------------------------------------------------
# clamp_seconds
# ---------------------------------------------------------------------------


def test_clamp_seconds_within_range_is_identity():
    from emoekg._lib.time_utils import clamp_seconds

    assert clamp_seconds(30.0, 100.0) == 30.0


def test_clamp_seconds_below_zero_becomes_zero():
    from emoekg._lib.time_utils import clamp_seconds

    assert clamp_seconds(-5.0, 100.0) == 0.0


def test_clamp_seconds_above_total_becomes_total():
    from emoekg._lib.time_utils import clamp_seconds

    assert clamp_seconds(200.0, 100.0) == 100.0


def test_clamp_seconds_rejects_negative_total():
    from emoekg._lib.time_utils import clamp_seconds

    with pytest.raises(ValueError):
        clamp_seconds(10.0, -1.0)


# ---------------------------------------------------------------------------
# round-trip sanity: format_hms(parse_hms(x)) == x (for normalized input)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["00:00:00", "00:00:59", "00:01:30", "01:02:03", "10:59:59"],
)
def test_format_parse_round_trip(text):
    from emoekg._lib.time_utils import format_hms, parse_hms

    assert format_hms(parse_hms(text)) == text
