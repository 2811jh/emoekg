"""Tests for ``emoekg.cli`` — the top-level orchestrator.

The CLI is a thin façade: it shells out to the four stage modules and adds
one piece of logic specific to Agent-driven use — refuse to continue past
Stage 2 until ``scores.json`` has been populated. We test that split in
isolation by monkey-patching the stage ``run`` functions; we don't want the
CLI tests to re-run heavy fetch/render pipelines (those have their own
test files).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from emoekg import cli


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stage_spies(monkeypatch):
    """Replace every stage ``run`` with a call-recorder.

    Returns a dict that, after the CLI runs, contains one key per stage
    with the positional-and-keyword args the CLI handed to it (or ``None``
    if the stage wasn't called). Using ``None`` as the "not called" sentinel
    makes the assertions read cleanly: ``assert calls["render"] is None``.
    """
    calls: dict[str, dict | None] = {
        "fetch": None, "slice": None, "detect": None, "render": None,
    }

    def _spy(name):
        def inner(*args, **kwargs):
            calls[name] = {"args": args, "kwargs": kwargs}
        return inner

    monkeypatch.setattr(cli.fetch_danmaku, "run", _spy("fetch"))
    monkeypatch.setattr(cli.slice_chunks, "run", _spy("slice"))
    monkeypatch.setattr(cli.detect_turnpoints, "run", _spy("detect"))
    monkeypatch.setattr(cli.render_report, "run", _spy("render"))

    return calls


def _write_populated_scores(wd: Path) -> None:
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "scores.json").write_text(
        json.dumps([{
            "chunk_id": "C001", "time_start": 0, "time_end": 10, "n_danmaku": 5,
            "joy": 6, "trust": 0, "fear": 0, "surprise": 0,
            "sadness": 0, "disgust": 0, "anger": 0, "anticipation": 0,
            "note": "哈哈刷屏",
        }], ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Parser smoke
# ---------------------------------------------------------------------------


def test_build_parser_accepts_all_three_subcommands():
    ap = cli.build_parser()
    # argparse doesn't expose its subcommands cleanly, so we drive it by
    # parsing representative arg strings. If any raises SystemExit, the
    # subcommand isn't wired up.
    ap.parse_args(["prepare", "BVTEST", "-o", "wd"])
    ap.parse_args(["finalize", "-o", "wd"])
    ap.parse_args(["run", "BVTEST", "-o", "wd"])


def test_version_flag_exits_zero(capsys):
    ap = cli.build_parser()
    with pytest.raises(SystemExit) as excinfo:
        ap.parse_args(["--version"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "emoekg" in out


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------


def test_prepare_runs_fetch_then_slice_then_hands_off(tmp_path, stage_spies, capsys):
    rc = cli.main(["prepare", "BV1xTEST", "-o", str(tmp_path)])
    assert rc == 0

    assert stage_spies["fetch"] is not None
    assert stage_spies["fetch"]["args"][0] == "BV1xTEST"
    assert Path(stage_spies["fetch"]["args"][1]) == tmp_path
    assert stage_spies["fetch"]["kwargs"] == {"force": False}

    assert stage_spies["slice"] is not None
    assert Path(stage_spies["slice"]["args"][0]) == tmp_path

    # Must NOT have run S4/S5 after prepare.
    assert stage_spies["detect"] is None
    assert stage_spies["render"] is None

    err = capsys.readouterr().err
    assert "Waiting for Agent scoring" in err
    assert "chunks.md" in err
    assert "scores.json" in err


def test_prepare_passes_force_flag(tmp_path, stage_spies):
    cli.main(["prepare", "BV1xTEST", "-o", str(tmp_path), "--force"])
    assert stage_spies["fetch"]["kwargs"]["force"] is True
    assert stage_spies["slice"]["kwargs"]["force"] is True


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------


def test_finalize_refuses_when_scores_missing(tmp_path, stage_spies, capsys):
    # No scores.json at all.
    rc = cli.main(["finalize", "-o", str(tmp_path)])
    assert rc == 2

    assert stage_spies["detect"] is None
    assert stage_spies["render"] is None

    err = capsys.readouterr().err
    assert "Stage 3 (Agent scoring) has not run" in err


def test_finalize_refuses_when_scores_is_empty_skeleton(tmp_path, stage_spies, capsys):
    (tmp_path / "scores.json").write_text("[]", encoding="utf-8")

    rc = cli.main(["finalize", "-o", str(tmp_path)])
    assert rc == 2
    assert stage_spies["detect"] is None
    assert "Stage 3" in capsys.readouterr().err


def test_finalize_runs_when_scores_populated(tmp_path, stage_spies, capsys):
    _write_populated_scores(tmp_path)

    rc = cli.main(["finalize", "-o", str(tmp_path)])
    assert rc == 0

    assert stage_spies["detect"] is not None
    assert stage_spies["render"] is not None
    assert stage_spies["render"]["kwargs"]["with_video"] is False

    out = capsys.readouterr().out
    assert "Report ready" in out
    assert "emoekg_report.html" in out


def test_finalize_passes_with_video_flag(tmp_path, stage_spies):
    _write_populated_scores(tmp_path)

    cli.main(["finalize", "-o", str(tmp_path), "--with-video"])
    assert stage_spies["render"]["kwargs"]["with_video"] is True


# ---------------------------------------------------------------------------
# run (one-shot)
# ---------------------------------------------------------------------------


def test_run_stops_at_handoff_when_scores_empty(tmp_path, stage_spies, capsys):
    # Simulate: fetch + slice succeed (we mock them), but slice leaves the
    # empty [] skeleton so run() must hand off.
    def slice_spy(*args, **kwargs):
        stage_spies["slice"] = {"args": args, "kwargs": kwargs}
        (tmp_path / "scores.json").write_text("[]", encoding="utf-8")

    # Override the generic spy for slice so it actually writes the skeleton.
    import emoekg.stages.slice_chunks as sc
    original = sc.run
    sc.run = slice_spy
    try:
        rc = cli.main(["run", "BV1xTEST", "-o", str(tmp_path)])
    finally:
        sc.run = original

    assert rc == 0
    assert stage_spies["detect"] is None
    assert stage_spies["render"] is None
    assert "Waiting for Agent scoring" in capsys.readouterr().err


def test_run_goes_all_the_way_when_scores_already_populated(tmp_path, stage_spies, capsys):
    # Pre-populate — mimic a resumed session.
    _write_populated_scores(tmp_path)

    rc = cli.main(["run", "BV1xTEST", "-o", str(tmp_path)])
    assert rc == 0

    assert stage_spies["fetch"] is not None
    assert stage_spies["slice"] is not None
    assert stage_spies["detect"] is not None
    assert stage_spies["render"] is not None


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


def test_missing_input_file_returns_2(tmp_path, monkeypatch, capsys):
    def raising_run(*args, **kwargs):
        raise FileNotFoundError("meta.json missing")
    monkeypatch.setattr(cli.fetch_danmaku, "run", raising_run)

    rc = cli.main(["prepare", "BV1xTEST", "-o", str(tmp_path)])
    assert rc == 2
    assert "missing input" in capsys.readouterr().err


def test_bad_url_returns_2(tmp_path, monkeypatch, capsys):
    def raising_run(*args, **kwargs):
        raise ValueError("not a BV id")
    monkeypatch.setattr(cli.fetch_danmaku, "run", raising_run)

    rc = cli.main(["prepare", "notavid", "-o", str(tmp_path)])
    assert rc == 2
    assert "input error" in capsys.readouterr().err


def test_network_failure_returns_1(tmp_path, monkeypatch, capsys):
    def raising_run(*args, **kwargs):
        raise RuntimeError("upstream 500")
    monkeypatch.setattr(cli.fetch_danmaku, "run", raising_run)

    rc = cli.main(["prepare", "BV1xTEST", "-o", str(tmp_path)])
    assert rc == 1
    assert "upstream/runtime" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# _scores_are_populated internal helper
# ---------------------------------------------------------------------------


class TestScoresArePopulated:
    def test_missing_file(self, tmp_path):
        assert cli._scores_are_populated(tmp_path / "nope.json") is False

    def test_empty_file(self, tmp_path):
        p = tmp_path / "scores.json"
        p.write_text("", encoding="utf-8")
        assert cli._scores_are_populated(p) is False

    def test_whitespace_only(self, tmp_path):
        p = tmp_path / "scores.json"
        p.write_text("   \n  ", encoding="utf-8")
        assert cli._scores_are_populated(p) is False

    def test_empty_array(self, tmp_path):
        p = tmp_path / "scores.json"
        p.write_text("[]", encoding="utf-8")
        assert cli._scores_are_populated(p) is False

    def test_populated(self, tmp_path):
        p = tmp_path / "scores.json"
        p.write_text('[{"chunk_id":"C001"}]', encoding="utf-8")
        assert cli._scores_are_populated(p) is True

    def test_malformed_json_raises(self, tmp_path):
        p = tmp_path / "scores.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            cli._scores_are_populated(p)
