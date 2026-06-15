"""emoekg command-line entry point — orchestrates the 5-stage pipeline.

emoekg is designed to be driven by an **AI Agent in a conversational session**
(CodeMaker / Claude / similar). The pipeline therefore splits naturally in two:

* **Data phases** (S1, S2, S4, S5) — deterministic Python, runnable as one
  subprocess.
* **Scoring phase** (S3) — the Agent reads the generated ``chunks.md`` prompt
  and writes scoring rows into ``scores.json`` *in the same conversation*,
  following the rubric in ``docs/scoring_rubric.md``.

This CLI exposes three subcommands that mirror that split:

* ``emoekg prepare <url> -o <dir>``
    Runs S1 + S2. Produces ``meta.json``, ``danmaku.json``, ``chunks.md``, and
    an empty ``scores.json`` skeleton. After this the Agent is expected to
    score the chunks and overwrite ``scores.json``.

* ``emoekg finalize -o <dir>``
    Runs S4 + S5. Requires a populated ``scores.json`` — if the file is still
    the empty ``[]`` skeleton, emoekg refuses to continue with a friendly
    reminder pointing at the rubric.

* ``emoekg run <url> -o <dir>``
    Convenience one-shot: runs S1 + S2, then checks if ``scores.json`` is
    already populated (e.g. from a previous session) and, if so, continues
    into S4 + S5. Otherwise prints the same reminder as ``finalize`` and
    exits 0 — this is the expected hand-off point for Agent-driven usage.

All three subcommands are idempotent (each stage skips if outputs already
exist) and accept ``--force`` to re-do work downstream of changes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from emoekg import __version__
from emoekg.stages import (
    detect_turnpoints,
    fetch_danmaku,
    render_report,
    slice_chunks,
)

__all__ = ["main", "build_parser", "run_prepare", "run_finalize", "run_oneshot"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_AGENT_HAND_OFF = """\
[emoekg] Data prepared. Waiting for Agent scoring (Stage 3).

Next step — in the current chat session, the Agent should:
  1. Open  {chunks_md}
  2. Score every chunk per the rubric in docs/scoring_rubric.md
     (8 Plutchik dims, 0–10 ints, SPARSE chunks → all zeros + note="SPARSE")
  3. Write the full list of score rows to
     {scores_json}
  4. Re-run `emoekg finalize -o {working_dir}` to produce the HTML report.

If you are NOT in an Agent session, see docs/scoring_rubric.md for how to
score manually.
"""


def _scores_are_populated(scores_path: Path) -> bool:
    """Return True iff scores.json contains at least one score row.

    We tolerate whitespace-only files and the ``[]`` skeleton written by
    Stage 2; both count as "not populated". Any JSON parse error propagates
    so the user sees why we can't proceed.
    """
    if not scores_path.exists():
        return False
    raw = scores_path.read_text(encoding="utf-8").strip()
    if not raw or raw == "[]":
        return False
    data = json.loads(raw)
    return isinstance(data, list) and len(data) > 0


def _print_hand_off(working_dir: Path) -> None:
    print(
        _AGENT_HAND_OFF.format(
            chunks_md=working_dir / "chunks.md",
            scores_json=working_dir / "scores.json",
            working_dir=working_dir,
        ),
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


def run_prepare(url: str, working_dir: Path, force: bool = False) -> int:
    """Execute S1 + S2, then hand off to the Agent."""
    working_dir = Path(working_dir)
    fetch_danmaku.run(url, working_dir, force=force)
    slice_chunks.run(working_dir, force=force)
    _print_hand_off(working_dir)
    return 0


def run_finalize(working_dir: Path, with_video: bool = False, force: bool = False) -> int:
    """Execute S4 + S5. Refuses to run if scores.json is unpopulated."""
    working_dir = Path(working_dir)
    scores_path = working_dir / "scores.json"

    if not _scores_are_populated(scores_path):
        print(
            f"[emoekg] ERROR: {scores_path} is empty — Stage 3 (Agent scoring) "
            "has not run yet.",
            file=sys.stderr,
        )
        _print_hand_off(working_dir)
        return 2

    detect_turnpoints.run(working_dir, force=force)
    render_report.run(working_dir, with_video=with_video, force=force)
    print(f"[emoekg] ✓ Report ready → {working_dir / 'emoekg_report.html'}")
    return 0


def run_oneshot(
    url: str,
    working_dir: Path,
    with_video: bool = False,
    force: bool = False,
) -> int:
    """Fetch + slice; if already-scored, also detect + render. Otherwise hand off."""
    working_dir = Path(working_dir)
    fetch_danmaku.run(url, working_dir, force=force)
    slice_chunks.run(working_dir, force=force)

    if not _scores_are_populated(working_dir / "scores.json"):
        _print_hand_off(working_dir)
        return 0

    detect_turnpoints.run(working_dir, force=force)
    render_report.run(working_dir, with_video=with_video, force=force)
    print(f"[emoekg] ✓ Report ready → {working_dir / 'emoekg_report.html'}")
    return 0


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="emoekg",
        description=(
            "Emotional ECG for Bilibili danmaku — 8-dim (Plutchik) emotion "
            "timeline for UX research. Designed to be driven by an AI Agent."
        ),
    )
    ap.add_argument("--version", action="version", version=f"emoekg {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    # prepare
    ap_prep = sub.add_parser(
        "prepare",
        help="S1+S2: fetch danmakus and slice into chunks.md (hand-off to Agent)",
    )
    ap_prep.add_argument("url", help="B 站视频 URL / 短链 / BV id")
    ap_prep.add_argument("-o", "--output", required=True, help="工作目录（自动创建）")
    ap_prep.add_argument("--force", action="store_true", help="忽略缓存重跑")

    # finalize
    ap_fin = sub.add_parser(
        "finalize",
        help="S4+S5: detect turnpoints and render HTML (requires populated scores.json)",
    )
    ap_fin.add_argument("-o", "--output", required=True, help="工作目录")
    ap_fin.add_argument(
        "--with-video", action="store_true",
        help="使用工作目录下的 video.mp4 替代 iframe 实现双向同步",
    )
    ap_fin.add_argument("--force", action="store_true", help="忽略缓存重跑")

    # run (one-shot)
    ap_run = sub.add_parser(
        "run",
        help="one-shot: S1+S2, then S4+S5 iff scores.json already populated",
    )
    ap_run.add_argument("url", help="B 站视频 URL / 短链 / BV id")
    ap_run.add_argument("-o", "--output", required=True, help="工作目录")
    ap_run.add_argument("--with-video", action="store_true")
    ap_run.add_argument("--force", action="store_true")

    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    wd = Path(args.output)

    try:
        if args.command == "prepare":
            return run_prepare(args.url, wd, force=args.force)
        if args.command == "finalize":
            return run_finalize(wd, with_video=args.with_video, force=args.force)
        if args.command == "run":
            return run_oneshot(args.url, wd, with_video=args.with_video, force=args.force)
    except FileNotFoundError as e:
        print(f"[emoekg] missing input: {e}", file=sys.stderr)
        return 2
    except (ValueError, TypeError) as e:
        print(f"[emoekg] input error: {e}", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"[emoekg] upstream/runtime error: {e}", file=sys.stderr)
        return 1

    ap.error(f"unknown command: {args.command!r}")  # pragma: no cover — argparse catches
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
