# 单条弹幕语义标注 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 §04 弹幕列表里单条弹幕的圆点颜色与情绪筛选反映该弹幕自身语义，而非继承所在 chunk 的主导情绪。

**Architecture:** 新增产物 `danmaku_labels.json`（Agent 在 Stage 3 逐条标注，8 维或 neutral），Stage 2 写空骨架并在 `chunks.md` 给弹幕加全局 `[#idx]`，Stage 5 注入 HTML，`app.js` 改读单条 label 并支持 neutral 隐藏；全程带兜底回退旧逻辑。

**Tech Stack:** Python 3.14, Jinja2, pytest, 原生 JS（无框架）。

参考 spec：`docs/superpowers/specs/2026-06-15-per-danmaku-emotion-labeling-design.md`

---

### Task 1: Stage 2 写空骨架 `danmaku_labels.json` + chunks.md 加 `[#idx]`

**Files:**
- Modify: `src/emoekg/stages/slice_chunks.py`
- Modify: `src/emoekg/templates/chunks_prompt.md.j2`
- Test: `tests/test_stage2_slice.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_stage2_slice.py` 末尾追加（沿用文件已有的 fixtures 风格——若已有 `working_dir`/`tmp_path` 构造 helper，复用之；下面用最小自包含写法）：

```python
def test_stage2_writes_danmaku_labels_skeleton(tmp_path):
    import json
    from emoekg.stages import slice_chunks

    (tmp_path / "meta.json").write_text(json.dumps(
        {"bvid": "BV1x", "title": "t", "up": "u",
         "duration_sec": 20, "view_count": 0, "cid": 1, "pubdate": 0}
    ), encoding="utf-8")
    (tmp_path / "danmaku.json").write_text(json.dumps([
        {"time": 1.0, "text": "a", "mode": 1, "color": 0, "fontsize": 25, "user_hash": "h1"},
        {"time": 2.0, "text": "b", "mode": 1, "color": 0, "fontsize": 25, "user_hash": "h2"},
    ]), encoding="utf-8")

    slice_chunks.run(tmp_path)

    labels_path = tmp_path / "danmaku_labels.json"
    assert labels_path.exists()
    assert json.loads(labels_path.read_text(encoding="utf-8")) == []


def test_stage2_chunks_md_has_global_idx(tmp_path):
    import json
    from emoekg.stages import slice_chunks

    (tmp_path / "meta.json").write_text(json.dumps(
        {"bvid": "BV1x", "title": "t", "up": "u",
         "duration_sec": 20, "view_count": 0, "cid": 1, "pubdate": 0}
    ), encoding="utf-8")
    (tmp_path / "danmaku.json").write_text(json.dumps([
        {"time": 1.0, "text": "hello", "mode": 1, "color": 0, "fontsize": 25, "user_hash": "h1"},
    ]), encoding="utf-8")

    slice_chunks.run(tmp_path)

    md = (tmp_path / "chunks.md").read_text(encoding="utf-8")
    assert "[#0]" in md
    assert "hello" in md
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_stage2_slice.py::test_stage2_writes_danmaku_labels_skeleton tests/test_stage2_slice.py::test_stage2_chunks_md_has_global_idx -v`
Expected: FAIL —`danmaku_labels.json` 不存在；`chunks.md` 不含 `[#0]`。

- [ ] **Step 3: 给 display danmaku 附带全局 idx**

`slice_chunks.py` 中，`danmaku.json` 加载后的 `dms` 是全局列表。`slice_by_window` 产出的 chunk 内 danmaku 是 `dms` 元素的引用。为拿到全局 idx，先建 id→idx 映射（用 `id()` 不稳，改用枚举写回 danmaku 字典）。

在 `dms = json.loads(...)` 之后、`slice_by_window` 之前插入：

```python
    # Tag each danmaku with its global index so the prompt can show [#idx]
    # and the Agent's per-danmaku labels align back to danmaku.json order.
    for i, d in enumerate(dms):
        d["_idx"] = i
```

然后把 `chunk["display_danmakus"]` 的构造改为带 `idx`：

```python
        chunk["display_danmakus"] = [
            {"idx": d["_idx"], "time_hms": format_hms(d["time"]), "text": d["text"]}
            for d in sampled
        ]
```

- [ ] **Step 4: 模板渲染 `[#idx]`**

`src/emoekg/templates/chunks_prompt.md.j2` 把弹幕行改为：

```jinja
{% for dm in chunk.display_danmakus -%}
- [#{{ dm.idx }}] {{ dm.time_hms }} {{ dm.text }}
{% endfor %}
```

- [ ] **Step 5: 写空骨架 `danmaku_labels.json`**

`slice_chunks.py` 中，在写 `insights_json` 之后追加：

```python
    # Per-danmaku emotion labels skeleton. The Agent fills this in Stage 3 with
    # one {"idx", "dim"} per danmaku ("neutral" for no-emotion danmaku).
    # render_report is tolerant of the empty form and falls back to chunk-level
    # dominant emotion when this is empty.
    labels_json = working_dir / "danmaku_labels.json"
    labels_json.write_text("[]", encoding="utf-8")
```

> 注意 SKIP 条件：当前 `run()` 的 skip 判断检查 chunks.md/scores.json/insights.json 三者。**把 `labels_json.exists()` 也加入 skip 条件**，否则升级旧目录时不会补建。修改 skip 判断：

```python
    labels_json = working_dir / "danmaku_labels.json"
    if (
        not force
        and chunks_md.exists()
        and scores_json.exists()
        and insights_json.exists()
        and labels_json.exists()
    ):
```

（把 `labels_json` 变量定义上移到 skip 判断之前，写骨架处复用同一变量。）

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_stage2_slice.py -v`
Expected: PASS（含新增 2 个 + 原有全部）。

- [ ] **Step 7: 提交**

```bash
git add src/emoekg/stages/slice_chunks.py src/emoekg/templates/chunks_prompt.md.j2 tests/test_stage2_slice.py
git commit -m "feat(stage2): emit danmaku_labels.json skeleton + global idx in chunks.md"
```

---

### Task 2: Stage 5 注入 `data-danmaku-labels`

**Files:**
- Modify: `src/emoekg/stages/render_report.py:106-147`
- Modify: `src/emoekg/templates/report.html.j2:3325-3329`
- Test: `tests/test_stage5_render.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_stage5_render.py` 追加。复用文件已有的「最小 working dir」构造方式；若已有 helper（如 `_make_working_dir`）请复用，否则用下面自包含写法：

```python
def test_stage5_injects_danmaku_labels(tmp_path):
    import json
    from emoekg.stages import render_report

    (tmp_path / "meta.json").write_text(json.dumps(
        {"bvid": "BV1x", "title": "t", "up": "u",
         "duration_sec": 20, "view_count": 0, "cid": 1, "pubdate": 0}
    ), encoding="utf-8")
    (tmp_path / "scores.json").write_text(json.dumps([
        {"chunk_id": "C001", "time_start": 0, "time_end": 5, "n_danmaku": 1,
         "joy": 3, "trust": 0, "fear": 0, "surprise": 0, "sadness": 0,
         "disgust": 0, "anger": 0, "anticipation": 0, "note": "x"}
    ]), encoding="utf-8")
    (tmp_path / "turnpoints.json").write_text("[]", encoding="utf-8")
    (tmp_path / "danmaku.json").write_text(json.dumps([
        {"time": 1.0, "text": "a", "mode": 1, "color": 0, "fontsize": 25, "user_hash": "h1"},
    ]), encoding="utf-8")
    (tmp_path / "insights.json").write_text(json.dumps({"summary": "", "insights": []}), encoding="utf-8")
    (tmp_path / "danmaku_labels.json").write_text(json.dumps([
        {"idx": 0, "dim": "disgust"}
    ]), encoding="utf-8")

    render_report.run(tmp_path)

    html = (tmp_path / "emoekg_report.html").read_text(encoding="utf-8")
    assert 'id="data-danmaku-labels"' in html
    assert "disgust" in html


def test_stage5_renders_without_labels_file(tmp_path):
    """Backward compat: missing danmaku_labels.json must not break rendering."""
    import json
    from emoekg.stages import render_report

    (tmp_path / "meta.json").write_text(json.dumps(
        {"bvid": "BV1x", "title": "t", "up": "u",
         "duration_sec": 20, "view_count": 0, "cid": 1, "pubdate": 0}
    ), encoding="utf-8")
    (tmp_path / "scores.json").write_text(json.dumps([
        {"chunk_id": "C001", "time_start": 0, "time_end": 5, "n_danmaku": 1,
         "joy": 3, "trust": 0, "fear": 0, "surprise": 0, "sadness": 0,
         "disgust": 0, "anger": 0, "anticipation": 0, "note": "x"}
    ]), encoding="utf-8")
    (tmp_path / "turnpoints.json").write_text("[]", encoding="utf-8")
    (tmp_path / "danmaku.json").write_text(json.dumps([
        {"time": 1.0, "text": "a", "mode": 1, "color": 0, "fontsize": 25, "user_hash": "h1"},
    ]), encoding="utf-8")
    (tmp_path / "insights.json").write_text(json.dumps({"summary": "", "insights": []}), encoding="utf-8")
    # NOTE: deliberately no danmaku_labels.json

    render_report.run(tmp_path)

    html = (tmp_path / "emoekg_report.html").read_text(encoding="utf-8")
    # The script block still exists, holding an empty array.
    assert 'id="data-danmaku-labels"' in html
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_stage5_render.py::test_stage5_injects_danmaku_labels tests/test_stage5_render.py::test_stage5_renders_without_labels_file -v`
Expected: FAIL — HTML 不含 `id="data-danmaku-labels"`。

- [ ] **Step 3: render_report 读取 labels（带兜底）**

`render_report.py`，在 `insights = _load_insights(...)`（约 110 行）之后追加：

```python
    # Per-danmaku emotion labels (Stage 3 Agent output). Missing/!list → [].
    labels_path = working_dir / "danmaku_labels.json"
    try:
        danmaku_labels = json.loads(labels_path.read_text(encoding="utf-8"))
        if not isinstance(danmaku_labels, list):
            danmaku_labels = []
    except (FileNotFoundError, json.JSONDecodeError):
        danmaku_labels = []
```

在 `tpl.render(...)` 调用里（`danmakus_json=...` 那一行之后）加入：

```python
        danmaku_labels_json=json.dumps(danmaku_labels, ensure_ascii=False),
```

- [ ] **Step 4: 模板新增 script 块**

`src/emoekg/templates/report.html.j2`，在 `data-danmakus` script 之后（约 3328 行）加入：

```jinja
<script type="application/json" id="data-danmaku-labels">{{ danmaku_labels_json | safe }}</script>
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_stage5_render.py -v`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add src/emoekg/stages/render_report.py src/emoekg/templates/report.html.j2 tests/test_stage5_render.py
git commit -m "feat(stage5): inject data-danmaku-labels with empty-array fallback"
```

---

### Task 3: app.js 读单条 label + neutral 渲染/筛选

**Files:**
- Modify: `src/emoekg/templates/app.js:23`（常量区）
- Modify: `src/emoekg/templates/app.js:541-586`（renderDanmakuList / applyDmFilter）
- Modify: `src/emoekg/templates/report.html.j2`（neutral 圆点 + 筛选键 CSS/DOM，如需要）

> 本任务无 Python 单测（纯前端逻辑），用渲染产物字符串断言 + 手动验收兜住。改完后跑全量 pytest 确保未破坏 Stage5 测试。

- [ ] **Step 1: 新增 DANMAKU_LABELS 常量 + 查表**

`app.js` 约第 23 行 `const DANMAKUS = ...;` 之后追加：

```javascript
const DANMAKU_LABELS = (() => {
  const el = $('data-danmaku-labels');
  if (!el) return null;
  try {
    const arr = JSON.parse(el.textContent);
    if (!Array.isArray(arr) || arr.length === 0) return null;
    const map = new Map();
    for (const r of arr) map.set(r.idx, r.dim);
    return map;
  } catch { return null; }
})();
```

> `DANMAKU_LABELS === null` 即触发兜底（旧逻辑）。非空 Map 时启用单条标签。

- [ ] **Step 2: 改 renderDanmakuList 的 dim 选取**

`app.js` `renderDanmakuList()` 中（约 544-552 行）的 `DANMAKUS.map`，把：

```javascript
  const html = DANMAKUS.map((d, i) => {
    const chunk = chunkDomOf(d.time);
    const dim = chunk ? dominantDim(chunk) : 'joy';
    return `<div class="item" data-idx="${i}" data-time="${d.time}" data-dim="${dim}">
      <span class="time">${fmtHMS(d.time)}</span>
      <span class="text">${escapeHtml(d.text)}</span>
      <span class="dot" style="background:${colors[dim]}"></span>
    </div>`;
  }).join('');
```

替换为：

```javascript
  const html = DANMAKUS.map((d, i) => {
    let dim;
    if (DANMAKU_LABELS) {
      // Per-danmaku label. Unlabeled idx (e.g. dense-chunk down-sampling) =
      // neutral. neutral = grey dot, hidden under any emotion filter.
      dim = DANMAKU_LABELS.get(i) || 'neutral';
    } else {
      // Fallback: inherit the chunk's dominant emotion (legacy behaviour).
      const chunk = chunkDomOf(d.time);
      dim = chunk ? dominantDim(chunk) : 'joy';
    }
    const dotColor = dim === 'neutral' ? INK_MUTED : colors[dim];
    return `<div class="item" data-idx="${i}" data-time="${d.time}" data-dim="${dim}">
      <span class="time">${fmtHMS(d.time)}</span>
      <span class="text">${escapeHtml(d.text)}</span>
      <span class="dot" style="background:${dotColor}"></span>
    </div>`;
  }).join('');
```

> `INK_MUTED` 已在 app.js:42 定义（`--n-6` 灰），可直接用。

- [ ] **Step 3: 确认 applyDmFilter 对 neutral 的行为**

`applyDmFilter()`（约 580-586 行）现有逻辑：

```javascript
function applyDmFilter() {
  document.querySelectorAll('#danmaku-list .item').forEach(el => {
    const okDim = activeFilter === 'all' || el.dataset.dim === activeFilter;
    const okText = !searchTerm || el.textContent.toLowerCase().includes(searchTerm);
    el.style.display = (okDim && okText) ? '' : 'none';
  });
}
```

此逻辑**已满足需求**，无需改动：`activeFilter === 'all'` 时 neutral 显示；选任一情绪键时 `el.dataset.dim === activeFilter` 对 neutral 为 false → 隐藏。本步仅为确认，不改代码。

- [ ] **Step 4: 渲染产物自检 + 跑全量测试**

先临时造一个带 label 的 working dir 渲染验证（或直接用 Task 4 的重跑）。最少先确保 pytest 全绿：

Run: `python -m pytest -q`
Expected: PASS（194+ 新增）。

- [ ] **Step 5: 提交**

```bash
git add src/emoekg/templates/app.js
git commit -m "feat(report): per-danmaku emotion dot/filter with neutral + legacy fallback"
```

---

### Task 4: 更新 scoring_rubric.md（Agent 标注说明）

**Files:**
- Modify: `docs/scoring_rubric.md`
- Modify: `SKILL.md`（Stage 3 步骤补一句产出 danmaku_labels.json）

- [ ] **Step 1: rubric 新增 §7**

`docs/scoring_rubric.md` 末尾追加：

```markdown
---

## 7. 单条弹幕情绪标注（danmaku_labels.json）

除 chunk 级 8 维打分外，Stage 3 还要为**每一条弹幕**单独标一个主导情绪，
写回 `danmaku_labels.json`。这驱动 §04 弹幕列表的圆点颜色与情绪筛选。

### 7.1 产出格式

```json
[
  {"idx": 0, "dim": "anticipation"},
  {"idx": 1, "dim": "neutral"},
  {"idx": 2, "dim": "disgust"}
]
```

- `idx`：`chunks.md` 里每条弹幕行首的 `[#idx]`，对齐 danmaku.json 全局下标
- `dim`：8 维之一，或 `"neutral"`（无情绪/噪声）

### 7.2 neutral 判据

以下归 `neutral`，不要硬塞情绪：
- 纯标点 / 无意义：`?`、`。`、`！`
- 时间戳/计数：`0分钟前`、`一分钟前`、`第一个看完的`
- 客观陈述/考据（无情绪色彩）：`背景音乐是她的变调`、`人声鼎沸`
- 无法判断主导情绪的中性弹幕

### 7.3 与 chunk 分的关系

单条标注**独立判断**，不要照搬所在 chunk 的主导情绪。
一个以「期待」为主的 chunk 里完全可以有 `disgust`、`neutral` 的弹幕。

### 7.4 dense chunk

被下采样（chunks.md 未展示）的弹幕标不到 → 默认 neutral，列表仍显示但不带情绪色。
```

- [ ] **Step 2: SKILL.md 补充**

`SKILL.md` 的「Step 3 — Agent 打分 + 写洞察」列表中，`write scores.json` 之后加一条：

```markdown
6. **`write` 工具**把逐条弹幕标签写回 `<working_dir>/danmaku_labels.json`
   - 数组每项 `{idx, dim}`，`idx` 对齐 chunks.md 的 `[#idx]`
   - `dim` ∈ 8 维或 `"neutral"`（无情绪），判据见 rubric §7
```

（其后的「写 insights.json」等步骤序号顺延，可不强制重排号，保持可读即可。）

- [ ] **Step 3: 提交**

```bash
git add docs/scoring_rubric.md SKILL.md
git commit -m "docs: rubric §7 + SKILL step for per-danmaku labeling"
```

---

### Task 5: 端到端验收（重跑两个第五人格视频）

**Files:** 无代码改动，仅验证 + 重新打分。

- [ ] **Step 1: 重新安装确保改动生效**

Run: `pip install -e "C:\Users\lijinghui03\.agents\skills\emoekg"`
Expected: Successfully installed emoekg。

- [ ] **Step 2: 重跑 prepare（带 SESSDATA，复用桌面目录）**

```bat
set "BILI_SESSDATA=<用户提供的值>"
emoekg prepare BV1oSRkBnE33 -o "%USERPROFILE%\Desktop\AI情绪心电图-第五人格加页手记预告" --force
emoekg prepare BV171G466Eeh -o "%USERPROFILE%\Desktop\AI情绪心电图-加页手记游戏内首发" --force
```

Expected: chunks.md 弹幕行含 `[#idx]`；目录下出现空 `danmaku_labels.json`。

- [ ] **Step 3: Agent 打分 + 逐条标注**

Agent 读两个 chunks.md，分别写回：`scores.json`、`insights.json`、`danmaku_labels.json`。
重点验证标注：「吵死了」→ disgust，「本来还点赞了…取消」→ disgust/anger，「?」「0分钟前」「人声鼎沸」→ neutral。

- [ ] **Step 4: finalize + 友好命名副本**

```bat
emoekg finalize -o "%USERPROFILE%\Desktop\AI情绪心电图-第五人格加页手记预告" --force
emoekg finalize -o "%USERPROFILE%\Desktop\AI情绪心电图-加页手记游戏内首发" --force
copy /Y "...\emoekg_report.html" "...\AI情绪心电图-<关键字>.html"
```

- [ ] **Step 5: 浏览器验收**

打开报告 → §04 弹幕列表：
- ALL 显示全量（计数不变）
- 点「期待」→「吵死了」「?」等不再出现
- neutral 弹幕圆点为灰色，点任一情绪键时被隐藏

---

## Self-Review

**Spec coverage:**
- 数据模型 `danmaku_labels.json` → Task 1（骨架）+ Task 3（消费）✅
- Agent 逐条标注 → Task 4（rubric/SKILL）+ Task 5 step3（执行）✅
- chunks.md `[#idx]` → Task 1 ✅
- render 注入 + 兜底 → Task 2 ✅
- app.js 单条 label + neutral + ALL 全量 + 筛选隐藏 + 回退 → Task 3 ✅
- 计数保持全量 → 未改 `total_danmaku`，天然满足 ✅
- 测试（stage2/stage5/手动验收）→ Task 1/2/5 ✅

**Placeholder scan:** 仅 Task 5 的 SESSDATA 值与友好命名为运行期变量，已用 `<...>` 显式标注，非代码占位。其余均为完整代码。✅

**Type consistency:** `danmaku_labels.json` 全程 `[{idx, dim}]`；JS 端 `DANMAKU_LABELS` 为 `Map<idx,dim>` 或 `null`；模板变量 `danmaku_labels_json`；script id `data-danmaku-labels`——三层命名一致。✅
