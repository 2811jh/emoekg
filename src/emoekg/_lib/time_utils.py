"""Time/duration helpers for emoekg.

All danmaku timestamps in emoekg are normalized to **seconds (float)** once they
enter the pipeline. Bilibili's protobuf field `progress` is an int in
milliseconds, so the fetch stage calls :func:`parse_timestamp` to convert.

Display uses ``HH:MM:SS`` (hours are *not* wrapped at 24; compilations can
exceed a day). :func:`parse_hms` is the inverse and accepts several shorthand
forms because users copy-paste timestamps from YouTube/Bilibili comments.
"""
from __future__ import annotations

import re
from typing import Union

Number = Union[int, float]

__all__ = [
    "parse_timestamp",
    "format_hms",
    "parse_hms",
    "clamp_seconds",
]


# ---------------------------------------------------------------------------
# Bilibili progress(ms) -> seconds(float)
# ---------------------------------------------------------------------------


def parse_timestamp(progress_ms: Number) -> float:
    """Convert a Bilibili `progress` field (milliseconds) to seconds.

    Raises:
        TypeError: if ``progress_ms`` is not int or float.
        ValueError: if ``progress_ms`` is negative.
    """
    if not isinstance(progress_ms, (int, float)) or isinstance(progress_ms, bool):
        raise TypeError(
            f"parse_timestamp expected int/float, got {type(progress_ms).__name__}"
        )
    if progress_ms < 0:
        raise ValueError(f"progress_ms must be >= 0, got {progress_ms}")
    return float(progress_ms) / 1000.0


# ---------------------------------------------------------------------------
# seconds(float) -> "HH:MM:SS"
# ---------------------------------------------------------------------------


def format_hms(seconds: Number) -> str:
    """Format ``seconds`` as ``HH:MM:SS`` with *floored* subseconds.

    Hours are never wrapped modulo 24 — compilations can be >24h, and UX
    researchers need the raw offset into the video.

    Raises:
        ValueError: if ``seconds`` is negative.
    """
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
        raise TypeError(f"format_hms expected int/float, got {type(seconds).__name__}")
    if seconds < 0:
        raise ValueError(f"seconds must be >= 0, got {seconds}")

    total = int(seconds)  # floor to whole seconds for display
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# "HH:MM:SS" / "MM:SS" / "S" -> seconds(float)
# ---------------------------------------------------------------------------

# Match strict H:M:S-style tokens: each segment is one or more digits.
_HMS_RE = re.compile(r"^\d+(?::\d+){0,2}$")


def parse_hms(text: str) -> float:
    """Parse ``HH:MM:SS`` / ``H:MM:SS`` / ``MM:SS`` / ``S`` into seconds (float).

    Whitespace around the token is stripped. Any other format (letters, too
    many colons, partial digits) raises :class:`ValueError`.
    """
    if not isinstance(text, str):
        raise ValueError(f"parse_hms expected str, got {type(text).__name__}")

    token = text.strip()
    if not token or not _HMS_RE.match(token):
        raise ValueError(f"not a valid HH:MM:SS / MM:SS / seconds string: {text!r}")

    parts = [int(p) for p in token.split(":")]
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    else:  # len == 1 — pure seconds
        return float(parts[0])

    return float(h * 3600 + m * 60 + s)


# ---------------------------------------------------------------------------
# clamp to [0, total]
# ---------------------------------------------------------------------------


def clamp_seconds(seconds: Number, total: Number) -> float:
    """Clamp ``seconds`` into ``[0, total]``.

    Used when mapping a detected turnpoint back onto the video timeline: the
    chunk midpoint may slightly exceed the reported video duration because of
    rounding at the last slice boundary.

    Raises:
        ValueError: if ``total`` is negative.
    """
    if total < 0:
        raise ValueError(f"total must be >= 0, got {total}")
    if seconds < 0:
        return 0.0
    if seconds > total:
        return float(total)
    return float(seconds)
