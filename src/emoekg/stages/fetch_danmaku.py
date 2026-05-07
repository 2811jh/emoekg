"""Stage 1 — fetch Bilibili video metadata and all historical danmakus.

Input: a URL / BV id string + a working directory.
Output:
  * ``<working_dir>/meta.json``    — normalized video metadata + fetched_at
  * ``<working_dir>/danmaku.json`` — deduped list of danmaku dicts

This stage is **idempotent by default**: if both output files already exist
the stage logs a SKIP and returns. Pass ``force=True`` (or ``--force`` on the
CLI) to bypass the cache. A *partial* cache (only one of the two files
present) is treated as dirty and triggers a full re-fetch.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from emoekg._lib.bv_parser import extract_bvid
from emoekg._lib.danmaku_client import fetch_all_danmakus, fetch_video_meta

__all__ = ["run", "main"]


def run(url_or_bvid: str, working_dir: Path | str, force: bool = False) -> None:
    """Execute Stage 1.

    Args:
        url_or_bvid: Any form accepted by :func:`extract_bvid` — full URL,
            short link, bare BV id, or a chat message containing one.
        working_dir: Output directory. Created if missing.
        force: If ``True``, ignore existing cache files and re-fetch.
    """
    working_dir = Path(working_dir)
    working_dir.mkdir(parents=True, exist_ok=True)

    meta_path = working_dir / "meta.json"
    dm_path = working_dir / "danmaku.json"

    if not force and meta_path.exists() and dm_path.exists():
        print(
            f"[Stage 1] SKIP — meta.json & danmaku.json already present in "
            f"{working_dir}. Pass --force to re-fetch."
        )
        return

    bvid = extract_bvid(url_or_bvid)

    print(f"[Stage 1] Fetching metadata for {bvid}…")
    meta = fetch_video_meta(bvid)
    # Record when we pulled this, for provenance in the final HTML report.
    meta["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"  meta: 《{meta['title']}》 | duration={meta['duration_sec']}s | "
        f"UP: {meta['up']} | views={meta['view_count']}"
    )

    print(f"[Stage 1] Fetching danmakus (duration={meta['duration_sec']}s)…")
    dms = fetch_all_danmakus(bvid, meta["duration_sec"])
    # No indent for the danmaku payload — it can easily be >10 MB of text
    # and indentation triples the file size without adding value.
    dm_path.write_text(
        json.dumps(dms, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  danmakus: {len(dms):,} total (deduped)")

    print(f"[Stage 1] Done → {working_dir}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="emoekg-fetch",
        description="emoekg Stage 1: fetch Bilibili video meta + danmakus",
    )
    ap.add_argument("url", help="B站视频 URL、短链或 BV id")
    ap.add_argument(
        "-o", "--output", required=True,
        help="工作目录路径（自动创建）",
    )
    ap.add_argument(
        "--force", action="store_true",
        help="忽略 meta.json / danmaku.json 缓存重新拉取",
    )
    args = ap.parse_args(argv)

    try:
        run(args.url, Path(args.output), force=args.force)
    except (ValueError, TypeError) as e:
        print(f"[Stage 1] input error: {e}", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"[Stage 1] network/upstream error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
