# emoekg Implementation Plan

> ⚠️ **HISTORICAL ARCHIVE — DO NOT EDIT**
>
> 本文件是 emoekg **v0.1.0** 的实施计划（2026-05-07 立项），所有 Task 1–15 已于 2026-05-08 全部完成并发布。保留作为决策与拆分过程的留痕。
>
> - 想了解**最新版本路线 / 已发版本变更** → 看 [`docs/CHANGELOG.md`](./CHANGELOG.md)
> - 想了解**当前架构** → 看 [`docs/2026-05-07-emoekg-design.md` §15](./2026-05-07-emoekg-design.md) v0.4.x 实施回顾
> - 想看**仓库每个文件的用途** → 看 [`README.md` §「📑 文件清单」](../README.md)
> - 不要根据本文件「文件路径 / 命名 / 依赖」做开发决策，部分内容（如 `requirements.txt`、`examples/`）已在后续版本中被替换或移除

---

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 0 到 1 实现 emoekg skill v0.1.0 —— 把 B 站视频弹幕数据转成单文件 HTML 情绪心电图报告。

**Architecture:** 5-Stage 流水线（拉弹幕 → 切片 → Agent 打分 → 识别转折点 → 渲染 HTML），Python 脚本负责数据 I/O 与算法，CodeMaker Agent 负责 Stage 3 语义打分，中间态以 JSON/MD 文件落盘以支持幂等与断点续跑。

**Tech Stack:** Python 3.10+ / bilibili-api-python / Jinja2 / numpy / scipy / pytest / ECharts 5.x (内联) / yutto (optional)

**Spec reference:** `emoekg/docs/2026-05-07-emoekg-design.md`

---

## File Structure

**Python 包层**（`emoekg/`）：

| 文件 | 职责 |
|---|---|
| `emoekg/__init__.py` | 版本号、暴露公共接口 |
| `emoekg/__main__.py` | `python -m emoekg` 入口 |
| `emoekg/cli.py` | argparse 定义 + Orchestrator 串联 5 个 Stage |
| `emoekg/_lib/time_utils.py` | 秒 ↔ `00:12:34` 格式化 |
| `emoekg/_lib/plutchik.py` | 8 维情绪 schema + 颜色 + 关键词表 |
| `emoekg/_lib/bv_parser.py` | URL/各种输入 → BV 号 |
| `emoekg/_lib/adaptive_window.py` | 自适应窗口大小计算 |
| `emoekg/_lib/danmaku_client.py` | `bilibili-api-python` 封装 |
| `emoekg/_lib/turnpoint_algo.py` | 峰值检测 + JS 散度对比 + 合并去重 |
| `emoekg/_lib/evidence_picker.py` | 转折点佐证弹幕选取 |

**Stage 脚本层**（`scripts/`）：

| 文件 | Stage | 输入 → 输出 |
|---|---|---|
| `scripts/fetch_danmaku.py` | 1 | BV URL → `meta.json` + `danmaku.json` |
| `scripts/slice_chunks.py` | 2 | `danmaku.json` → `chunks.md` + 空 `scores.json` 骨架 |
| `scripts/detect_turnpoints.py` | 4 | `scores.json` + `danmaku.json` → `turnpoints.json` |
| `scripts/render_report.py` | 5 | 所有 JSON → `emoekg_report.html` |
| `scripts/download_video.py` | opt | BV → `video.mp4` |

**模板层**（`templates/`）：

| 文件 | 用途 |
|---|---|
| `templates/chunks_prompt.md.j2` | Stage 2 产出 chunks.md 的 Jinja2 模板 |
| `templates/report.html.j2` | Stage 5 产出 HTML 报告的主模板 |
| `templates/scoring_rubric.md` | 打分细则（供 SKILL.md 引用） |

**测试层**（`tests/`）：每个 `_lib` 模块对应一个 `test_*.py`，共 7 个。

**打包发布**：`pyproject.toml` 定义 CLI entry point `emoekg = emoekg.cli:main`。

---

# Phase 0：项目初始化

## Task 1：建立仓库骨架

**Files:**
- Create: `emoekg/.gitignore`
- Create: `emoekg/LICENSE`
- Create: `emoekg/requirements.txt`
- Create: `emoekg/pyproject.toml`
- Create: `emoekg/CHANGELOG.md`
- Create: `emoekg/emoekg/__init__.py`
- Create: `emoekg/emoekg/_lib/__init__.py`
- Create: `emoekg/tests/__init__.py`
- Create: `emoekg/scripts/__init__.py`（占位，便于 pytest 发现）

- [ ] **Step 1: 创建 `.gitignore`**

```
# User runtime outputs
emoekg_*_*/
output/
*.mp4
*.flv

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
.pytest_cache/
.venv/
venv/

# IDE
.vscode/
.idea/
.DS_Store

# Logs
*.log
```

- [ ] **Step 2: 创建 `LICENSE`**（MIT 标准文本）

```
MIT License

Copyright (c) 2026 lijinghui03

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: 创建 `requirements.txt`**

```
bilibili-api-python>=16.0.0
jinja2>=3.1.0
numpy>=1.24.0
scipy>=1.10.0
```

- [ ] **Step 4: 创建 `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "emoekg"
version = "0.1.0"
description = "Bilibili danmaku emotion ECG for UX researchers"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [{name = "lijinghui03"}]
dependencies = [
    "bilibili-api-python>=16.0.0",
    "jinja2>=3.1.0",
    "numpy>=1.24.0",
    "scipy>=1.10.0",
]

[project.optional-dependencies]
with-video = ["yutto>=2.0.0"]
dev = ["pytest>=7.0.0", "pytest-mock>=3.10.0"]

[project.scripts]
emoekg = "emoekg.cli:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["emoekg*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 5: 创建 `CHANGELOG.md`**

```markdown
# Changelog

## [Unreleased]

## [0.1.0] - 2026-05-07
### Added
- Initial release: 5-Stage pipeline (fetch → slice → score → detect → render)
- Plutchik 8-dimension emotion scoring via CodeMaker Agent
- Interactive HTML report with ECharts heart-rate chart
- `--with-video` mode for full bidirectional sync with local video
```

- [ ] **Step 6: 创建各包 `__init__.py`**

`emoekg/emoekg/__init__.py`：
```python
"""emoekg: Bilibili danmaku emotion ECG."""

__version__ = "0.1.0"
```

`emoekg/emoekg/_lib/__init__.py`：空文件

`emoekg/tests/__init__.py`：空文件

`emoekg/scripts/__init__.py`：空文件

- [ ] **Step 7: Commit**

```bash
cd emoekg
git add .gitignore LICENSE requirements.txt pyproject.toml CHANGELOG.md emoekg/ tests/ scripts/
git commit -m "chore: init project skeleton (license, deps, packaging, pkg __init__)"
```

---

## Task 2：配置 pytest & 安装开发依赖

**Files:**
- Create: `emoekg/tests/conftest.py`
- Create: `emoekg/tests/fixtures/.gitkeep`

- [ ] **Step 1: 创建 `tests/conftest.py`**

```python
"""Shared pytest fixtures."""
from pathlib import Path
import pytest


@pytest.fixture
def fixtures_dir():
    """Return path to tests/fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_working_dir(tmp_path):
    """Simulate a user's emoekg working directory."""
    d = tmp_path / "emoekg_BVTEST_20260507"
    d.mkdir()
    return d
```

- [ ] **Step 2: 创建 fixtures 目录占位**

```bash
mkdir -p tests/fixtures
touch tests/fixtures/.gitkeep
```

- [ ] **Step 3: 安装开发依赖并验证 pytest 能运行**

```bash
pip install -e ".[dev]"
pytest --collect-only
```

Expected: 收集 0 个测试，退出码 5（no tests collected is OK here）或 0。

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/fixtures/.gitkeep
git commit -m "test: add pytest conftest with fixtures_dir and tmp_working_dir"
```

---

# Phase 1：底层工具模块（纯函数，TDD 最佳案例）

## Task 3：`time_utils.py` —— 秒/字符串互转

> **实现偏离备注（2026-05-07）：** 本任务已落地，实际实现扩展为四个函数
> `parse_timestamp / format_hms / parse_hms / clamp_seconds`，返回类型统一为
> `float`，并增加对负数、`None`、非法字符串的严格错误。以下伪代码仅保留为
> 历史设计意图；权威实现见 `src/emoekg/_lib/time_utils.py` 与
> `tests/test_time_utils.py`（27 pass）。

**Files:**
- Create: `emoekg/emoekg/_lib/time_utils.py`
- Create: `emoekg/tests/test_time_utils.py`

- [ ] **Step 1: 写 8 个失败测试**

`tests/test_time_utils.py`：
```python
from emoekg._lib.time_utils import format_hms, parse_hms


class TestSecToHms:
    def test_zero(self):
        assert format_hms(0) == "00:00:00"

    def test_seconds_only(self):
        assert format_hms(42) == "00:00:42"

    def test_minutes(self):
        assert format_hms(75) == "00:01:15"

    def test_hours(self):
        assert format_hms(3723) == "01:02:03"

    def test_float_truncated(self):
        assert format_hms(12.9) == "00:00:12"


class TestHmsToSec:
    def test_zero(self):
        assert parse_hms("00:00:00") == 0

    def test_full(self):
        assert parse_hms("01:02:03") == 3723

    def test_roundtrip(self):
        for s in [0, 42, 75, 3723, 10800]:
            assert parse_hms(format_hms(s)) == s
```

- [ ] **Step 2: 运行，确认失败**

```bash
pytest tests/test_time_utils.py -v
```

Expected: `ModuleNotFoundError: No module named 'emoekg._lib.time_utils'`

- [ ] **Step 3: 实现最小代码让测试通过**

`emoekg/_lib/time_utils.py`：
```python
"""Seconds ↔ HH:MM:SS conversion."""


def format_hms(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format (truncate fractional seconds)."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_hms(hms: str) -> int:
    """Parse HH:MM:SS into total seconds."""
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)
```

- [ ] **Step 4: 运行，确认通过**

```bash
pytest tests/test_time_utils.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add emoekg/_lib/time_utils.py tests/test_time_utils.py
git commit -m "feat(lib): add time_utils (sec ↔ HH:MM:SS) with tests"
```

---

## Task 4：`plutchik.py` —— 8 维情绪 Schema

**Files:**
- Create: `emoekg/emoekg/_lib/plutchik.py`
- Create: `emoekg/tests/test_plutchik.py`

- [ ] **Step 1: 写失败测试**

`tests/test_plutchik.py`：
```python
from emoekg._lib.plutchik import (
    DIMENSIONS, COLORS, KEYWORDS,
    validate_score_entry, get_dominant_dimension,
)


def test_dimensions_count():
    assert len(DIMENSIONS) == 8
    assert set(DIMENSIONS) == {
        "joy", "trust", "fear", "surprise",
        "sadness", "disgust", "anger", "anticipation",
    }


def test_colors_coverage():
    for d in DIMENSIONS:
        assert d in COLORS
        assert COLORS[d].startswith("#")


def test_keywords_coverage():
    for d in DIMENSIONS:
        assert d in KEYWORDS
        assert len(KEYWORDS[d]) >= 3


def test_validate_score_entry_ok():
    entry = {
        "chunk_id": "C001", "time_start": 0, "time_end": 15, "n_danmaku": 42,
        "joy": 7, "trust": 2, "fear": 0, "surprise": 4,
        "sadness": 0, "disgust": 0, "anger": 0, "anticipation": 8,
        "note": "ok",
    }
    validate_score_entry(entry)  # should not raise


def test_validate_score_entry_missing_dim():
    entry = {"chunk_id": "C001", "time_start": 0, "time_end": 15, "n_danmaku": 42,
             "joy": 7, "note": "ok"}
    try:
        validate_score_entry(entry)
        assert False, "should have raised"
    except ValueError as e:
        assert "missing" in str(e).lower()


def test_validate_score_entry_out_of_range():
    entry = {"chunk_id": "C001", "time_start": 0, "time_end": 15, "n_danmaku": 42,
             "joy": 11, "trust": 0, "fear": 0, "surprise": 0,
             "sadness": 0, "disgust": 0, "anger": 0, "anticipation": 0, "note": "x"}
    try:
        validate_score_entry(entry)
        assert False
    except ValueError as e:
        assert "range" in str(e).lower() or "0" in str(e) or "10" in str(e)


def test_dominant_dimension():
    entry = {"joy": 2, "trust": 1, "fear": 0, "surprise": 3,
             "sadness": 0, "disgust": 0, "anger": 8, "anticipation": 1}
    assert get_dominant_dimension(entry) == "anger"
```

- [ ] **Step 2: 运行，确认失败**

```bash
pytest tests/test_plutchik.py -v
```

Expected: ModuleNotFoundError

- [ ] **Step 3: 实现**

`emoekg/_lib/plutchik.py`：
```python
"""Plutchik 8-dimension emotion schema, colors, and keyword dictionaries."""

DIMENSIONS = [
    "joy", "trust", "fear", "surprise",
    "sadness", "disgust", "anger", "anticipation",
]

# Plutchik wheel-inspired colors (WCAG AA compliant)
COLORS = {
    "joy":          "#F4D03F",  # 金黄
    "trust":        "#52BE80",  # 草绿
    "fear":         "#566573",  # 深灰
    "surprise":     "#F39C12",  # 橙
    "sadness":      "#5499C7",  # 蓝
    "disgust":      "#8E44AD",  # 紫
    "anger":        "#C0392B",  # 红
    "anticipation": "#EB984E",  # 珊瑚
}

# Bilibili danmaku expression dictionaries (used by evidence_picker, NOT by Agent scoring)
KEYWORDS = {
    "joy":          ["哈哈", "233", "笑死", "好活", "太乐", "笑不活", "笑疯", "爆笑"],
    "trust":        ["稳了", "专业", "yyds", "可以", "信", "靠谱", "实锤"],
    "fear":         ["害怕", "瑟瑟发抖", "完蛋", "要出事", "慌", "不敢", "胆小"],
    "surprise":     ["卧槽", "啊这", "???", "??", "离谱", "什么情况", "震惊", "离大谱"],
    "sadness":      ["破防", "难过", "emo", "泪目", "心疼", "哭了", "想哭", "好惨"],
    "disgust":      ["恶心", "作呕", "下头", "恶臭", "辣眼", "反胃", "呕"],
    "anger":        ["退游", "策划死", "气死", "滚", "辣鸡", "垃圾", "恶心", "骂人"],
    "anticipation": ["等你", "快更新", "下一集", "蹲", "求出", "催更", "期待"],
}


def validate_score_entry(entry: dict) -> None:
    """Raise ValueError if score entry is malformed."""
    required = {"chunk_id", "time_start", "time_end", "n_danmaku", "note"} | set(DIMENSIONS)
    missing = required - entry.keys()
    if missing:
        raise ValueError(f"missing keys: {missing}")
    for d in DIMENSIONS:
        v = entry[d]
        if not isinstance(v, int) or v < 0 or v > 10:
            raise ValueError(f"{d}={v} out of range [0,10] or not int")


def get_dominant_dimension(entry: dict) -> str:
    """Return the dimension with the highest score."""
    return max(DIMENSIONS, key=lambda d: entry.get(d, 0))
```

- [ ] **Step 4: 运行，确认通过**

```bash
pytest tests/test_plutchik.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add emoekg/_lib/plutchik.py tests/test_plutchik.py
git commit -m "feat(lib): add plutchik schema (8 dims, colors, keywords, validator)"
```

---

## Task 5：`bv_parser.py` —— URL 解析

**Files:**
- Create: `emoekg/emoekg/_lib/bv_parser.py`
- Create: `emoekg/tests/test_bv_parser.py`

- [ ] **Step 1: 写失败测试（覆盖 spec §1.3 需求 #1）**

`tests/test_bv_parser.py`：
```python
import pytest
from emoekg._lib.bv_parser import extract_bvid


@pytest.mark.parametrize("url,expected", [
    ("https://www.bilibili.com/video/BV18acMz4ELL", "BV18acMz4ELL"),
    ("https://www.bilibili.com/video/BV18acMz4ELL/", "BV18acMz4ELL"),
    ("https://www.bilibili.com/video/BV18acMz4ELL/?share_source=copy_web", "BV18acMz4ELL"),
    ("https://b23.tv/BV18acMz4ELL", "BV18acMz4ELL"),
    ("https://m.bilibili.com/video/BV18acMz4ELL", "BV18acMz4ELL"),
    ("BV18acMz4ELL", "BV18acMz4ELL"),
    ("bv18acmz4ell", "BV18acMz4ELL"),  # case normalization
])
def test_valid_inputs(url, expected):
    assert extract_bvid(url) == expected


@pytest.mark.parametrize("invalid", [
    "", "not-a-url", "https://youtube.com/watch?v=abc", "BV", "BV12",
])
def test_invalid_raises(invalid):
    with pytest.raises(ValueError):
        extract_bvid(invalid)
```

- [ ] **Step 2: 运行，确认失败**

- [ ] **Step 3: 实现**

`emoekg/_lib/bv_parser.py`：
```python
"""Extract BV id from various Bilibili URL forms."""
import re

# BV ids are 12 chars total: "BV" + 10 alphanumeric characters
_BV_PATTERN = re.compile(r"BV[A-Za-z0-9]{10}", re.IGNORECASE)


def extract_bvid(text: str) -> str:
    """
    Extract the canonical BVxxxxxxxxxx id from:
    - full bilibili.com video URLs (with or without query params)
    - b23.tv short links
    - mobile m.bilibili.com URLs
    - bare BV ids (any case)

    Raises ValueError if no valid BV id is found.
    """
    if not text:
        raise ValueError("empty input")
    m = _BV_PATTERN.search(text)
    if not m:
        raise ValueError(f"no BV id found in: {text!r}")
    # Normalize case: "BV" prefix uppercase, body preserves original case
    raw = m.group(0)
    return "BV" + raw[2:]
```

- [ ] **Step 4: 运行，确认通过 & 处理 case normalization**

```bash
pytest tests/test_bv_parser.py -v
```

如 `bv18acmz4ell` 这条失败（期望 `BV18acMz4ELL`），修改实现的最后一行——由于无法从小写恢复大小写，修改测试中的该用例：

改成：
```python
("bv18acMz4ELL", "BV18acMz4ELL"),  # only prefix case normalized
```

重跑直到 8 passed。

- [ ] **Step 5: Commit**

```bash
git add emoekg/_lib/bv_parser.py tests/test_bv_parser.py
git commit -m "feat(lib): add bv_parser with URL/shortlink/bare-id support"
```

---

## Task 6：`adaptive_window.py` —— 自适应窗口

**Files:**
- Create: `emoekg/emoekg/_lib/adaptive_window.py`
- Create: `emoekg/tests/test_adaptive_window.py`

- [ ] **Step 1: 写失败测试**

`tests/test_adaptive_window.py`：
```python
import pytest
from emoekg._lib.adaptive_window import compute_window_size, slice_by_window


def test_short_video_3min():
    # 180s / 90 target = 2s raw → friendly 5s
    assert compute_window_size(180) == 5


def test_medium_video_18min():
    # 1080 / 90 = 12 → friendly 15
    assert compute_window_size(18 * 60) == 15


def test_long_video_1h():
    # 3600/90=40 → friendly 45
    assert compute_window_size(3600) == 45


def test_very_long_3h():
    # 10800/90=120 → friendly 120
    assert compute_window_size(3 * 3600) == 120


def test_caps_at_180s():
    # for >= 4.5h: 16200/90=180 friendly; beyond that we cap
    assert compute_window_size(10 * 3600) == 180


def test_slice_empty():
    assert slice_by_window([], 15, total_duration=60) == [
        {"chunk_id": "C001", "time_start": 0, "time_end": 15, "danmakus": []},
        {"chunk_id": "C002", "time_start": 15, "time_end": 30, "danmakus": []},
        {"chunk_id": "C003", "time_start": 30, "time_end": 45, "danmakus": []},
        {"chunk_id": "C004", "time_start": 45, "time_end": 60, "danmakus": []},
    ]


def test_slice_with_danmakus():
    danmakus = [
        {"time": 2.1, "text": "a"},
        {"time": 7.5, "text": "b"},
        {"time": 16.0, "text": "c"},
    ]
    result = slice_by_window(danmakus, window_size=10, total_duration=30)
    assert len(result) == 3
    assert [d["text"] for d in result[0]["danmakus"]] == ["a", "b"]
    assert [d["text"] for d in result[1]["danmakus"]] == ["c"]
    assert result[2]["danmakus"] == []
```

- [ ] **Step 2: 运行，确认失败**

- [ ] **Step 3: 实现**

`emoekg/_lib/adaptive_window.py`：
```python
"""Adaptive window sizing and danmaku slicing."""

_FRIENDLY_WINDOWS = [5, 10, 15, 30, 45, 60, 90, 120, 180]
_TARGET_CHUNKS = 90


def compute_window_size(duration_sec: int) -> int:
    """Target ~90 chunks, snapped to friendly window sizes. Cap at 180s."""
    if duration_sec <= 0:
        return _FRIENDLY_WINDOWS[0]
    raw = duration_sec / _TARGET_CHUNKS
    for w in _FRIENDLY_WINDOWS:
        if w >= raw:
            return w
    return _FRIENDLY_WINDOWS[-1]


def slice_by_window(danmakus: list[dict], window_size: int,
                    total_duration: int) -> list[dict]:
    """
    Split danmakus into time-windowed chunks.

    Each danmaku must have a 'time' field (float seconds).
    Returns list of chunk dicts: {chunk_id, time_start, time_end, danmakus}.
    Chunks cover [0, total_duration] and may end with a partial last window.
    """
    chunks = []
    # sort danmakus by time (defensive)
    sorted_dm = sorted(danmakus, key=lambda d: d["time"])
    idx = 0
    chunk_num = 1
    t = 0
    while t < total_duration:
        end = min(t + window_size, total_duration)
        # collect danmakus whose time is in [t, end)
        bucket = []
        while idx < len(sorted_dm) and sorted_dm[idx]["time"] < end:
            if sorted_dm[idx]["time"] >= t:
                bucket.append(sorted_dm[idx])
            idx += 1
        chunks.append({
            "chunk_id": f"C{chunk_num:03d}",
            "time_start": t,
            "time_end": end,
            "danmakus": bucket,
        })
        t = end
        chunk_num += 1
    return chunks
```

- [ ] **Step 4: 运行，确认通过**

```bash
pytest tests/test_adaptive_window.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add emoekg/_lib/adaptive_window.py tests/test_adaptive_window.py
git commit -m "feat(lib): adaptive_window (friendly sizing + slice_by_window)"
```

---

# Phase 2：弹幕抓取

## Task 7：`danmaku_client.py` —— bilibili-api 封装

**Files:**
- Create: `emoekg/emoekg/_lib/danmaku_client.py`
- Create: `emoekg/tests/test_danmaku_client.py`

**背景说明**：`bilibili-api-python` 的 `Video` 对象有 `get_info()` 和 `get_danmakus(page_index)` 异步方法。本模块同步化封装 + 错误重试。由于真实 API 调用依赖网络，测试全部 mock。

- [ ] **Step 1: 写失败测试（全 mock）**

`tests/test_danmaku_client.py`：
```python
from unittest.mock import MagicMock, patch
import pytest
from emoekg._lib.danmaku_client import fetch_video_meta, fetch_all_danmakus


@patch("emoekg._lib.danmaku_client._get_video")
def test_fetch_video_meta(mock_get_video):
    fake_video = MagicMock()

    async def fake_info():
        return {
            "title": "Test Video",
            "owner": {"name": "TestUP"},
            "duration": 1080,
            "stat": {"view": 123456},
            "cid": 999,
        }
    fake_video.get_info = fake_info
    mock_get_video.return_value = fake_video

    meta = fetch_video_meta("BV18acMz4ELL")
    assert meta["bvid"] == "BV18acMz4ELL"
    assert meta["title"] == "Test Video"
    assert meta["up"] == "TestUP"
    assert meta["duration_sec"] == 1080
    assert meta["view_count"] == 123456
    assert meta["cid"] == 999


@patch("emoekg._lib.danmaku_client._get_video")
def test_fetch_all_danmakus_single_page(mock_get_video):
    fake_dm = MagicMock()
    fake_dm.progress = 12340  # milliseconds
    fake_dm.content = "test"
    fake_dm.mode = 1
    fake_dm.color = 16777215
    fake_dm.fontsize = 25
    fake_dm.midHash = "abc"

    fake_video = MagicMock()

    async def fake_get_dm(page_index):
        if page_index == 0:
            return [fake_dm]
        return []
    fake_video.get_danmakus = fake_get_dm
    mock_get_video.return_value = fake_video

    dms = fetch_all_danmakus("BV18acMz4ELL", duration_sec=60)
    assert len(dms) == 1
    assert dms[0]["time"] == pytest.approx(12.34)
    assert dms[0]["text"] == "test"
    assert dms[0]["mode"] == 1
```

- [ ] **Step 2: 运行，确认失败**

- [ ] **Step 3: 实现**

`emoekg/_lib/danmaku_client.py`：
```python
"""Sync wrapper over bilibili-api-python."""
import asyncio
import time
from bilibili_api import video


def _get_video(bvid: str):
    """Factory hook for mocking in tests."""
    return video.Video(bvid=bvid)


def _run(coro):
    """Run an async coroutine in a sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


def fetch_video_meta(bvid: str, retries: int = 3) -> dict:
    """Fetch video metadata. Normalized dict keyed to our schema."""
    v = _get_video(bvid)
    last_exc = None
    for attempt in range(retries):
        try:
            info = _run(v.get_info())
            return {
                "bvid": bvid,
                "title": info.get("title", ""),
                "up": info.get("owner", {}).get("name", ""),
                "duration_sec": int(info.get("duration", 0)),
                "view_count": int(info.get("stat", {}).get("view", 0)),
                "cid": int(info.get("cid", 0)),
            }
        except Exception as e:  # noqa: BLE001
            last_exc = e
            time.sleep(1.5 ** attempt)
    raise RuntimeError(f"fetch_video_meta failed after {retries} attempts") from last_exc


def fetch_all_danmakus(bvid: str, duration_sec: int, retries: int = 3) -> list[dict]:
    """
    Fetch all danmakus via Protobuf segmented API (6-min segments).
    Returns list of normalized dicts: {time, text, mode, color, fontsize, user_hash}.
    """
    v = _get_video(bvid)
    # one segment = 360 seconds, page_index starts at 0
    num_pages = max(1, (duration_sec // 360) + 1)
    all_dms = []
    for page in range(num_pages):
        last_exc = None
        for attempt in range(retries):
            try:
                raw = _run(v.get_danmakus(page_index=page))
                for dm in raw:
                    all_dms.append({
                        "time": round(dm.progress / 1000.0, 3),
                        "text": dm.content,
                        "mode": dm.mode,
                        "color": int(dm.color),
                        "fontsize": int(dm.fontsize),
                        "user_hash": dm.midHash,
                    })
                break
            except Exception as e:  # noqa: BLE001
                last_exc = e
                time.sleep(1.5 ** attempt)
        else:
            raise RuntimeError(f"fetch_danmakus page={page} failed") from last_exc
    # dedupe exact (time, text, user_hash) triples
    seen = set()
    unique = []
    for d in all_dms:
        key = (d["time"], d["text"], d["user_hash"])
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique
```

- [ ] **Step 4: 运行，确认通过**

```bash
pytest tests/test_danmaku_client.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add emoekg/_lib/danmaku_client.py tests/test_danmaku_client.py
git commit -m "feat(lib): danmaku_client with sync wrapper, retry, dedup"
```

---

## Task 8：Stage 1 —— `scripts/fetch_danmaku.py`

**Files:**
- Create: `emoekg/scripts/fetch_danmaku.py`
- Create: `emoekg/tests/test_stage1_fetch.py`

- [ ] **Step 1: 写一个集成级测试（mock 网络层）**

`tests/test_stage1_fetch.py`：
```python
import json
from unittest.mock import patch
from pathlib import Path
import sys

# import the stage1 script as a module
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import fetch_danmaku  # noqa: E402


@patch("fetch_danmaku.fetch_all_danmakus")
@patch("fetch_danmaku.fetch_video_meta")
def test_stage1_produces_meta_and_danmaku_json(mock_meta, mock_dms, tmp_working_dir):
    mock_meta.return_value = {
        "bvid": "BVTEST", "title": "T", "up": "U",
        "duration_sec": 60, "view_count": 0, "cid": 1,
    }
    mock_dms.return_value = [
        {"time": 1.0, "text": "a", "mode": 1, "color": 0xFFFFFF, "fontsize": 25, "user_hash": "h1"}
    ]

    fetch_danmaku.run("BV18acMz4ELL", tmp_working_dir, force=False)

    meta = json.loads((tmp_working_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["bvid"] == "BVTEST"
    assert "fetched_at" in meta

    dms = json.loads((tmp_working_dir / "danmaku.json").read_text(encoding="utf-8"))
    assert len(dms) == 1
    assert dms[0]["text"] == "a"


@patch("fetch_danmaku.fetch_all_danmakus")
@patch("fetch_danmaku.fetch_video_meta")
def test_stage1_idempotent_skip(mock_meta, mock_dms, tmp_working_dir):
    # pre-populate both files
    (tmp_working_dir / "meta.json").write_text('{"bvid":"X"}', encoding="utf-8")
    (tmp_working_dir / "danmaku.json").write_text('[]', encoding="utf-8")
    fetch_danmaku.run("BV18acMz4ELL", tmp_working_dir, force=False)
    mock_meta.assert_not_called()
    mock_dms.assert_not_called()
```

- [ ] **Step 2: 运行，确认失败**

- [ ] **Step 3: 实现**

`scripts/fetch_danmaku.py`：
```python
"""Stage 1: fetch video metadata and all danmakus into JSON files."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# allow running as a script or as module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from emoekg._lib.bv_parser import extract_bvid
from emoekg._lib.danmaku_client import fetch_video_meta, fetch_all_danmakus


def run(url_or_bvid: str, working_dir: Path, force: bool = False) -> None:
    working_dir = Path(working_dir)
    working_dir.mkdir(parents=True, exist_ok=True)

    meta_path = working_dir / "meta.json"
    dm_path = working_dir / "danmaku.json"

    if not force and meta_path.exists() and dm_path.exists():
        print(f"[SKIP] Stage 1: meta.json and danmaku.json already exist in {working_dir}")
        return

    bvid = extract_bvid(url_or_bvid)
    print(f"[Stage 1] Fetching metadata for {bvid}...")
    meta = fetch_video_meta(bvid)
    meta["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  meta: {meta['title']} | {meta['duration_sec']}s | UP: {meta['up']}")

    print(f"[Stage 1] Fetching all danmakus (duration={meta['duration_sec']}s)...")
    dms = fetch_all_danmakus(bvid, meta["duration_sec"])
    dm_path.write_text(json.dumps(dms, ensure_ascii=False), encoding="utf-8")
    print(f"  danmakus: {len(dms)} total (deduped)")

    print(f"[Stage 1] Done. Output: {working_dir}")


def main():
    ap = argparse.ArgumentParser(description="emoekg Stage 1: fetch danmaku")
    ap.add_argument("url", help="B站视频 URL 或 BV id")
    ap.add_argument("-o", "--output", required=True, help="工作目录路径")
    ap.add_argument("--force", action="store_true", help="忽略缓存重新拉取")
    args = ap.parse_args()
    run(args.url, Path(args.output), force=args.force)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_stage1_fetch.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_danmaku.py tests/test_stage1_fetch.py
git commit -m "feat(stage1): fetch_danmaku.py with idempotent caching"
```

---

# Phase 3：切片 & Stage 2

## Task 9：`templates/chunks_prompt.md.j2` —— Stage 2 模板

**Files:**
- Create: `emoekg/templates/chunks_prompt.md.j2`

- [ ] **Step 1: 创建模板**

`templates/chunks_prompt.md.j2`：
```jinja2
# Danmaku Chunks for {{ meta.bvid }}
Video: 《{{ meta.title }}》| UP: {{ meta.up }} | Duration: {{ duration_hms }} | Total: {{ total_danmaku }} 弹幕
Window size: {{ window_size }}s | Total chunks: {{ chunks | length }}

---

{% for chunk in chunks -%}
## [{{ chunk.chunk_id }}] {{ chunk.time_start_hms }} – {{ chunk.time_end_hms }} (n={{ chunk.danmakus | length }}{% if chunk.danmakus | length < 3 %}, SPARSE{% endif %})
{% for dm in chunk.display_danmakus -%}
- {{ dm.time_hms }} {{ dm.text }}
{% endfor %}
{% endfor %}
```

- [ ] **Step 2: Commit**

```bash
git add templates/chunks_prompt.md.j2
git commit -m "feat(templates): chunks_prompt.md.j2 for Stage 2 output"
```

---

## Task 10：Stage 2 —— `scripts/slice_chunks.py`

**Files:**
- Create: `emoekg/scripts/slice_chunks.py`
- Create: `emoekg/tests/test_stage2_slice.py`

- [ ] **Step 1: 写失败测试**

`tests/test_stage2_slice.py`：
```python
import json
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import slice_chunks  # noqa: E402


def _write_fixtures(wd: Path):
    (wd / "meta.json").write_text(json.dumps({
        "bvid": "BVTEST", "title": "T", "up": "U",
        "duration_sec": 60, "view_count": 0, "cid": 1,
        "fetched_at": "2026-05-07T00:00:00",
    }), encoding="utf-8")
    (wd / "danmaku.json").write_text(json.dumps([
        {"time": 2.0, "text": "开场", "mode": 1, "color": 0xFFFFFF, "fontsize": 25, "user_hash": "h1"},
        {"time": 3.5, "text": "666", "mode": 1, "color": 0xFFFFFF, "fontsize": 25, "user_hash": "h2"},
        {"time": 20.0, "text": "什么情况", "mode": 1, "color": 0xFFFFFF, "fontsize": 25, "user_hash": "h3"},
    ]), encoding="utf-8")


def test_stage2_produces_chunks_md_and_scores_skeleton(tmp_working_dir):
    _write_fixtures(tmp_working_dir)
    slice_chunks.run(tmp_working_dir, force=False)
    chunks_text = (tmp_working_dir / "chunks.md").read_text(encoding="utf-8")
    assert "Danmaku Chunks for BVTEST" in chunks_text
    assert "[C001]" in chunks_text
    assert "开场" in chunks_text
    # scores.json should exist with empty list
    scores = json.loads((tmp_working_dir / "scores.json").read_text(encoding="utf-8"))
    assert scores == []


def test_stage2_marks_sparse_chunks(tmp_working_dir):
    _write_fixtures(tmp_working_dir)
    slice_chunks.run(tmp_working_dir, force=False)
    chunks_text = (tmp_working_dir / "chunks.md").read_text(encoding="utf-8")
    # window_size for 60s → compute_window_size returns 5s, so many empty/sparse chunks
    assert "SPARSE" in chunks_text
```

- [ ] **Step 2: 运行，确认失败**

- [ ] **Step 3: 实现**

`scripts/slice_chunks.py`：
```python
"""Stage 2: slice danmakus into chunks and produce chunks.md + scores.json skeleton."""
import argparse
import json
import random
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from emoekg._lib.adaptive_window import compute_window_size, slice_by_window
from emoekg._lib.time_utils import format_hms


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
DENSE_THRESHOLD = 150
DENSE_SAMPLE_HEAD = 30
DENSE_SAMPLE_TAIL = 30
DENSE_SAMPLE_MID = 90


def _sample_dense(danmakus: list[dict]) -> list[dict]:
    """When a chunk has > 150 danmakus, sample head 30 + tail 30 + random mid 90."""
    if len(danmakus) <= DENSE_THRESHOLD:
        return danmakus
    head = danmakus[:DENSE_SAMPLE_HEAD]
    tail = danmakus[-DENSE_SAMPLE_TAIL:]
    mid_pool = danmakus[DENSE_SAMPLE_HEAD:-DENSE_SAMPLE_TAIL]
    mid = random.sample(mid_pool, min(DENSE_SAMPLE_MID, len(mid_pool)))
    mid.sort(key=lambda d: d["time"])
    return head + mid + tail


def run(working_dir: Path, force: bool = False) -> None:
    working_dir = Path(working_dir)
    chunks_md = working_dir / "chunks.md"
    scores_json = working_dir / "scores.json"

    if not force and chunks_md.exists() and scores_json.exists():
        print(f"[SKIP] Stage 2: chunks.md and scores.json already exist")
        return

    meta = json.loads((working_dir / "meta.json").read_text(encoding="utf-8"))
    dms = json.loads((working_dir / "danmaku.json").read_text(encoding="utf-8"))
    duration = meta["duration_sec"]
    window_size = compute_window_size(duration)

    print(f"[Stage 2] Slicing {len(dms)} danmakus into {duration}s windows...")
    chunks = slice_by_window(dms, window_size, duration)

    # enrich with display fields
    for chunk in chunks:
        chunk["time_start_hms"] = format_hms(chunk["time_start"])
        chunk["time_end_hms"] = format_hms(chunk["time_end"])
        chunk["display_danmakus"] = [
            {"time_hms": format_hms(d["time"]), "text": d["text"]}
            for d in _sample_dense(chunk["danmakus"])
        ]

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True, lstrip_blocks=True,
    )
    tpl = env.get_template("chunks_prompt.md.j2")
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
    print(f"[Stage 2] Done. {len(chunks)} chunks, window={window_size}s")


def main():
    ap = argparse.ArgumentParser(description="emoekg Stage 2: slice chunks")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    run(Path(args.output), force=args.force)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_stage2_slice.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/slice_chunks.py tests/test_stage2_slice.py
git commit -m "feat(stage2): slice_chunks.py (adaptive windowing, dense sampling)"
```

---

# Phase 4：算法模块（转折点检测）

## Task 11：`turnpoint_algo.py` —— 峰值 / 谷值检测

**Files:**
- Create: `emoekg/emoekg/_lib/turnpoint_algo.py`（首次添加 peak/valley 部分）
- Create: `emoekg/tests/test_turnpoint_algo.py`

- [ ] **Step 1: 写失败测试（合成曲线 → 期望的峰/谷）**

`tests/test_turnpoint_algo.py`：
```python
from emoekg._lib.turnpoint_algo import find_peaks_valleys


def _make_scores(series: dict[str, list[int]]) -> list[dict]:
    """Build a list of score entries from per-dimension arrays."""
    from emoekg._lib.plutchik import DIMENSIONS
    n = len(next(iter(series.values())))
    entries = []
    for i in range(n):
        entry = {"chunk_id": f"C{i+1:03d}", "time_start": i * 15, "time_end": (i + 1) * 15,
                 "n_danmaku": 20, "note": ""}
        for d in DIMENSIONS:
            entry[d] = series.get(d, [0] * n)[i]
        entries.append(entry)
    return entries


def test_find_single_joy_peak():
    joy = [1, 2, 3, 9, 3, 2, 1, 1, 1, 1]  # peak at index 3
    scores = _make_scores({"joy": joy})
    result = find_peaks_valleys(scores)
    peak_ids = [r["chunk_id"] for r in result if r["type"] == "peak" and r["main_dimension"] == "joy"]
    assert "C004" in peak_ids


def test_ignores_small_bumps():
    joy = [1, 2, 3, 4, 3, 2, 1] * 3  # max=4, below threshold 6
    scores = _make_scores({"joy": joy})
    result = find_peaks_valleys(scores)
    assert not any(r["type"] == "peak" and r["main_dimension"] == "joy" for r in result)


def test_detects_valleys_for_sustained_high_baseline():
    # anger high baseline 8 with a dip to 1 in the middle
    anger = [8, 8, 8, 8, 8, 1, 8, 8, 8, 8]
    scores = _make_scores({"anger": anger})
    result = find_peaks_valleys(scores)
    valleys = [r for r in result if r["type"] == "valley" and r["main_dimension"] == "anger"]
    assert len(valleys) >= 1
```

- [ ] **Step 2: 运行，确认失败**

- [ ] **Step 3: 实现**

`emoekg/_lib/turnpoint_algo.py`（先实现 peak/valley 部分，JS 散度下一任务追加）：
```python
"""Turnpoint detection: peak/valley on each dimension + JS divergence between windows."""
from __future__ import annotations
import numpy as np
from scipy.signal import find_peaks

from emoekg._lib.plutchik import DIMENSIONS

PEAK_HEIGHT = 6          # only consider scores >= 6 as peaks
PEAK_DISTANCE = 3        # peaks must be >=3 chunks apart
PEAK_PROMINENCE = 2      # peak stands out by at least 2


def find_peaks_valleys(scores: list[dict]) -> list[dict]:
    """Return a list of candidate turnpoints (type=peak|valley) from per-dim scores."""
    if not scores:
        return []
    results: list[dict] = []
    for dim in DIMENSIONS:
        series = np.array([s.get(dim, 0) for s in scores], dtype=float)
        peaks, _ = find_peaks(series, height=PEAK_HEIGHT,
                              distance=PEAK_DISTANCE, prominence=PEAK_PROMINENCE)
        valleys, _ = find_peaks(-series, height=-(10 - PEAK_HEIGHT),
                                distance=PEAK_DISTANCE, prominence=PEAK_PROMINENCE)
        for idx in peaks:
            results.append({
                "chunk_id": scores[int(idx)]["chunk_id"],
                "chunk_index": int(idx),
                "type": "peak",
                "main_dimension": dim,
                "direction": "up",
                "magnitude": float(series[idx]),
                "description": f"{dim} 峰值 {series[idx]:.0f}",
            })
        for idx in valleys:
            # only valley if the dimension baseline was meaningfully high before/after
            neighbor = max(
                series[max(0, idx - 2):idx].max(initial=0),
                series[idx + 1:idx + 3].max(initial=0),
            )
            if neighbor >= PEAK_HEIGHT:
                results.append({
                    "chunk_id": scores[int(idx)]["chunk_id"],
                    "chunk_index": int(idx),
                    "type": "valley",
                    "main_dimension": dim,
                    "direction": "down",
                    "magnitude": float(series[idx]),
                    "description": f"{dim} 谷值 {series[idx]:.0f}",
                })
    return results
```

- [ ] **Step 4: 运行，确认通过**

```bash
pytest tests/test_turnpoint_algo.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add emoekg/_lib/turnpoint_algo.py tests/test_turnpoint_algo.py
git commit -m "feat(lib): turnpoint_algo peak/valley detection via scipy"
```

---

## Task 12：`turnpoint_algo.py` —— JS 散度 + 合并去重

**Files:**
- Modify: `emoekg/emoekg/_lib/turnpoint_algo.py`
- Modify: `emoekg/tests/test_turnpoint_algo.py`（追加用例）

- [ ] **Step 1: 追加失败测试**

追加到 `tests/test_turnpoint_algo.py` 末尾：
```python
from emoekg._lib.turnpoint_algo import find_shifts, merge_turnpoints


def test_find_shifts_detects_sharp_switch():
    # frames 0-4 are all joy; 5-9 switch to all anger
    series = {"joy": [8, 8, 8, 8, 8, 0, 0, 0, 0, 0],
              "anger": [0, 0, 0, 0, 0, 8, 8, 8, 8, 8]}
    scores = _make_scores(series)
    shifts = find_shifts(scores)
    shift_indices = [s["chunk_index"] for s in shifts]
    assert any(4 <= i <= 6 for i in shift_indices)


def test_merge_deduplicates_nearby_turnpoints():
    a = {"chunk_id": "C010", "chunk_index": 9, "type": "peak",
         "main_dimension": "joy", "direction": "up", "magnitude": 9.0, "description": "x"}
    b = {"chunk_id": "C011", "chunk_index": 10, "type": "shift",
         "main_dimension": "joy", "direction": "up", "magnitude": 0.5, "description": "y"}
    merged = merge_turnpoints([a, b], window_size=15)
    assert len(merged) == 1
    # higher-magnitude one wins
    assert merged[0]["type"] == "peak"


def test_merge_caps_total():
    tps = [{"chunk_id": f"C{i:03d}", "chunk_index": i * 5, "type": "peak",
            "main_dimension": "joy", "direction": "up", "magnitude": float(i),
            "description": ""} for i in range(30)]
    merged = merge_turnpoints(tps, window_size=15, max_total=15)
    assert len(merged) <= 15
```

- [ ] **Step 2: 运行，确认失败**

- [ ] **Step 3: 追加实现**

追加到 `emoekg/_lib/turnpoint_algo.py` 末尾：
```python
# ----------------- JS divergence shift detection -----------------

JS_THRESHOLD = 0.15
SHIFT_WINDOW = 3


def _normalize(vec: np.ndarray) -> np.ndarray:
    s = vec.sum()
    if s <= 0:
        return np.full_like(vec, 1.0 / len(vec))
    return vec / s


def _js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    m = 0.5 * (p + q)
    def _kl(a, b):
        a = np.where(a == 0, 1e-12, a)
        b = np.where(b == 0, 1e-12, b)
        return np.sum(a * np.log2(a / b))
    return 0.5 * _kl(p, m) + 0.5 * _kl(q, m)


def find_shifts(scores: list[dict]) -> list[dict]:
    """Find chunks where the prior/subsequent emotion distributions diverge sharply."""
    results: list[dict] = []
    n = len(scores)
    if n < 2 * SHIFT_WINDOW:
        return results
    matrix = np.array([[s.get(d, 0) for d in DIMENSIONS] for s in scores], dtype=float)
    for i in range(SHIFT_WINDOW, n - SHIFT_WINDOW):
        prev = _normalize(matrix[i - SHIFT_WINDOW:i].sum(axis=0))
        nxt = _normalize(matrix[i:i + SHIFT_WINDOW].sum(axis=0))
        js = _js_divergence(prev, nxt)
        if js >= JS_THRESHOLD:
            diff = matrix[i:i + SHIFT_WINDOW].mean(axis=0) - matrix[i - SHIFT_WINDOW:i].mean(axis=0)
            top_idx = int(np.argmax(np.abs(diff)))
            dim = DIMENSIONS[top_idx]
            direction = "up" if diff[top_idx] > 0 else "down"
            results.append({
                "chunk_id": scores[i]["chunk_id"],
                "chunk_index": i,
                "type": "shift",
                "main_dimension": dim,
                "direction": direction,
                "magnitude": float(abs(diff[top_idx])),
                "description": f"{dim} {'飙升' if direction == 'up' else '骤降'} "
                               f"(Δ{diff[top_idx]:+.1f}, JS={js:.2f})",
            })
    return results


def merge_turnpoints(turnpoints: list[dict], window_size: int,
                     max_total: int = 15) -> list[dict]:
    """
    Merge turnpoints whose chunk_index gap < 2 windows worth of chunks.
    When merging, keep the one with the largest magnitude.
    Cap final list at max_total, sorted by time (chunk_index).
    """
    if not turnpoints:
        return []
    sorted_tps = sorted(turnpoints, key=lambda t: t["chunk_index"])
    GAP = 2  # chunks
    clusters: list[list[dict]] = []
    for tp in sorted_tps:
        if clusters and tp["chunk_index"] - clusters[-1][-1]["chunk_index"] <= GAP:
            clusters[-1].append(tp)
        else:
            clusters.append([tp])
    winners = [max(c, key=lambda t: t["magnitude"]) for c in clusters]
    # cap: keep top-N by magnitude then re-sort by time
    if len(winners) > max_total:
        winners = sorted(winners, key=lambda t: t["magnitude"], reverse=True)[:max_total]
    winners.sort(key=lambda t: t["chunk_index"])
    # assign final turnpoint_id
    for i, tp in enumerate(winners, 1):
        tp["turnpoint_id"] = f"TP{i:02d}"
    return winners
```

- [ ] **Step 4: 运行，确认全部通过**

```bash
pytest tests/test_turnpoint_algo.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add emoekg/_lib/turnpoint_algo.py tests/test_turnpoint_algo.py
git commit -m "feat(lib): JS-divergence shift detection + merge_turnpoints"
```

---

## Task 13：`evidence_picker.py` —— 佐证弹幕选取

**Files:**
- Create: `emoekg/emoekg/_lib/evidence_picker.py`
- Create: `emoekg/tests/test_evidence_picker.py`

- [ ] **Step 1: 写失败测试**

`tests/test_evidence_picker.py`：
```python
from emoekg._lib.evidence_picker import pick_evidence


def _dm(t, text, user_hash="u"):
    return {"time": t, "text": text, "mode": 1, "color": 0xFFFFFF,
            "fontsize": 25, "user_hash": user_hash}


def test_prefers_keyword_matches_for_dimension():
    danmakus = [
        _dm(1.0, "666", "u1"),
        _dm(2.0, "我直接退游", "u2"),      # anger keyword: 退游
        _dm(3.0, "策划死妈", "u3"),        # anger keyword
        _dm(4.0, "辣鸡游戏", "u4"),        # anger keyword
        _dm(5.0, "真的气死了", "u5"),      # anger keyword: 气死
        _dm(6.0, "好的", "u6"),
        _dm(7.0, "垃圾策划", "u7"),        # anger keyword
    ]
    picked = pick_evidence(danmakus, dimension="anger", target=5)
    texts = [d["text"] for d in picked]
    # all 5 should be keyword matches
    assert "666" not in texts
    assert "好的" not in texts
    assert len(picked) == 5


def test_dedupes_duplicate_users_and_texts():
    danmakus = [
        _dm(1.0, "退游", "u1"),
        _dm(2.0, "退游", "u1"),     # same user, same text → drop
        _dm(3.0, "退游", "u2"),     # different user, same text → drop (exact text dup)
        _dm(4.0, "气死", "u3"),
    ]
    picked = pick_evidence(danmakus, dimension="anger", target=5)
    texts = [d["text"] for d in picked]
    assert texts.count("退游") == 1


def test_falls_back_to_longest_when_not_enough_keyword_hits():
    danmakus = [
        _dm(1.0, "a", "u1"),
        _dm(2.0, "这条弹幕很长描述了很多东西", "u2"),
        _dm(3.0, "短", "u3"),
        _dm(4.0, "也还行吧", "u4"),
    ]
    picked = pick_evidence(danmakus, dimension="anger", target=2)
    assert picked[0]["text"].startswith("这条弹幕")  # longest first
```

- [ ] **Step 2: 运行，确认失败**

- [ ] **Step 3: 实现**

`emoekg/_lib/evidence_picker.py`：
```python
"""Pick the most persuasive danmakus as evidence for a turnpoint's dominant dimension."""
from emoekg._lib.plutchik import KEYWORDS


def _dedup_key(dm: dict) -> tuple:
    return (dm["user_hash"], dm["text"])


def pick_evidence(danmakus: list[dict], dimension: str, target: int = 5) -> list[dict]:
    """
    Pick up to `target` danmakus that best exemplify `dimension`.
    Priority:
      1. Contains keywords for `dimension`
      2. Longer text (more informative)
      3. De-duplicate identical (user_hash, text) pairs and identical texts
    """
    keywords = KEYWORDS.get(dimension, [])
    scored: list[tuple[int, int, dict]] = []
    seen_exact_text = set()
    seen_user_text = set()
    for d in danmakus:
        key = _dedup_key(d)
        if key in seen_user_text or d["text"] in seen_exact_text:
            continue
        seen_user_text.add(key)
        seen_exact_text.add(d["text"])
        kw_hits = sum(1 for k in keywords if k in d["text"])
        scored.append((kw_hits, len(d["text"]), d))
    # sort: keyword hits desc, length desc, time asc
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]["time"]))
    return [t[2] for t in scored[:target]]
```

- [ ] **Step 4: 运行，确认通过**

```bash
pytest tests/test_evidence_picker.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add emoekg/_lib/evidence_picker.py tests/test_evidence_picker.py
git commit -m "feat(lib): evidence_picker (keyword > length > dedup priority)"
```

---

# Phase 5：Stage 4 转折点整合

## Task 14：Stage 4 —— `scripts/detect_turnpoints.py`

**Files:**
- Create: `emoekg/scripts/detect_turnpoints.py`
- Create: `emoekg/tests/test_stage4_detect.py`

- [ ] **Step 1: 写失败测试**

`tests/test_stage4_detect.py`：
```python
import json
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import detect_turnpoints  # noqa: E402


def _write_fixtures(wd: Path):
    (wd / "meta.json").write_text(json.dumps({
        "bvid": "BVTEST", "duration_sec": 150, "title": "t", "up": "u",
        "view_count": 0, "cid": 1, "fetched_at": "2026-05-07T00:00:00",
    }), encoding="utf-8")
    # 10 chunks, joy peaks at C004 and C008
    joy_vals = [1, 2, 3, 9, 4, 2, 2, 9, 3, 1]
    scores = []
    for i, j in enumerate(joy_vals):
        scores.append({
            "chunk_id": f"C{i+1:03d}", "time_start": i * 15, "time_end": (i + 1) * 15,
            "n_danmaku": 20,
            "joy": j, "trust": 0, "fear": 0, "surprise": 0,
            "sadness": 0, "disgust": 0, "anger": 0, "anticipation": 0,
            "note": "",
        })
    (wd / "scores.json").write_text(json.dumps(scores), encoding="utf-8")
    dms = [{"time": i * 3, "text": f"好好笑{i}", "mode": 1, "color": 0xFFFFFF,
            "fontsize": 25, "user_hash": f"u{i}"} for i in range(50)]
    (wd / "danmaku.json").write_text(json.dumps(dms), encoding="utf-8")


def test_stage4_produces_turnpoints_with_evidence(tmp_working_dir):
    _write_fixtures(tmp_working_dir)
    detect_turnpoints.run(tmp_working_dir, force=False)
    tps = json.loads((tmp_working_dir / "turnpoints.json").read_text(encoding="utf-8"))
    assert len(tps) >= 1
    for tp in tps:
        assert tp["turnpoint_id"].startswith("TP")
        assert tp["type"] in ("peak", "valley", "shift")
        assert len(tp["evidence_danmakus"]) >= 1
        assert "time" in tp["evidence_danmakus"][0]


def test_stage4_validates_score_completeness(tmp_working_dir):
    _write_fixtures(tmp_working_dir)
    scores = json.loads((tmp_working_dir / "scores.json").read_text(encoding="utf-8"))
    scores.pop()  # remove last chunk
    (tmp_working_dir / "scores.json").write_text(json.dumps(scores), encoding="utf-8")
    # But we have 10 chunks expected by duration (150/15=10)
    try:
        detect_turnpoints.run(tmp_working_dir, force=True)
    except SystemExit as e:
        assert e.code != 0
```

- [ ] **Step 2: 运行，确认失败**

- [ ] **Step 3: 实现**

`scripts/detect_turnpoints.py`：
```python
"""Stage 4: detect turnpoints from scores.json and attach evidence danmakus."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from emoekg._lib.plutchik import validate_score_entry
from emoekg._lib.turnpoint_algo import find_peaks_valleys, find_shifts, merge_turnpoints
from emoekg._lib.evidence_picker import pick_evidence
from emoekg._lib.adaptive_window import compute_window_size


def _validate_scores(scores, expected_count: int) -> None:
    if len(scores) != expected_count:
        print(f"[ERROR] scores.json has {len(scores)} entries, expected {expected_count}",
              file=sys.stderr)
        sys.exit(2)
    zero_chunks = 0
    for s in scores:
        validate_score_entry(s)
        if s["n_danmaku"] >= 3 and all(s.get(k, 0) == 0 for k in
                ["joy","trust","fear","surprise","sadness","disgust","anger","anticipation"]):
            zero_chunks += 1
    if expected_count and zero_chunks / expected_count > 0.20:
        print(f"[WARN] {zero_chunks}/{expected_count} non-sparse chunks all-zero "
              "(Agent may have skipped scoring)", file=sys.stderr)


def run(working_dir: Path, force: bool = False) -> None:
    working_dir = Path(working_dir)
    tp_path = working_dir / "turnpoints.json"
    if not force and tp_path.exists():
        print("[SKIP] Stage 4: turnpoints.json already exists")
        return

    meta = json.loads((working_dir / "meta.json").read_text(encoding="utf-8"))
    scores = json.loads((working_dir / "scores.json").read_text(encoding="utf-8"))
    dms = json.loads((working_dir / "danmaku.json").read_text(encoding="utf-8"))
    window_size = compute_window_size(meta["duration_sec"])
    expected_chunks = (meta["duration_sec"] + window_size - 1) // window_size
    _validate_scores(scores, expected_chunks)

    peaks = find_peaks_valleys(scores)
    shifts = find_shifts(scores)
    merged = merge_turnpoints(peaks + shifts, window_size=window_size)
    print(f"[Stage 4] Found {len(peaks)} peaks/valleys + {len(shifts)} shifts → {len(merged)} after merge")

    # index danmakus by chunk
    def _chunk_of(t: float) -> int:
        return min(int(t // window_size), expected_chunks - 1)
    chunk_buckets: dict[int, list] = {}
    for d in dms:
        chunk_buckets.setdefault(_chunk_of(d["time"]), []).append(d)

    for tp in merged:
        idx = tp["chunk_index"]
        pool = list(chunk_buckets.get(idx, []))
        if len(pool) < 5:
            pool += chunk_buckets.get(idx - 1, []) + chunk_buckets.get(idx + 1, [])
        evidence = pick_evidence(pool, tp["main_dimension"], target=5)
        tp["evidence_danmakus"] = [
            {"time": d["time"], "text": d["text"], "color": d["color"]}
            for d in evidence
        ]
        tp["time_start"] = scores[idx]["time_start"]
        tp["time_end"] = scores[idx]["time_end"]

    tp_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Stage 4] Done. Wrote {len(merged)} turnpoints")


def main():
    ap = argparse.ArgumentParser(description="emoekg Stage 4: detect turnpoints")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    run(Path(args.output), force=args.force)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_stage4_detect.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/detect_turnpoints.py tests/test_stage4_detect.py
git commit -m "feat(stage4): detect_turnpoints.py (merge + evidence attach)"
```

---

# Phase 6：HTML 报告（Stage 5）

**说明**：HTML 报告是"前端产物"，浏览器行为很难做纯单元测试。本阶段每个 Task 采取 "写代码 → 手动浏览器验证 clicklist → commit" 节奏。最终由 Task 27 跑真实视频做一次端到端验证。

## Task 15：下载 ECharts 离线 UMD 包

**Files:**
- Create: `emoekg/templates/vendor/echarts.min.js`

- [ ] **Step 1: 下载 ECharts 5.5 最小化包**

```bash
mkdir -p templates/vendor
curl -L -o templates/vendor/echarts.min.js https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js
```

Expected: 文件大小约 900KB

- [ ] **Step 2: 验证文件可用**

```bash
python -c "p=open('templates/vendor/echarts.min.js').read(); assert 'echarts' in p[:200]; print('ok', len(p), 'bytes')"
```

Expected: `ok 9xxxxx bytes`

- [ ] **Step 3: Commit**

```bash
git add templates/vendor/echarts.min.js
git commit -m "chore: vendor ECharts 5.5 for inline embedding"
```

---

## Task 16：`report.html.j2` 骨架 —— 布局 + 元信息 + 数据注入

**Files:**
- Create: `emoekg/templates/report.html.j2`

- [ ] **Step 1: 创建模板主骨架**

`templates/report.html.j2`：
```jinja2
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🫀 emoekg · {{ meta.title }}</title>
<style>
:root { --bg:#0f1419; --fg:#e6e6e6; --muted:#8a94a6; --card:#1a2028; --accent:#F4D03F; }
* { box-sizing: border-box; }
body { margin:0; font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
       background:var(--bg); color:var(--fg); line-height:1.6; }
.container { max-width:1400px; margin:0 auto; padding:20px; }
header { padding:16px 0 24px; border-bottom:1px solid #2a3340; }
header h1 { margin:0 0 8px; font-size:22px; }
header .meta { color:var(--muted); font-size:13px; }
header .meta a { color:var(--accent); text-decoration:none; margin-left:12px; }
.panel { background:var(--card); border:1px solid #2a3340; border-radius:8px;
         padding:16px; margin:16px 0; }
.panel h2 { margin:0 0 12px; font-size:16px; color:var(--accent); }
.layout { display:grid; grid-template-columns: 1fr 1fr; gap:16px; }
@media (max-width:900px) { .layout { grid-template-columns: 1fr; } }
#video-wrapper, #video-wrapper iframe, #video-wrapper video {
  width:100%; aspect-ratio: 16/9; border:0; background:#000; border-radius:4px;
}
#danmaku-list { max-height:400px; overflow-y:auto; font-size:13px; }
#danmaku-list .item { padding:4px 8px; border-left:3px solid transparent; cursor:pointer; }
#danmaku-list .item:hover { background:#222a33; }
#danmaku-list .item.active { background:#2a3340; border-left-color:var(--accent); }
#danmaku-list .time { color:var(--muted); margin-right:8px; font-family:monospace; }
#danmaku-list .dot { display:inline-block; width:8px; height:8px; border-radius:50%;
                     margin-left:6px; vertical-align:middle; }
.filter-bar { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:8px; }
.filter-bar button { background:#2a3340; color:var(--fg); border:0; padding:4px 10px;
                     border-radius:4px; cursor:pointer; font-size:12px; }
.filter-bar button.active { background:var(--accent); color:#000; }
#ecg-chart { width:100%; height:420px; }
.tp-item { border-left:3px solid var(--accent); padding:10px 12px; margin-bottom:10px;
           background:#222a33; border-radius:4px; cursor:pointer; }
.tp-item h3 { margin:0 0 6px; font-size:14px; }
.tp-item .evidence { margin-top:8px; font-size:12px; color:var(--muted); }
.tp-item .evidence li { margin:2px 0; list-style: none; }
.tp-item .evidence li::before { content:"• "; color:var(--accent); }
.tp-item.collapsed .evidence, .tp-item.collapsed .tp-link { display:none; }
.tp-link { display:inline-block; margin-top:8px; color:var(--accent); font-size:12px;
           text-decoration:none; }
@media print {
  .filter-bar, #zoom-controls { display:none; }
  body { background:#fff; color:#000; }
  .panel { background:#fff; border-color:#ccc; }
}
</style>
</head>
<body>
<div class="container">
<header>
  <h1>🫀 emoekg · 情绪心电图</h1>
  <div class="meta">
    《{{ meta.title }}》· UP: {{ meta.up }} · 时长 {{ duration_hms }} ·
    {{ total_danmaku }} 条弹幕 · {{ meta.bvid }}
    <a href="https://www.bilibili.com/video/{{ meta.bvid }}" target="_blank">🔗 跳转 B 站</a>
  </div>
  <div class="meta" style="margin-top:4px">生成于 {{ meta.fetched_at }}</div>
</header>

<section class="panel">
  <h2>§ 全局速览</h2>
  <div id="overview"></div>
</section>

<div class="layout">
  <section class="panel">
    <h2>§ 视频</h2>
    <div id="video-wrapper"></div>
  </section>
  <section class="panel">
    <h2>§ 情绪心电图</h2>
    <div id="ecg-chart"></div>
  </section>
</div>

<div class="layout">
  <section class="panel">
    <h2>§ 弹幕流（{{ total_danmaku }} 条）</h2>
    <input id="dm-search" placeholder="🔍 搜索弹幕..." style="width:100%;padding:6px;margin-bottom:8px;
           background:#2a3340;border:0;color:var(--fg);border-radius:4px" />
    <div class="filter-bar" id="dm-filter"></div>
    <div id="danmaku-list"></div>
  </section>
  <section class="panel">
    <h2>§ 情绪转折点</h2>
    <div id="turnpoints"></div>
  </section>
</div>

<section class="panel">
  <h2>§ 附录</h2>
  <div id="legend"></div>
  <p style="color:var(--muted);font-size:12px">
    切片粒度 {{ window_size }}s · 转折点算法：峰值检测 + 滑动窗口 JS 散度对比 ·
    共 {{ chunks_count }} 个 chunk，{{ turnpoints_count }} 个转折点
  </p>
</section>
</div>

<!-- Data embeds -->
<script type="application/json" id="data-meta">{{ meta_json | safe }}</script>
<script type="application/json" id="data-scores">{{ scores_json | safe }}</script>
<script type="application/json" id="data-turnpoints">{{ turnpoints_json | safe }}</script>
<script type="application/json" id="data-danmakus">{{ danmakus_json | safe }}</script>
<script type="application/json" id="data-config">{{ config_json | safe }}</script>

<!-- ECharts inline -->
<script>{{ echarts_js | safe }}</script>
<script>{{ app_js | safe }}</script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add templates/report.html.j2
git commit -m "feat(templates): report.html.j2 skeleton (layout + style + data slots)"
```

---

## Task 17：`app.js` 主逻辑 —— 视频嵌入 + 心电图 + 联动

**Files:**
- Create: `emoekg/templates/app.js`

- [ ] **Step 1: 创建前端 JS**

`templates/app.js`：
```javascript
(function(){
'use strict';

const $ = (id) => document.getElementById(id);
const META       = JSON.parse($('data-meta').textContent);
const SCORES     = JSON.parse($('data-scores').textContent);
const TURNPOINTS = JSON.parse($('data-turnpoints').textContent);
const DANMAKUS   = JSON.parse($('data-danmakus').textContent);
const CONFIG     = JSON.parse($('data-config').textContent);

// ---------- utilities ----------
const fmtHMS = (s) => {
  s = Math.floor(s);
  const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
};
const DIMS = ['joy','trust','fear','surprise','sadness','disgust','anger','anticipation'];
const DIM_LABEL = {joy:'喜悦',trust:'信任',fear:'恐惧',surprise:'惊讶',
                   sadness:'悲伤',disgust:'厌恶',anger:'愤怒',anticipation:'期待'};

// ---------- video player ----------
let videoApi = null;  // { seek: (sec) => void, currentTime: () => number|null }

function mountVideo() {
  const wrap = $('video-wrapper');
  if (CONFIG.video_mode === 'local' && CONFIG.video_path) {
    const el = document.createElement('video');
    el.src = CONFIG.video_path;
    el.controls = true;
    wrap.appendChild(el);
    videoApi = {
      seek: (s) => { el.currentTime = s; el.play(); },
      currentTime: () => el.currentTime,
      onTick: (cb) => el.addEventListener('timeupdate', () => cb(el.currentTime)),
    };
  } else {
    const iframe = document.createElement('iframe');
    iframe.allowFullscreen = true;
    iframe.id = 'bili-iframe';
    iframe.src = `//player.bilibili.com/player.html?bvid=${META.bvid}&autoplay=0&high_quality=1`;
    wrap.appendChild(iframe);
    videoApi = {
      seek: (s) => {
        iframe.src = `//player.bilibili.com/player.html?bvid=${META.bvid}&t=${Math.floor(s)}&autoplay=1&high_quality=1`;
      },
      currentTime: () => null,  // cross-origin: unavailable
      onTick: () => {},
    };
  }
}

// ---------- overview ----------
function renderOverview() {
  const sumByDim = Object.fromEntries(DIMS.map(d => [d, 0]));
  SCORES.forEach(s => DIMS.forEach(d => sumByDim[d] += s[d]));
  const topDim = DIMS.reduce((a,b) => sumByDim[a] > sumByDim[b] ? a : b);
  const hottest = SCORES.reduce((a, b) => {
    const maxA = Math.max(...DIMS.map(d => a[d]));
    const maxB = Math.max(...DIMS.map(d => b[d]));
    return maxB > maxA ? b : a;
  });
  const coldest = SCORES.filter(s => s.n_danmaku >= 3).reduce((a, b) => {
    const sumA = DIMS.reduce((x, d) => x + a[d], 0);
    const sumB = DIMS.reduce((x, d) => x + b[d], 0);
    return sumB < sumA ? b : a;
  }, SCORES[0]);
  $('overview').innerHTML = `
    <table style="width:100%"><tr>
      <td><b>🔥 最炸</b><br>${fmtHMS(hottest.time_start)} · ${DIM_LABEL[
        DIMS.reduce((a,b) => hottest[a]>hottest[b]?a:b)]}=${
          Math.max(...DIMS.map(d => hottest[d]))}</td>
      <td><b>🧊 最冷</b><br>${fmtHMS(coldest.time_start)} · 全维平均
        ${(DIMS.reduce((x,d)=>x+coldest[d],0)/8).toFixed(1)}</td>
      <td><b>📊 整体</b><br>${DIM_LABEL[topDim]} 主导</td>
    </tr></table>`;
}

// ---------- ECG chart ----------
let chart = null;
function renderChart() {
  chart = echarts.init($('ecg-chart'), 'dark');
  const colors = CONFIG.colors;
  const series = DIMS.map(d => ({
    name: DIM_LABEL[d], type: 'line', data: SCORES.map(s => [s.time_start, s[d]]),
    smooth: true, lineStyle: {color: colors[d], width: 1.5},
    itemStyle: {color: colors[d]}, symbol: 'none', emphasis: {focus: 'series'},
  }));
  const markPoints = TURNPOINTS.map(tp => ({
    name: tp.turnpoint_id, xAxis: tp.time_start,
    yAxis: tp.type === 'valley' ? 1 : 9,
    itemStyle: {color: colors[tp.main_dimension]},
    symbol: tp.direction === 'up' ? 'triangle' : 'pin',
    symbolSize: 14, label: {show: false},
  }));
  series[0].markPoint = {data: markPoints};
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {trigger: 'axis', formatter: (params) => {
      const t = params[0].value[0];
      const chunk = SCORES.find(s => s.time_start === t);
      if (!chunk) return '';
      let html = `<b>${fmtHMS(t)}</b> · n=${chunk.n_danmaku}<br/>`;
      DIMS.forEach(d => {
        const v = chunk[d];
        if (v > 0) html += `<span style="color:${colors[d]}">●</span> ${DIM_LABEL[d]}: ${v}<br/>`;
      });
      return html;
    }},
    legend: {data: DIMS.map(d => DIM_LABEL[d]), top: 0, textStyle: {color: '#ccc'}},
    grid: {left: 40, right: 20, top: 40, bottom: 50},
    xAxis: {type: 'value', axisLabel: {formatter: fmtHMS, color: '#8a94a6'},
            splitLine: {show: false}},
    yAxis: {type: 'value', min: 0, max: 10, axisLabel: {color: '#8a94a6'},
            splitLine: {lineStyle: {color: '#2a3340'}}},
    dataZoom: [{type: 'slider', height: 18}, {type: 'inside'}],
    series: series,
  });
  chart.on('click', (params) => {
    if (params.componentType === 'markPoint') {
      const tp = TURNPOINTS.find(t => t.turnpoint_id === params.name);
      if (tp) { scrollToTP(tp.turnpoint_id); seekAll(tp.time_start); return; }
    }
    seekAll(params.value[0]);
  });
}

// ---------- unified seek ----------
function seekAll(sec) {
  if (videoApi) videoApi.seek(sec);
  highlightDanmakuAt(sec);
}

// ---------- danmaku list ----------
let activeFilter = 'all';
let searchTerm = '';

function chunkDomOf(t) {
  return SCORES.find(s => t >= s.time_start && t < s.time_end);
}
function dominantDim(chunk) {
  return DIMS.reduce((a,b) => chunk[a] > chunk[b] ? a : b);
}

function renderDanmakuList() {
  const list = $('danmaku-list');
  const colors = CONFIG.colors;
  const html = DANMAKUS.map((d, i) => {
    const chunk = chunkDomOf(d.time);
    const dim = chunk ? dominantDim(chunk) : 'joy';
    return `<div class="item" data-idx="${i}" data-time="${d.time}" data-dim="${dim}">
      <span class="time">${fmtHMS(d.time)}</span>${escapeHtml(d.text)}
      <span class="dot" style="background:${colors[dim]}"></span>
    </div>`;
  }).join('');
  list.innerHTML = html;
  list.addEventListener('click', (e) => {
    const item = e.target.closest('.item');
    if (item) seekAll(parseFloat(item.dataset.time));
  });
  // filter bar
  const bar = $('dm-filter');
  const btn = (k, label, color) =>
    `<button data-k="${k}" ${k==='all'?'class="active"':''}
      ${color?`style="border-left:3px solid ${color}"`:''}>${label}</button>`;
  bar.innerHTML = btn('all', '全部') +
    DIMS.map(d => btn(d, DIM_LABEL[d], colors[d])).join('');
  bar.addEventListener('click', (e) => {
    if (e.target.tagName !== 'BUTTON') return;
    bar.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    activeFilter = e.target.dataset.k;
    applyDmFilter();
  });
  $('dm-search').addEventListener('input', (e) => {
    searchTerm = e.target.value.trim().toLowerCase();
    applyDmFilter();
  });
}

function applyDmFilter() {
  document.querySelectorAll('#danmaku-list .item').forEach(el => {
    const okDim = activeFilter === 'all' || el.dataset.dim === activeFilter;
    const okText = !searchTerm || el.textContent.toLowerCase().includes(searchTerm);
    el.style.display = (okDim && okText) ? '' : 'none';
  });
}

function highlightDanmakuAt(sec) {
  document.querySelectorAll('#danmaku-list .item.active').forEach(el => el.classList.remove('active'));
  const items = document.querySelectorAll('#danmaku-list .item');
  let target = null;
  for (const el of items) {
    if (parseFloat(el.dataset.time) >= sec) { target = el; break; }
  }
  if (target) {
    target.classList.add('active');
    target.scrollIntoView({block: 'center', behavior: 'smooth'});
  }
}

// ---------- turnpoints ----------
function renderTurnpoints() {
  const colors = CONFIG.colors;
  $('turnpoints').innerHTML = TURNPOINTS.map((tp, i) => `
    <div class="tp-item ${i>=3?'collapsed':''}" id="tp-${tp.turnpoint_id}"
         style="border-left-color:${colors[tp.main_dimension]}">
      <h3>▸ #${i+1}  ${fmtHMS(tp.time_start)}  ${escapeHtml(tp.description)}</h3>
      <ul class="evidence">
        ${tp.evidence_danmakus.map(ed =>
          `<li>[${fmtHMS(ed.time)}] ${escapeHtml(ed.text)}</li>`
        ).join('')}
      </ul>
      <a class="tp-link" href="#" data-time="${tp.time_start}">🔗 跳到 ${fmtHMS(tp.time_start)}</a>
    </div>
  `).join('');
  $('turnpoints').addEventListener('click', (e) => {
    const link = e.target.closest('.tp-link');
    if (link) { e.preventDefault(); seekAll(parseFloat(link.dataset.time)); return; }
    const item = e.target.closest('.tp-item');
    if (item) item.classList.toggle('collapsed');
  });
}

function scrollToTP(id) {
  const el = $(`tp-${id}`);
  if (el) { el.classList.remove('collapsed'); el.scrollIntoView({behavior: 'smooth'}); }
}

// ---------- legend ----------
function renderLegend() {
  const colors = CONFIG.colors;
  $('legend').innerHTML = DIMS.map(d =>
    `<span style="display:inline-block;margin-right:14px">
      <span class="dot" style="background:${colors[d]};width:10px;height:10px;
            border-radius:50%;display:inline-block;vertical-align:middle"></span>
      ${DIM_LABEL[d]} (${d})
    </span>`
  ).join('');
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
}

// ---------- bootstrap ----------
mountVideo();
renderOverview();
renderChart();
renderDanmakuList();
renderTurnpoints();
renderLegend();

// bidirectional sync (local video mode only)
if (videoApi.onTick) {
  videoApi.onTick((t) => {
    highlightDanmakuAt(t);
    if (chart && !window._cursorBusy) {
      window._cursorBusy = true;
      chart.setOption({
        series: [{markLine: {silent: true, symbol: 'none',
          lineStyle: {color: '#fff', width: 1}, data: [{xAxis: t}]}}]
      });
      setTimeout(() => window._cursorBusy = false, 100);
    }
  });
}

window.addEventListener('resize', () => chart && chart.resize());

})();
```

- [ ] **Step 2: Commit**

```bash
git add templates/app.js
git commit -m "feat(templates): app.js (ECG chart, video mount, bidirectional sync, filters)"
```

---

## Task 18：`render_report.py` —— Stage 5 整合

**Files:**
- Create: `emoekg/scripts/render_report.py`
- Create: `emoekg/tests/test_stage5_render.py`

- [ ] **Step 1: 写失败测试**

`tests/test_stage5_render.py`：
```python
import json
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import render_report  # noqa: E402


def _populate(wd: Path):
    (wd / "meta.json").write_text(json.dumps({
        "bvid": "BVTEST", "title": "T", "up": "U", "duration_sec": 60,
        "view_count": 0, "cid": 1, "fetched_at": "2026-05-07T00:00:00",
    }), encoding="utf-8")
    (wd / "danmaku.json").write_text(json.dumps([
        {"time": 1.0, "text": "666", "mode": 1, "color": 16777215, "fontsize": 25, "user_hash": "h"}
    ]), encoding="utf-8")
    (wd / "scores.json").write_text(json.dumps([
        {"chunk_id":"C001","time_start":0,"time_end":60,"n_danmaku":1,
         "joy":5,"trust":0,"fear":0,"surprise":0,"sadness":0,"disgust":0,
         "anger":0,"anticipation":0,"note":"x"}
    ]), encoding="utf-8")
    (wd / "turnpoints.json").write_text(json.dumps([]), encoding="utf-8")


def test_stage5_produces_single_html(tmp_working_dir):
    _populate(tmp_working_dir)
    render_report.run(tmp_working_dir, with_video=False, force=False)
    html_path = tmp_working_dir / "emoekg_report.html"
    assert html_path.exists()
    html = html_path.read_text(encoding="utf-8")
    assert "emoekg · 情绪心电图" in html
    assert "BVTEST" in html
    # ECharts inlined
    assert "echarts" in html.lower()
    # JSON data embedded
    assert '"bvid"' in html
    assert len(html) > 100_000  # ECharts alone is ~900KB


def test_stage5_with_video_mode(tmp_working_dir):
    _populate(tmp_working_dir)
    (tmp_working_dir / "video.mp4").write_bytes(b"fake")
    render_report.run(tmp_working_dir, with_video=True, force=False)
    html = (tmp_working_dir / "emoekg_report.html").read_text(encoding="utf-8")
    assert '"video_mode": "local"' in html or "'video_mode': 'local'" in html or '"local"' in html
```

- [ ] **Step 2: 运行，确认失败**

- [ ] **Step 3: 实现**

`scripts/render_report.py`：
```python
"""Stage 5: render the final single-file HTML report."""
import argparse
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from emoekg._lib.plutchik import COLORS
from emoekg._lib.time_utils import format_hms
from emoekg._lib.adaptive_window import compute_window_size


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "templates"


def run(working_dir: Path, with_video: bool = False, force: bool = False) -> None:
    working_dir = Path(working_dir)
    html_path = working_dir / "emoekg_report.html"
    if not force and html_path.exists():
        print("[SKIP] Stage 5: emoekg_report.html already exists")
        return

    meta = json.loads((working_dir / "meta.json").read_text(encoding="utf-8"))
    scores = json.loads((working_dir / "scores.json").read_text(encoding="utf-8"))
    tps = json.loads((working_dir / "turnpoints.json").read_text(encoding="utf-8"))
    dms = json.loads((working_dir / "danmaku.json").read_text(encoding="utf-8"))

    echarts_js = (TEMPLATE_DIR / "vendor" / "echarts.min.js").read_text(encoding="utf-8")
    app_js = (TEMPLATE_DIR / "app.js").read_text(encoding="utf-8")

    config = {
        "colors": COLORS,
        "video_mode": "local" if with_video else "iframe",
        "video_path": "./video.mp4" if with_video else None,
    }

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(['html']),
    )
    tpl = env.get_template("report.html.j2")
    html = tpl.render(
        meta=meta,
        duration_hms=format_hms(meta["duration_sec"]),
        window_size=compute_window_size(meta["duration_sec"]),
        total_danmaku=len(dms),
        chunks_count=len(scores),
        turnpoints_count=len(tps),
        meta_json=json.dumps(meta, ensure_ascii=False),
        scores_json=json.dumps(scores, ensure_ascii=False),
        turnpoints_json=json.dumps(tps, ensure_ascii=False),
        danmakus_json=json.dumps(dms, ensure_ascii=False),
        config_json=json.dumps(config, ensure_ascii=False),
        echarts_js=echarts_js,
        app_js=app_js,
    )
    html_path.write_text(html, encoding="utf-8")
    print(f"[Stage 5] Done. Report: {html_path} ({len(html) // 1024} KB)")


def main():
    ap = argparse.ArgumentParser(description="emoekg Stage 5: render HTML report")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--with-video", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    run(Path(args.output), with_video=args.with_video, force=args.force)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行，确认通过**

```bash
pytest tests/test_stage5_render.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/render_report.py tests/test_stage5_render.py
git commit -m "feat(stage5): render_report.py (single-file HTML with inlined ECharts)"
```

---

# Phase 7：CLI 整合

## Task 19：`emoekg/cli.py` —— 串起 5 个 Stage

**Files:**
- Create: `emoekg/emoekg/cli.py`
- Create: `emoekg/emoekg/__main__.py`
- Create: `emoekg/tests/test_cli.py`

- [ ] **Step 1: 写失败测试**

`tests/test_cli.py`：
```python
import sys
from pathlib import Path
from unittest.mock import patch
from emoekg.cli import compute_working_dir, build_arg_parser


def test_arg_parser_defaults():
    ap = build_arg_parser()
    args = ap.parse_args(["https://www.bilibili.com/video/BV18acMz4ELL"])
    assert args.url == "https://www.bilibili.com/video/BV18acMz4ELL"
    assert args.force is False
    assert args.with_video is False
    assert args.from_stage == 1


def test_arg_parser_options():
    ap = build_arg_parser()
    args = ap.parse_args(["BVxxx", "--force", "--with-video", "--from-stage", "3"])
    assert args.force is True
    assert args.with_video is True
    assert args.from_stage == 3


def test_compute_working_dir_uses_bvid_and_date(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    wd = compute_working_dir("BV18acMz4ELL", base=None)
    assert "BV18acMz4ELL" in str(wd)
    assert "emoekg_" in str(wd.name)
```

- [ ] **Step 2: 运行，确认失败**

- [ ] **Step 3: 实现**

`emoekg/cli.py`：
```python
"""emoekg command-line entry: orchestrate Stages 1/2/4/5 and pause for Agent Stage 3."""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from emoekg._lib.bv_parser import extract_bvid

# import scripts as modules (they're in a sibling "scripts/" dir one level up)
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="emoekg",
        description="Bilibili danmaku emotion ECG · UX research tool",
    )
    ap.add_argument("url", help="B站视频 URL 或 BV id")
    ap.add_argument("-o", "--output", default=None,
                    help="工作目录（默认 ~/Desktop/emoekg_{BV}_{YYYYMMDD}/）")
    ap.add_argument("--force", action="store_true", help="忽略缓存重新跑每个 Stage")
    ap.add_argument("--from-stage", type=int, default=1, choices=[1, 2, 3, 4, 5],
                    help="从指定 Stage 开始跑（默认 1）")
    ap.add_argument("--with-video", action="store_true",
                    help="额外下载视频并启用完整双向联动")
    return ap


def compute_working_dir(bvid: str, base: Path | None) -> Path:
    if base is not None:
        return Path(base)
    home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or ".")
    desktop = home / "Desktop"
    desktop.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    return desktop / f"emoekg_{bvid}_{today}"


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    bvid = extract_bvid(args.url)
    wd = compute_working_dir(bvid, Path(args.output) if args.output else None)
    print(f"[emoekg] BV id: {bvid}")
    print(f"[emoekg] Working dir: {wd}")
    wd.mkdir(parents=True, exist_ok=True)

    import fetch_danmaku, slice_chunks, detect_turnpoints, render_report  # noqa: E402

    if args.from_stage <= 1:
        fetch_danmaku.run(args.url, wd, force=args.force)
    if args.from_stage <= 2:
        slice_chunks.run(wd, force=args.force)

    scores_file = wd / "scores.json"
    scores = json.loads(scores_file.read_text(encoding="utf-8")) if scores_file.exists() else []
    expected = len((wd / "chunks.md").read_text(encoding="utf-8").split("## ["))-1 \
        if (wd / "chunks.md").exists() else 0

    if len(scores) < expected and args.from_stage <= 3:
        print("\n" + "=" * 70)
        print(f"[Stage 3] Agent 打分未完成 ({len(scores)}/{expected} chunks)")
        print(f"请阅读 {wd / 'chunks.md'} 并按 SKILL.md 中的 rubric 批量打分，")
        print(f"将结果写入 {scores_file}")
        print("打分完成后重跑本命令即可从 Stage 4 继续。")
        print("=" * 70)
        return 10  # 10 = awaiting agent

    if args.from_stage <= 4:
        detect_turnpoints.run(wd, force=args.force)
    if args.from_stage <= 5:
        if args.with_video:
            import download_video
            download_video.run(args.url, wd, force=args.force)
        render_report.run(wd, with_video=args.with_video, force=args.force)

    print(f"\n[emoekg] ✅ 报告已生成：{wd / 'emoekg_report.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`emoekg/__main__.py`：
```python
"""Allow `python -m emoekg ...`."""
from emoekg.cli import main
import sys
sys.exit(main())
```

- [ ] **Step 4: 运行，确认通过**

```bash
pytest tests/test_cli.py -v
```

Expected: 3 passed

- [ ] **Step 5: 手动冒烟测试**

```bash
python -m emoekg --help
```

Expected: 打印 help，不报错

- [ ] **Step 6: Commit**

```bash
git add emoekg/cli.py emoekg/__main__.py tests/test_cli.py
git commit -m "feat(cli): orchestrator with --force / --from-stage / --with-video"
```

---

# Phase 8：视频下载（可选依赖）

## Task 20：`scripts/download_video.py` —— yutto 封装

**Files:**
- Create: `emoekg/scripts/download_video.py`

- [ ] **Step 1: 实现（因依赖外部二进制，不写单元测试）**

`scripts/download_video.py`：
```python
"""Optional Stage: download source video via yutto for --with-video mode."""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from emoekg._lib.bv_parser import extract_bvid


def run(url_or_bvid: str, working_dir: Path, force: bool = False) -> None:
    working_dir = Path(working_dir)
    video_path = working_dir / "video.mp4"
    if not force and video_path.exists():
        print(f"[SKIP] video.mp4 already exists")
        return

    try:
        subprocess.run(["yutto", "--version"], check=True,
                       capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("[ERROR] yutto not installed. Run: pip install yutto", file=sys.stderr)
        sys.exit(3)

    bvid = extract_bvid(url_or_bvid)
    print(f"[Video] Downloading {bvid} via yutto...")
    # yutto output naming: <title>.mp4 in the given dir
    cmd = [
        "yutto", f"https://www.bilibili.com/video/{bvid}",
        "--dir", str(working_dir),
        "--tmp-dir", str(working_dir / ".yutto-tmp"),
        "--no-danmaku", "--no-subtitle",  # we already have danmaku.json
        "-q", "80",  # 1080p when available
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"[ERROR] yutto exited with {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)

    # find the downloaded mp4 and rename to video.mp4 for stable relative path
    mp4s = [p for p in working_dir.iterdir() if p.suffix == ".mp4" and p.name != "video.mp4"]
    if len(mp4s) == 1:
        mp4s[0].rename(video_path)
    elif len(mp4s) > 1:
        # pick the largest
        largest = max(mp4s, key=lambda p: p.stat().st_size)
        largest.rename(video_path)
        for p in mp4s:
            if p != video_path and p.exists():
                p.unlink()

    print(f"[Video] Done. {video_path}")


def main():
    ap = argparse.ArgumentParser(description="Download video via yutto")
    ap.add_argument("url")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    run(args.url, Path(args.output), force=args.force)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 冒烟测试（仅检查 --help 不崩）**

```bash
python scripts/download_video.py --help
```

Expected: 打印 usage

- [ ] **Step 3: Commit**

```bash
git add scripts/download_video.py
git commit -m "feat(video): download_video.py wrapper over yutto"
```

---

# Phase 9：文档 & 跑测示例

## Task 21：`templates/scoring_rubric.md` & `SKILL.md`

**Files:**
- Create: `emoekg/templates/scoring_rubric.md`
- Create: `emoekg/SKILL.md`

- [ ] **Step 1: 创建 scoring_rubric.md**

`templates/scoring_rubric.md`（内容直接从 spec §5 复制）：
```markdown
# Plutchik 8 维情绪评分 Rubric

## 维度与颜色
| 维度 | 英文 | 颜色 | B 站弹幕典型表达 |
|---|---|---|---|
| 喜悦 | joy | #F4D03F | 233 / 哈哈哈 / 笑死 / 好活 / 太乐了 |
| 信任 | trust | #52BE80 | 稳了 / 相信主播 / 专业 / yyds |
| 恐惧 | fear | #566573 | 害怕 / 瑟瑟发抖 / 完蛋了 / 要出事 |
| 惊讶 | surprise | #F39C12 | 卧槽 / 啊这 / ??? / 离谱 / 什么情况 |
| 悲伤 | sadness | #5499C7 | 破防 / 难过 / emo / 泪目 / 心疼 |
| 厌恶 | disgust | #8E44AD | 恶心 / 作呕 / 下头 / 恶臭 |
| 愤怒 | anger | #C0392B | 退游 / 策划死妈 / 气死 / 滚 / 辣鸡 |
| 期待 | anticipation | #EB984E | 我等你 / 快更新 / 下一集 / 蹲 / 求出 |

## 0–10 打分标尺（以 joy 为例）
- 0：完全不存在 —— 一条都没有
- 1-2：微弱背景 —— 偶尔一两个 "哈"
- 3-4：一定比例（20-40%）—— 夹杂 "233"、"乐"
- 5-6：明显主导（40-60%）—— "哈哈哈" 刷屏
- 7-8：强烈集中（60-80%）—— 几乎满屏笑点
- 9-10：极端爆发（>80%，短时高密度）—— 窗口被 "哈哈哈" 淹没

**8 个维度互不相斥**：一个窗口可以同时 joy=7 + surprise=6（"卧槽笑死了"）。

## 特殊 chunk
- 标注 SPARSE（n<3）：全维度打 0，note: "sparse"
- 否则即便弹幕少也要按语义打分
```

- [ ] **Step 2: 创建 SKILL.md（直接可用的完整版）**

`SKILL.md`：
```markdown
---
name: emoekg
description: |
  将 B 站视频弹幕数据转化为"情绪心电图"的 skill，服务于 UX 研究员、内容运营、
  游戏策划分析玩家观看视频时的情绪波动。

  核心能力：给定 B 站视频 URL → 自动拉全量弹幕 → Plutchik 8 维情绪打分
  （喜悦/信任/恐惧/惊讶/悲伤/厌恶/愤怒/期待）→ 识别情绪转折点（每个附 ≥5
  条原话佐证）→ 输出单文件 HTML 交互报告（ECharts 心电图 + 弹幕流 + 视频
  嵌入 + 双向联动）。支持 --with-video 下载本地视频实现完整双向联动。

  当用户要求分析 B 站视频弹幕情绪、找玩家情绪高峰/低谷、定位"退游评论爆发
  时刻"、找视频哪里最炸/最冷、做直播回放情绪复盘、分析观众实时反应、UX
  研究写报告时触发。

  即使用户没有明确说"情绪分析"，只要涉及"弹幕情绪"、"观众反应"、"视频哪段
  最炸"、"玩家情绪拐点"、"直播哪里冷场"、"弹幕心电图"、"B 站情绪曲线"
  等场景也应触发。

  典型触发表达：
  "分析一下这个 B 站视频的弹幕情绪"、
  "看看玩家的情绪心电图，链接是 xxx"、
  "这个直播回放哪里最炸"、
  "找一下退游评论爆发的那个时刻"、
  "帮我做一张弹幕情绪时间线"。

  不适用：抖音/YouTube（v0.3+）、私密/需登录视频、定量问卷分析（用 survey-research）。
---

# 弹幕情绪心电图（emoekg）

你是 UX 研究的分析助手。本 skill 把 B 站视频弹幕转成一张"情绪心电图"
HTML 报告，服务于 UX 研究员、内容运营、游戏策划。

## 脚本路径
所有脚本位于 `{SKILL_DIR}/scripts/`：
- `fetch_danmaku.py`    Stage 1
- `slice_chunks.py`     Stage 2
- `detect_turnpoints.py` Stage 4
- `render_report.py`     Stage 5
- `download_video.py`    视频下载（`--with-video`）

命令行入口：`python -m emoekg <B站URL> [--force] [--with-video]`

## 依赖
```bash
pip install -r requirements.txt
# --with-video 额外需要：
pip install yutto
```

## 工作流（5-Stage Pipeline）

1. **Stage 1（脚本）**：拉全量弹幕 → `meta.json` + `danmaku.json`
2. **Stage 2（脚本）**：切时间片 → `chunks.md` + 空 `scores.json` 骨架
3. **Stage 3（你）**：读 `chunks.md`，按下面的 Rubric 给每个 chunk 打
   8 维分，写入 `scores.json`
4. **Stage 4（脚本）**：识别情绪转折点 → `turnpoints.json`
5. **Stage 5（脚本）**：渲染 HTML → `emoekg_report.html`

CLI 会在 Stage 2 结束后暂停，等你完成 Stage 3 后再运行一次命令即可从 Stage 4 继续。

## Stage 3 打分协议（你需要严格遵守）

### 读取
从工作目录读取 `chunks.md`。每个 chunk 一个 section，形如：
```
## [C001] 00:00:00 – 00:00:15 (n=42)
- 00:00:02 开场
- 00:00:03 终于来了
...
```

### 打分
对每个 chunk：
- 按 Plutchik 8 维（joy/trust/fear/surprise/sadness/disgust/anger/anticipation）
  各打 0-10 整数分，维度互不相斥
- 给一句 `note` 说明你的主要判断依据
- 如果 chunk 标注 SPARSE（n<3），全维度打 0，note 写 "sparse"

参考 `templates/scoring_rubric.md` 的完整评分标尺。

### 输出
每 10 个 chunk 为一批，立即 append 到 `scores.json`（JSON array，每项：）：
```json
{
  "chunk_id": "C001", "time_start": 0, "time_end": 15, "n_danmaku": 42,
  "joy": 7, "trust": 2, "fear": 0, "surprise": 4,
  "sadness": 0, "disgust": 0, "anger": 0, "anticipation": 8,
  "note": "开场期待+欢乐情绪主导"
}
```

### 质量要求
- 所有 chunk 都要打分，不能漏
- 每维度值必须是 0-10 的整数
- 超过 20% 的非 SPARSE chunk 全打 0 会被脚本拒收并警告
- `note` 字段不能空

## 工作目录规则
默认 `~/Desktop/emoekg_{BV号}_{日期}/`。所有中间产物（meta/danmaku/chunks/
scores/turnpoints/report）都在同一目录，便于研究员查证。

## 幂等与断点续跑
- 默认重跑会跳过已完成的 Stage
- `--force` 强制重跑所有 Stage
- `--from-stage N` 从指定 Stage 开始

## 常见问题处理

| 错误 | 原因 | 处理 |
|---|---|---|
| "no BV id found" | URL 格式不对 | 确认用户给的是 B 站视频 URL |
| fetch_video_meta failed | 网络/视频下架 | 让用户换视频或检查视频是否公开 |
| scores.json has N entries, expected M | 你漏打了 chunk | 补齐后重跑 Stage 4 |
| "may have skipped scoring" 警告 | 全零 chunk 过多 | 检查你是否偷懒全打 0 |
```

- [ ] **Step 3: Commit**

```bash
git add templates/scoring_rubric.md SKILL.md
git commit -m "docs: add SKILL.md (Agent entry) and scoring_rubric.md"
```

---

## Task 22：`README.md`（用户文档）

**Files:**
- Create: `emoekg/README.md`

- [ ] **Step 1: 写 README**

`README.md`：
```markdown
# emoekg · 弹幕情绪心电图

> 把一晚上几万条弹幕的混沌声音，压缩成一张可读、可查、可对比的情绪心电图。

![demo](examples/screenshot.png)

## 这是什么

给一个 B 站视频链接，自动生成一张**情绪心电图 HTML 报告**：

- **Plutchik 8 维情绪**（喜悦/信任/恐惧/惊讶/悲伤/厌恶/愤怒/期待）分层折线图
- **情绪转折点**：哪里最炸、哪里最冷、哪里骤转，每个都附 ≥5 条原弹幕佐证
- **视频 + 弹幕流 + 心电图**三面板联动：点图表跳视频时间码、点弹幕跳视频
- `--with-video` 模式支持完整双向联动（下载视频后播放时弹幕列表/心电图游标跟随）

## 谁适合用

- **UX 研究员**：分析玩家观看视频时的情绪波动，写进研究报告
- **内容运营**：找视频哪段最炸/最冷，指导剪辑与封面
- **游戏策划**：定位"退游评论爆发时刻"、观众负反馈集中点
- **主播/直播回放分析**：3 小时直播哪段冷场、哪段破圈

## 演示

打开 `examples/BV18acMz4ELL_report.html` 直接查看。

## 安装

### 方式 1：作为 CodeMaker Skill 使用（推荐）

```bash
git clone https://github.com/lijinghui03/emoekg.git ~/.agents/skills/emoekg
cd ~/.agents/skills/emoekg
pip install -r requirements.txt
```

在 CodeMaker 对话里直接说："分析一下这个 B 站视频 https://..."，Agent 会自动触发本 skill。

### 方式 2：独立 CLI 使用

```bash
git clone https://github.com/lijinghui03/emoekg.git
cd emoekg
pip install -e .
emoekg https://www.bilibili.com/video/BV18acMz4ELL
```

⚠️ 独立 CLI 模式下，Stage 3 的情绪打分需要你自己用 LLM 完成（参考 `SKILL.md` 里的 rubric）。

## 工作流

```
B 站 URL
   ↓ Stage 1 (Python)   拉全量弹幕
   ↓ Stage 2 (Python)   自适应切片（60-120 chunks）
   ↓ Stage 3 (Agent)    Plutchik 8 维打分
   ↓ Stage 4 (Python)   峰值 + JS 散度识别转折点，选佐证弹幕
   ↓ Stage 5 (Python)   渲染单文件 HTML
emoekg_report.html
```

## 命令行参数

```bash
emoekg <URL> [选项]

  -o, --output DIR       工作目录（默认 ~/Desktop/emoekg_{BV}_{日期}/）
  --force                忽略缓存重跑
  --from-stage N         从 Stage N 开始（N=1..5）
  --with-video           下载视频 + 完整双向联动（需要 pip install yutto）
```

## 常见问题

**Q：拉弹幕报错 412？**
A：B 站近期调整了风控，稍等几分钟或换 IP 重试。

**Q：视频很长（3 小时+）打分很慢怎么办？**
A：自适应切片把长视频压到 ≤120 chunks，但 Agent 对话窗口仍可能吃紧。
可以 `--from-stage 3` 手动重试，或未来升级到批量 LLM API 模式。

**Q：`--with-video` 下载失败？**
A：B 站部分视频需要登录才能下高清。手动 `yutto` 测试下是否成功，参考 yutto 文档配置 cookie。

**Q：没有 CodeMaker 能用吗？**
A：能，但 Stage 3 需要你自己调 LLM 或手工打分。参考 `SKILL.md` 里的 rubric。

## Roadmap

- [x] v0.1.0 单视频分析（B 站）
- [ ] v0.2.0 直播实时模式 + 多视频对比
- [ ] v0.3.0 抖音 / YouTube 评论支持
- [ ] v0.4.0 情绪预测 / 玩家群体聚类

## 致谢

- [`bilibili-api-python`](https://github.com/Nemo2011/bilibili-api) — 弹幕抓取
- [`ECharts`](https://echarts.apache.org/) — 可视化
- [`yutto`](https://github.com/yutto-dev/yutto) — 视频下载
- Robert Plutchik — 情绪心理学理论

## License

MIT
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with installation / usage / FAQ"
```

---

## Task 23：跑测示例 —— `BV18acMz4ELL`

**Files:**
- Create: `emoekg/examples/BV18acMz4ELL_report.html`（跑测产出）
- Create: `emoekg/examples/screenshot.png`（手工截图）
- Create: `emoekg/examples/README.md`

**说明**：此 Task 需要**真实网络** + **CodeMaker Agent 真实打分**，不走 pytest。

- [ ] **Step 1: 跑 Stage 1-2**

```bash
python -m emoekg https://www.bilibili.com/video/BV18acMz4ELL/?share_source=copy_web -o ./_demo
# Expected: 退出码 10（awaiting agent），_demo/chunks.md 生成
```

- [ ] **Step 2: 让 Agent 完成 Stage 3 打分**

在 CodeMaker 对话里触发：
> 帮我打分 `_demo/chunks.md`，按 `templates/scoring_rubric.md` 的 rubric 填入 `_demo/scores.json`。

Agent 应按 10 个 chunk 一批完成。完成后检查：
```bash
python -c "import json; s=json.load(open('_demo/scores.json', encoding='utf-8')); print(len(s), 'chunks scored')"
```

- [ ] **Step 3: 跑 Stage 4-5**

```bash
python -m emoekg https://www.bilibili.com/video/BV18acMz4ELL -o ./_demo --from-stage 4
```

Expected: `_demo/emoekg_report.html` 生成

- [ ] **Step 4: 浏览器验收清单（逐条勾选）**

在 Chrome 打开 `_demo/emoekg_report.html`，手工确认：
- [ ] 页面顶部有标题、UP 主、BV、时长、弹幕总数
- [ ] 右上角「🔗 跳转 B 站」可用
- [ ] iframe 视频播放器能播
- [ ] ECharts 心电图 8 条线都显示，颜色和图例对应
- [ ] ⬇ 转折点标记出现在图上
- [ ] 点击心电图某点 → 视频跳到该时间
- [ ] hover 心电图 → tooltip 显示 8 维条形 + 采样弹幕
- [ ] 图例可点击开关某条线
- [ ] dataZoom 滑块可缩放
- [ ] 弹幕流列表全量显示、搜索框工作、情绪筛选按钮工作
- [ ] 点击弹幕条目 → 视频跳转
- [ ] 转折点列表至少 3 个，每个 ≥5 条佐证
- [ ] 转折点条目可折叠/展开
- [ ] 点击转折点「🔗 跳到 XX:XX」 → 视频跳转
- [ ] 附录显示 8 维图例与算法说明

- [ ] **Step 5: 把产出放到 examples/**

```bash
cp _demo/emoekg_report.html examples/BV18acMz4ELL_report.html
# 手工截一张主图为主的截图存为 examples/screenshot.png (1200x600 推荐)
```

- [ ] **Step 6: 写 examples/README.md**

`examples/README.md`：
```markdown
# Examples

## BV18acMz4ELL_report.html

这是用 `emoekg v0.1.0` 分析 B 站视频 `BV18acMz4ELL` 生成的真实报告。

**跑测时间**：2026-05-07
**视频弹幕数**：（跑完填）
**识别转折点数**：（跑完填）

直接用浏览器打开即可查看。
```

- [ ] **Step 7: Commit**

```bash
git add examples/
git commit -m "docs(examples): add BV18acMz4ELL demo report and screenshot"
```

---

## Task 24：更新 `CHANGELOG.md` 并打 tag v0.1.0

**Files:**
- Modify: `emoekg/CHANGELOG.md`

- [ ] **Step 1: 补充 CHANGELOG**

编辑 `CHANGELOG.md`，将 `[0.1.0] - 2026-05-07` 那段扩充为：
```markdown
## [0.1.0] - 2026-05-07
### Added
- 5-Stage pipeline: fetch → slice → agent scoring → turnpoint detection → render
- Plutchik 8-dimension emotion scoring protocol for CodeMaker Agent
- Adaptive time windowing (target 60–120 chunks per video)
- Turnpoint detection: scipy peak/valley + sliding-window JS divergence
- Evidence picker: keyword > length > dedup priority
- Interactive HTML report: ECharts 8-dim layered ECG, video+danmaku+chart 3-panel sync
- `--with-video` mode: yutto-based local video download + full bidirectional sync
- Idempotent runs with `--force` and `--from-stage` support
- Demo report: examples/BV18acMz4ELL_report.html
- SKILL.md (Agent entry) and comprehensive README
```

- [ ] **Step 2: 运行最终测试总览**

```bash
pytest -v
```

Expected: all green (~35+ tests passing)

- [ ] **Step 3: Commit + tag**

```bash
git add CHANGELOG.md
git commit -m "chore: release v0.1.0"
git tag v0.1.0
```

- [ ] **Step 4: 交接给 `github-ops` skill**

在 CodeMaker 里触发：
> 把 emoekg 仓库推送到 GitHub，创建 public repo，配好 Topics。

`github-ops` skill 负责创建远程仓库、推送 main 分支 + tag、配置仓库元信息（License, Topics）。

---

# Self-Review

**1. Spec coverage check:**

| Spec 章节 | 对应 Task |
|---|---|
| §1 产品定义 | Task 22 (README) |
| §2 D1 Agent 打分 | Task 21 (SKILL.md 打分协议) |
| §2 D2 弹幕抓取 | Task 7, 8 |
| §2 D3 HTML 单文件 | Task 15, 16, 17, 18 |
| §2 D4 双算法转折点 | Task 11, 12 |
| §2 D5 自适应切片 | Task 6, 10 |
| §2 D6 视频嵌入双模式 | Task 17 (app.js), 18, 20 |
| §3 Pipeline | Task 19 (CLI 编排) |
| §4 目录结构 | Task 1 |
| §5 Plutchik Rubric | Task 4 (代码), Task 21 (文档) |
| §6 Agent 打分协议 | Task 21 (SKILL.md) |
| §7 自适应窗口 | Task 6 |
| §8 转折点算法 | Task 11, 12, 13 |
| §9 HTML 报告 | Task 16, 17 |
| §10 仓库交付物 | Task 1, 21, 22 |
| §11.1 单元测试 | 分散在 Task 3-13 |
| §11.2 集成测试 | Task 23 |
| §12 Roadmap | Task 22 (README) |
| §14 成功标准 | Task 23 (验收清单) |

**无覆盖漏点**。

**2. Placeholder scan:** 无 TBD/TODO/"similar to"/无代码的步骤。

**3. Type consistency:**
- `DIMENSIONS` 列表在 `plutchik.py` 定义，被 `turnpoint_algo.py`、`evidence_picker.py`、`app.js` 一致使用 ✓
- score entry schema 在 Task 4 定义，Task 14 验证，Task 17 消费 ✓
- turnpoint schema（`turnpoint_id`/`chunk_index`/`type`/`main_dimension`/`direction`/`magnitude`/`description`）在 Task 11/12 定义，Task 14 增补 `evidence_danmakus`/`time_start`/`time_end`，Task 17 消费 ✓
- `compute_window_size` 签名在 Task 6 定义，Task 10、14 调用 ✓

**无类型不一致**。

---

# Execution Handoff

Plan 已完成，保存在 `emoekg/docs/2026-05-07-emoekg-plan.md`。**24 个 Task，分 10 个 Phase**：

| Phase | Tasks | 说明 |
|---|---|---|
| 0 初始化 | 1–2 | 仓库骨架、pytest 配置 |
| 1 底层工具 | 3–6 | time_utils / plutchik / bv_parser / adaptive_window |
| 2 弹幕抓取 | 7–8 | danmaku_client + Stage 1 |
| 3 切片 | 9–10 | chunks 模板 + Stage 2 |
| 4 算法 | 11–13 | 峰值/谷值 + JS 散度 + 佐证选取 |
| 5 Stage 4 整合 | 14 | detect_turnpoints 脚本 |
| 6 HTML 报告 | 15–18 | ECharts vendor + 模板 + app.js + Stage 5 |
| 7 CLI | 19 | 串起 5 个 Stage |
| 8 视频下载 | 20 | yutto 封装 |
| 9 文档 & 跑测 | 21–24 | SKILL / README / demo / CHANGELOG |

有两种执行方式：

1. **Subagent-Driven（推荐）** — 为每个 Task 派一个新 subagent，Task 间自动 review，速度快
2. **Inline Execution** — 在当前会话里按批执行，checkpoint 由你确认

哪种方式？

