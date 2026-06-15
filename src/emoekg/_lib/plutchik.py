"""Plutchik 8-dimension emotion schema for emoekg.

Everything downstream of the Agent scoring stage — turnpoint detection,
evidence picking, report rendering — derives its notion of "emotion" from
this module. Four public objects:

* :data:`DIMENSIONS` — ordered list of the 8 primitive emotions. The order is
  **stable** and is used as the x-axis of the radar chart and as the tie-break
  when multiple dimensions share the same score.
* :data:`COLORS` — mapping ``dim -> "#RRGGBB"``, used by ECharts to paint each
  layer of the emotional ECG. Colors are unique to keep the chart readable.
* :data:`KEYWORDS` — Chinese danmaku expressions typical of each emotion.
  Consumed by :mod:`emoekg._lib.evidence_picker` *only* (the Agent scoring
  stage must NOT rely on naive keyword matching).
* :func:`validate_score_entry` — strict validator for the per-chunk rows the
  Agent produces in ``scores.json``.
* :func:`get_dominant_dimension` — pick the emotion with the max score for a
  given chunk, tie-broken by :data:`DIMENSIONS` order.
"""
from __future__ import annotations

from typing import Mapping, Sequence

__all__ = [
    "DIMENSIONS",
    "COLORS",
    "KEYWORDS",
    "validate_score_entry",
    "get_dominant_dimension",
]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

DIMENSIONS: list[str] = [
    "joy",
    "trust",
    "fear",
    "surprise",
    "sadness",
    "disgust",
    "anger",
    "anticipation",
]

# Plutchik-wheel inspired palette. Each entry is a 7-char hex triplet. All
# colors must be unique — sharing a hue would make the stacked ECG ambiguous.
COLORS: Mapping[str, str] = {
    "joy":          "#F4D03F",  # gold — high arousal positive
    "trust":        "#52BE80",  # green — calm positive
    "fear":         "#566573",  # slate — tension
    "surprise":     "#F39C12",  # orange — alert
    "sadness":      "#5499C7",  # blue — low arousal negative
    "disgust":      "#8E44AD",  # purple — aversion
    "anger":        "#C0392B",  # red — high arousal negative
    "anticipation": "#EB984E",  # coral — expectancy
}

# Bilibili danmaku keyword dictionaries. These are intentionally **disjoint**
# across dimensions so that `evidence_picker` can attribute a matched danmaku
# to exactly one emotion.
#
# NOTE: these are hints for evidence selection only. They are NEVER used by
# the Agent scoring stage, which operates on semantics, not lexicons.
KEYWORDS: Mapping[str, Sequence[str]] = {
    "joy":          ["哈哈", "233", "笑死", "好活", "太乐", "笑不活", "笑疯", "爆笑"],
    "trust":        ["稳了", "专业", "yyds", "靠谱", "实锤", "大佬", "值得信任"],
    "fear":         ["害怕", "瑟瑟发抖", "要出事", "慌", "不敢", "胆小", "吓人"],
    "surprise":     ["卧槽", "啊这", "???", "??", "离谱", "什么情况", "震惊", "离大谱"],
    "sadness":      ["破防", "难过", "emo", "泪目", "心疼", "哭了", "想哭", "好惨"],
    "disgust":      ["恶心", "作呕", "下头", "恶臭", "辣眼", "反胃", "呕"],
    "anger":        ["气死", "辣鸡", "垃圾", "退游", "策划死", "滚", "骂人"],
    "anticipation": ["等你", "快更新", "下一集", "蹲", "求出", "催更", "期待"],
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_META_FIELDS = ("chunk_id", "time_start", "time_end", "n_danmaku", "note")


def validate_score_entry(entry: Mapping) -> None:
    """Raise :class:`ValueError` if ``entry`` is not a well-formed score row.

    The Agent scoring stage writes one such row per chunk. A row must contain:

    * the 5 meta fields ``chunk_id`` / ``time_start`` / ``time_end`` /
      ``n_danmaku`` / ``note``
    * all 8 :data:`DIMENSIONS`, each an ``int`` in ``[0, 10]``

    Any missing key, out-of-range value, or non-``int`` score (including
    ``bool``, ``float``, or numeric strings) is a hard failure — we prefer
    loudly rejecting a sloppy Agent response over silently producing a chart
    built on junk data.
    """
    required = set(_META_FIELDS) | set(DIMENSIONS)
    missing = required - set(entry.keys())
    if missing:
        raise ValueError(f"missing keys: {sorted(missing)}")

    for d in DIMENSIONS:
        v = entry[d]
        # bool is an int subclass in Python — reject it explicitly, since a
        # "True" score is semantically meaningless for an emotion intensity.
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(
                f"{d}={v!r} is not an int (got {type(v).__name__}); "
                "scores must be int in range [0, 10]"
            )
        if v < 0 or v > 10:
            raise ValueError(f"{d}={v} out of range [0, 10]")


# ---------------------------------------------------------------------------
# Dominant dimension
# ---------------------------------------------------------------------------


def get_dominant_dimension(entry: Mapping) -> str:
    """Return the :data:`DIMENSIONS` entry with the highest score in ``entry``.

    Missing dimensions count as 0. Ties are broken by :data:`DIMENSIONS` order
    (i.e. the earliest dimension in the canonical list wins), which keeps the
    report deterministic when an Agent scores, say, joy and trust both as 5.
    """
    # `max` with `key=` returns the *first* element achieving the max, which
    # naturally honours DIMENSIONS order for ties.
    return max(DIMENSIONS, key=lambda d: entry.get(d, 0))
