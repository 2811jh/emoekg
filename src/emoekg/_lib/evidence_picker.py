"""Pick supporting-evidence danmakus for a turnpoint's dominant dimension.

When we surface a turnpoint in the final HTML report, we want 3–5 representative
danmakus next to it that convince the reader the emotion label is correct.
Three prioritization tiers, applied after deduplication:

  1. **Keyword match.** Contains one or more entries from
     :data:`emoekg._lib.plutchik.KEYWORDS[dimension]`. Higher match count wins.
  2. **Length.** Longer danmakus carry more context than reactive "哈哈" / "666".
  3. **Time.** Earlier wins, so evidence reads in playback order.

Dedup key is the raw ``text`` string — duplicate content from different users
(a viral "666" catch-phrase) collapses to a single instance so it doesn't
crowd out other evidence.
"""
from __future__ import annotations

from emoekg._lib.plutchik import KEYWORDS

__all__ = ["pick_evidence"]


def pick_evidence(
    danmakus: list[dict],
    dimension: str,
    target: int = 5,
) -> list[dict]:
    """Select up to ``target`` danmakus exemplifying ``dimension``.

    Args:
        danmakus: Candidate danmakus (typically all danmakus in a turnpoint's
            chunk plus a handful of chunks on either side).
        dimension: One of :data:`emoekg._lib.plutchik.DIMENSIONS`. If an
            unknown name is passed we simply have no keywords to boost, so
            ranking degenerates gracefully to length-then-time.
        target: Upper bound on returned items. Fewer are returned if there
            aren't enough unique texts.

    Returns:
        A list of the original danmaku dicts (no copy), ordered by the
        ranking tiers above.
    """
    keywords = KEYWORDS.get(dimension, ())

    # First pass: dedup on text, compute per-item ranking score.
    seen_texts: set[str] = set()
    scored: list[tuple[int, int, float, dict]] = []
    for d in danmakus:
        text = d["text"]
        if text in seen_texts:
            continue
        seen_texts.add(text)

        kw_hits = sum(1 for k in keywords if k in text)
        scored.append((kw_hits, len(text), d["time"], d))

    # Rank: keyword hits DESC, length DESC, time ASC.
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]))

    return [entry[3] for entry in scored[:target]]
