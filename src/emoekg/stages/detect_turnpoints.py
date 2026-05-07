"""Stage 4 — detect turnpoints, cluster them, attach evidence danmakus.

Input:   ``<working_dir>/meta.json`` + ``scores.json`` + ``danmaku.json``.
Output:  ``<working_dir>/turnpoints.json`` — list of merged turnpoints, each
         with ``{turnpoint_id, chunk_id, chunk_index, type, main_dimension,
         direction, magnitude, description, time_start, time_end,
         evidence_danmakus:[{time,text,color}...]}``.

Before detecting, we validate the Agent's ``scores.json``:

  * exact chunk count matches what Stage 2 produced
  * every row passes :func:`emoekg._lib.plutchik.validate_score_entry`
  * we warn (soft failure) if > 20% of non-SPARSE chunks are all-zero
    (a classic sign the Agent skimmed the prompt)

Detection fuses peak/valley with JS-divergence shifts, then
:func:`merge_turnpoints` deduplicates overlapping detections and caps the
list. For each survivor we pick up to 5 evidence danmakus from that chunk,
broadening to the immediate neighbours if the chunk itself is sparse.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from emoekg._lib.adaptive_window import compute_window_size, slice_by_window
from emoekg._lib.evidence_picker import pick_evidence
from emoekg._lib.plutchik import DIMENSIONS, validate_score_entry
from emoekg._lib.turnpoint_algo import (
    find_peaks_valleys,
    find_shifts,
    merge_turnpoints,
)

__all__ = ["run", "main"]

# If more than this fraction of non-SPARSE chunks came back all-zero,
# it's almost certainly an Agent scoring failure — warn loudly.
_ZERO_CHUNK_WARN_THRESHOLD = 0.20
# Minimum danmakus required before we claim a chunk is "dense enough" to
# carry turnpoint evidence by itself (otherwise we broaden to neighbours).
_EVIDENCE_MIN_POOL = 5


def _validate_scores(scores: list[dict], expected_count: int) -> None:
    if len(scores) != expected_count:
        print(
            f"[Stage 4] ERROR: scores.json has {len(scores)} entries, "
            f"expected {expected_count}. Did Stage 3 finish writing all chunks?",
            file=sys.stderr,
        )
        sys.exit(2)

    zero_chunks = 0
    non_sparse = 0
    for s in scores:
        validate_score_entry(s)
        if s["n_danmaku"] >= 3:
            non_sparse += 1
            if all(s.get(d, 0) == 0 for d in DIMENSIONS):
                zero_chunks += 1

    if non_sparse and zero_chunks / non_sparse > _ZERO_CHUNK_WARN_THRESHOLD:
        print(
            f"[Stage 4] WARN: {zero_chunks}/{non_sparse} non-sparse chunks "
            "have all-zero scores — the Agent may have skipped scoring.",
            file=sys.stderr,
        )


def _expected_chunk_count(duration_sec: int, window_size: int) -> int:
    """Mirror Stage 2's chunking exactly by reusing slice_by_window."""
    return len(slice_by_window([], window_size, duration_sec))


def run(working_dir: Path | str, force: bool = False) -> None:
    """Execute Stage 4."""
    working_dir = Path(working_dir)
    tp_path = working_dir / "turnpoints.json"

    if not force and tp_path.exists():
        print(
            f"[Stage 4] SKIP — turnpoints.json present in {working_dir}. "
            "Pass --force to recompute."
        )
        return

    meta = json.loads((working_dir / "meta.json").read_text(encoding="utf-8"))
    scores = json.loads((working_dir / "scores.json").read_text(encoding="utf-8"))
    dms = json.loads((working_dir / "danmaku.json").read_text(encoding="utf-8"))

    duration = meta["duration_sec"]
    window_size = compute_window_size(duration)
    expected_chunks = _expected_chunk_count(duration, window_size)

    _validate_scores(scores, expected_chunks)

    peaks = find_peaks_valleys(scores)
    shifts = find_shifts(scores)
    merged = merge_turnpoints(peaks + shifts, window_size=window_size)
    print(
        f"[Stage 4] {len(peaks)} peaks/valleys + {len(shifts)} shifts "
        f"→ {len(merged)} after merge"
    )

    # Index danmakus by chunk so evidence lookup is O(1) per turnpoint.
    chunk_buckets: dict[int, list[dict]] = {}
    for d in dms:
        idx = min(int(d["time"] // window_size), expected_chunks - 1)
        if idx < 0:
            continue
        chunk_buckets.setdefault(idx, []).append(d)

    for tp in merged:
        idx = tp["chunk_index"]
        pool = list(chunk_buckets.get(idx, []))
        # If the chunk itself is sparse, widen to its neighbours so the
        # turnpoint doesn't end up with 0 evidence quotes.
        if len(pool) < _EVIDENCE_MIN_POOL:
            pool += chunk_buckets.get(idx - 1, [])
            pool += chunk_buckets.get(idx + 1, [])

        evidence = pick_evidence(pool, tp["main_dimension"], target=5)
        tp["evidence_danmakus"] = [
            {"time": d["time"], "text": d["text"], "color": d["color"]}
            for d in evidence
        ]
        tp["time_start"] = scores[idx]["time_start"]
        tp["time_end"] = scores[idx]["time_end"]

    tp_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[Stage 4] Done → {len(merged)} turnpoints")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="emoekg-detect",
        description="emoekg Stage 4: detect emotional turnpoints",
    )
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    try:
        run(Path(args.output), force=args.force)
    except FileNotFoundError as e:
        print(f"[Stage 4] missing input: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
