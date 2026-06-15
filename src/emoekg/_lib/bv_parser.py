"""BV id extraction from arbitrary user-supplied text.

UX researchers paste in whatever copy they got from a coworker: desktop URLs
with ``?share_source=``, ``b23.tv`` short links, mobile ``m.bilibili.com``
URLs, a bare BV id, or a chat sentence that happens to contain one. This
module returns the canonical ``BV``-prefixed id or raises loudly.

**Canonical form.** The 2-character ``BV`` prefix is always upper-cased. The
10-character body is returned *verbatim* because Bilibili's BV id body is
case-sensitive; we cannot recover the original case from a fully-lowercased
paste, so the caller gets whatever case they supplied.
"""
from __future__ import annotations

import re

__all__ = ["extract_bvid"]


# A BV id is exactly "BV" + 10 alphanumeric characters (Base58-ish alphabet,
# but we don't enforce the specific alphabet — any [A-Za-z0-9] is accepted to
# stay tolerant of future Bilibili changes). The `(?!\w)` lookahead prevents
# the regex from matching the first 10 chars of a longer token like
# "BV12345678901", which would otherwise swallow the trailing digit.
_BV_PATTERN = re.compile(
    r"(?<!\w)"           # left boundary: not preceded by a word char
    r"(BV[A-Za-z0-9]{10})"
    r"(?!\w)",           # right boundary: not followed by a word char
    re.IGNORECASE,
)


def extract_bvid(text: str) -> str:
    """Extract the first canonical BV id from ``text``.

    Accepts anything string-like — full URLs, short links, bare ids, or chat
    forwards with an id embedded mid-sentence.

    Args:
        text: Raw user input. Must be a ``str``.

    Returns:
        The canonical form ``"BV" + body`` (prefix upper-cased, body as-is).

    Raises:
        TypeError: if ``text`` is not a ``str``.
        ValueError: if ``text`` is empty/whitespace, or contains no BV id.
    """
    if not isinstance(text, str):
        raise TypeError(f"extract_bvid expected str, got {type(text).__name__}")

    if not text.strip():
        raise ValueError("empty input")

    m = _BV_PATTERN.search(text)
    if not m:
        raise ValueError(f"no BV id found in: {text!r}")

    raw = m.group(1)
    # Normalize prefix ("bv" -> "BV"); body case is preserved verbatim because
    # BV body is case-sensitive and we have no way to recover it from a paste
    # that's already been lower/uppercased.
    return "BV" + raw[2:]
