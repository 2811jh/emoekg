"""Stage 2 — slice danmakus into adaptive windows, render chunks.md prompt.

Input:   ``<working_dir>/meta.json`` + ``<working_dir>/danmaku.json`` (Stage 1).
Outputs (written into ``working_dir``):
    * ``chunks.md``    — Jinja2-rendered prompt for the Agent
    * ``scores.json``  — empty list skeleton, Agent fills in Stage 3
    * ``insights.json`` — empty skeleton for the Agent's executive summary,
      also filled in Stage 3 (see ``docs/scoring_rubric.md`` §6)

Design notes:
  * Window size is chosen by :func:`emoekg._lib.adaptive_window.compute_window_size`
    (targets ~90 chunks, snapped to friendly values).
  * Chunks with ≥151 danmakus are **down-sampled** to 150 (head 30, random
    middle 90, tail 30). The full count is preserved in the header line so
    the Agent knows the chunk is dense even though it only sees a sample.
  * Sampling is **deterministic**: we seed a local RNG from the chunk_id so
    re-running Stage 2 on the same data produces byte-identical chunks.md.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from emoekg._lib.adaptive_window import compute_window_size, slice_by_window
from emoekg._lib.time_utils import format_hms

__all__ = ["run", "main"]

# Chunks with more than this many danmakus get down-sampled in the prompt.
_DENSE_THRESHOLD = 150
_DENSE_HEAD = 30
_DENSE_MID = 90
_DENSE_TAIL = 30


def _sample_dense(danmakus: list[dict], seed: str) -> list[dict]:
    """Down-sample a dense chunk to 150 danmakus: head 30 + mid 90 + tail 30.

    Sampling is deterministic — same input + same ``seed`` → same output.
    Middle samples are re-sorted by ``time`` after random picking to keep the
    prompt chronologically readable.
    """
    if len(danmakus) <= _DENSE_THRESHOLD:
        return danmakus

    head = danmakus[:_DENSE_HEAD]
    tail = danmakus[-_DENSE_TAIL:]
    mid_pool = danmakus[_DENSE_HEAD:-_DENSE_TAIL]

    rng = random.Random(seed)
    k = min(_DENSE_MID, len(mid_pool))
    mid = rng.sample(mid_pool, k)
    mid.sort(key=lambda d: d["time"])

    return head + mid + tail


def _load_template():
    """Return the Jinja2 ``chunks_prompt.md.j2`` template.

    We mount the Jinja ``FileSystemLoader`` at the packaged ``emoekg/templates``
    directory so the template renders identically whether emoekg is run from
    a source checkout or a pip-installed wheel.
    """
    template_dir = Path(str(files("emoekg.templates")))
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("chunks_prompt.md.j2")


def run(working_dir: Path | str, force: bool = False) -> None:
    """Execute Stage 2.

    Args:
        working_dir: Directory containing ``meta.json`` + ``danmaku.json``.
            Outputs (``chunks.md`` + ``scores.json``) are written here.
        force: Ignore existing outputs and re-render.
    """
    working_dir = Path(working_dir)
    chunks_md = working_dir / "chunks.md"
    scores_json = working_dir / "scores.json"
    insights_json = working_dir / "insights.json"

    # "Skip" requires all three artifacts present — otherwise we re-run so
    # older working dirs (pre-insights protocol) can be upgraded in place.
    if (
        not force
        and chunks_md.exists()
        and scores_json.exists()
        and insights_json.exists()
    ):
        print(
            f"[Stage 2] SKIP — chunks.md, scores.json, insights.json all "
            f"present in {working_dir}. Pass --force to re-slice."
        )
        return

    meta = json.loads((working_dir / "meta.json").read_text(encoding="utf-8"))
    dms = json.loads((working_dir / "danmaku.json").read_text(encoding="utf-8"))
    duration = meta["duration_sec"]
    window_size = compute_window_size(duration)

    print(
        f"[Stage 2] Slicing {len(dms):,} danmakus into "
        f"{window_size}s windows over {duration}s…"
    )
    chunks = slice_by_window(dms, window_size, duration)

    # Enrich chunks with display-time fields + (possibly down-sampled) danmaku
    # list for the prompt. We keep the raw `danmakus` list untouched so the
    # true count is still accessible via `chunk.danmakus | length` in the
    # template header (where we mark SPARSE).
    for chunk in chunks:
        chunk["time_start_hms"] = format_hms(chunk["time_start"])
        chunk["time_end_hms"] = format_hms(chunk["time_end"])
        sampled = _sample_dense(chunk["danmakus"], seed=chunk["chunk_id"])
        chunk["display_danmakus"] = [
            {"time_hms": format_hms(d["time"]), "text": d["text"]}
            for d in sampled
        ]

    tpl = _load_template()
    chunks_md.write_text(
        tpl.render(
            meta=meta,
            duration_hms=format_hms(duration),
            total_danmaku=len(dms),
            window_size=window_size,
            chunks=chunks,
        ),
        encoding="utf-8",
    )
    scores_json.write_text("[]", encoding="utf-8")
    # Insights skeleton. The Agent overwrites this with a populated summary +
    # three insights; ``render_report`` is tolerant of the skeleton form and
    # will simply omit the Executive Summary block in that case.
    insights_json.write_text(
        json.dumps(
            {"summary": "", "insights": []},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[Stage 2] Done → {len(chunks)} chunks, window={window_size}s")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="emoekg-slice",
        description="emoekg Stage 2: slice danmakus into chunks",
    )
    ap.add_argument(
        "-o", "--output", required=True,
        help="Working directory (must contain meta.json + danmaku.json)",
    )
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    try:
        run(Path(args.output), force=args.force)
    except FileNotFoundError as e:
        print(f"[Stage 2] missing input: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
