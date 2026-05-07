"""Stage 5 — render the single-file interactive HTML report.

The output is one standalone HTML file (~1 MB — ECharts dominates) that opens
in any modern browser with no external fetches. Five JSON blobs are embedded
in ``<script type="application/json">`` tags; the front-end (``app.js``,
also inlined) reads them on ``DOMContentLoaded`` and wires up the chart,
video player, danmaku list, and turnpoint panel.

Two playback modes:

* **iframe (default)** — ``CONFIG.video_mode == "iframe"``. HTML embeds the
  Bilibili player via ``<iframe>`` and supports *one-way* seeking (click the
  chart → jump the player). Cross-origin prevents reading back playback time.
* **local** — ``CONFIG.video_mode == "local"``. Used when a ``video.mp4``
  sidecar file exists next to the report (e.g. from ``yutto``). Enables full
  bidirectional sync.
"""
from __future__ import annotations

import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from emoekg._lib.adaptive_window import compute_window_size
from emoekg._lib.plutchik import COLORS
from emoekg._lib.time_utils import format_hms

__all__ = ["run", "main"]


def _template_dir() -> Path:
    """Locate the packaged ``emoekg/templates/`` directory."""
    return Path(str(files("emoekg.templates")))


def _load_insights(path: Path) -> dict:
    """Read ``insights.json`` and normalize it for the template.

    The file is **optional in practice**: Stage 2 writes an empty skeleton,
    and the Agent's scoring pass usually overwrites it with a populated
    form. The template only renders the Executive Summary block when the
    summary text is non-empty, so a missing or skeletal file degrades
    gracefully to "no TL;DR".

    Expected populated schema::

        {
          "summary":   "本视频的情绪核心是 ...",   # one-sentence TL;DR
          "insights": [
            {"title": "期待先行", "body": "价格公布后即刻转化..."},
            {"title": "梗触发",   "body": "跨 IP 识别引发集体笑声..."},
            {"title": "信任背书", "body": "流畅度确认是第二个 trust 峰..."},
          ]
        }

    Returns an always-valid dict (missing fields filled with empty values)
    so the template never needs defensive ``{% if %}`` guards beyond a
    single ``insights.summary`` check.
    """
    if not path.exists():
        return {"summary": "", "insights": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # A malformed insights file is not fatal to the report.
        return {"summary": "", "insights": []}
    return {
        "summary": str(data.get("summary", "") or ""),
        "insights": [
            {"title": str(i.get("title", "") or ""),
             "body":  str(i.get("body", "")  or "")}
            for i in (data.get("insights") or [])
            if isinstance(i, dict)
        ],
    }


def run(
    working_dir: Path | str,
    with_video: bool = False,
    force: bool = False,
) -> None:
    """Render ``emoekg_report.html`` into ``working_dir``.

    Args:
        working_dir: Directory with Stages 1–4 outputs
            (``meta.json``, ``danmaku.json``, ``scores.json``, ``turnpoints.json``).
        with_video: If ``True``, configure the front-end to use a sidecar
            ``video.mp4`` instead of the Bilibili iframe.
        force: Overwrite an existing ``emoekg_report.html``.
    """
    working_dir = Path(working_dir)
    html_path = working_dir / "emoekg_report.html"

    if not force and html_path.exists():
        print(
            f"[Stage 5] SKIP — emoekg_report.html present in {working_dir}. "
            "Pass --force to re-render."
        )
        return

    meta = json.loads((working_dir / "meta.json").read_text(encoding="utf-8"))
    scores = json.loads((working_dir / "scores.json").read_text(encoding="utf-8"))
    tps = json.loads((working_dir / "turnpoints.json").read_text(encoding="utf-8"))
    dms = json.loads((working_dir / "danmaku.json").read_text(encoding="utf-8"))
    insights = _load_insights(working_dir / "insights.json")

    tpl_dir = _template_dir()
    echarts_js = (tpl_dir / "vendor" / "echarts.min.js").read_text(encoding="utf-8")
    app_js = (tpl_dir / "app.js").read_text(encoding="utf-8")

    config = {
        "colors": dict(COLORS),  # Mapping → plain dict for JSON
        "video_mode": "local" if with_video else "iframe",
        "video_path": "./video.mp4" if with_video else None,
    }

    env = Environment(
        loader=FileSystemLoader(str(tpl_dir)),
        # We deliberately do NOT escape HTML output: the `| safe` filter is
        # used on JSON blobs that we've already controlled. The data we're
        # embedding is user-supplied danmaku text, which is escaped
        # client-side in app.js before being inserted into the DOM.
        autoescape=select_autoescape(enabled_extensions=()),
    )
    tpl = env.get_template("report.html.j2")
    html = tpl.render(
        meta=meta,
        duration_hms=format_hms(meta["duration_sec"]),
        window_size=compute_window_size(meta["duration_sec"]),
        total_danmaku=len(dms),
        chunks_count=len(scores),
        turnpoints_count=len(tps),
        insights=insights,  # {"summary": "...", "insights": [{title, body}, ...]}
        # JSON blobs. indent=2 helps when a researcher peeks at the source.
        meta_json=json.dumps(meta, ensure_ascii=False, indent=2),
        scores_json=json.dumps(scores, ensure_ascii=False, indent=2),
        turnpoints_json=json.dumps(tps, ensure_ascii=False, indent=2),
        danmakus_json=json.dumps(dms, ensure_ascii=False),
        config_json=json.dumps(config, ensure_ascii=False, indent=2),
        echarts_js=echarts_js,
        app_js=app_js,
    )
    html_path.write_text(html, encoding="utf-8")
    print(f"[Stage 5] Done → {html_path} ({len(html) // 1024} KB)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="emoekg-render",
        description="emoekg Stage 5: render the interactive HTML report",
    )
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument(
        "--with-video", action="store_true",
        help="Use a local video.mp4 sidecar for full bidirectional sync",
    )
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    try:
        run(Path(args.output), with_video=args.with_video, force=args.force)
    except FileNotFoundError as e:
        print(f"[Stage 5] missing input: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
