# 单条弹幕语义标注 — 修复弹幕列表情绪误分类

date: 2026-06-15
status: approved
context: 用户发现 §04「转折与原声」弹幕列表里，单条弹幕的情绪分类明显错误——「吵死了」被归为期待、「本来还点赞了看到网易就取消了」被归为期待、「?」「人声鼎沸」「0分钟前」等噪声弹幕也被强行归入某情绪类。

## 问题根因

`app.js` 的 `renderDanmakuList()`（约 544-546 行）渲染弹幕列表时，每条弹幕的情绪标签不是对弹幕本身做语义识别，而是直接继承所在 5 秒 chunk 的「主导情绪」：

```js
const chunk = chunkDomOf(d.time);                 // 找弹幕所属 chunk
const dim = chunk ? dominantDim(chunk) : 'joy';   // 套用 chunk 主导情绪
```

整条 emoekg 流水线只在 **chunk 级**打 8 维分，**单条弹幕从未被单独分类**。弹幕列表的颜色圆点与情绪筛选器假装是「按弹幕情绪」分类，实则是「按 chunk 主导情绪」分类——这是误分类的全部来源。

附带问题：大量纯噪声弹幕（`?`、`0分钟前`、`人声鼎沸`、`一分钟前`）本身没有情绪，却被迫归入某个情绪维度。

## 目标与范围

**目标**：让弹幕列表里单条弹幕的圆点颜色 + 情绪筛选反映**该弹幕自身**的语义。

**范围内**：
- 单条弹幕的展示分类（圆点颜色 + 情绪筛选键行为）
- 无情绪弹幕的中性处理

**范围外（明确不动）**：
- chunk 级 8 维打分逻辑
- 情绪曲线（ECG chart）、转折点检测（Stage 4）、洞察（insights）
- §02 监护仪面板的 ±20s 邻近弹幕 trail

## 设计

### 数据模型

新增工作目录产物 `danmaku_labels.json`：

```json
[
  {"idx": 0, "dim": "anticipation"},
  {"idx": 1, "dim": "neutral"},
  {"idx": 2, "dim": "disgust"}
]
```

- `idx`：对齐 `danmaku.json` 的数组下标（0-based），与 `app.js` 里 `DANMAKUS` 的 index 一致
- `dim`：8 维之一（`joy/trust/fear/surprise/sadness/disgust/anger/anticipation`）或 `"neutral"`（无情绪/噪声）
- 数组长度 == `danmaku.json` 长度，顺序严格对齐

### 标注者：Agent（Stage 3）

逐条标注由 Agent 在 Stage 3 完成（与现有 chunk 级打分同属 Agent 职责），产出**完整映射**——每条弹幕都给一个 `dim` 或 `neutral`。

为支持逐条标注，`chunks.md` 需为每条弹幕展示其全局 `idx`，模板改为：

```
- [#12] 00:00:24 一分钟 好烫好烫
```

> 注意 dense chunk 的下采样：被采样掉的弹幕不会出现在 `chunks.md` 里，Agent 标不到。这些弹幕的 label 缺省为 `neutral`（见下「缺省与兜底」），保证 ALL 视图仍显示它们、只是不带情绪色。

### 流水线改动

| 文件 | 改动 |
|---|---|
| `slice_chunks.py` | 渲染 chunks 时为每条 display danmaku 附带全局 `idx`；写空骨架 `danmaku_labels.json`（`[]`） |
| `chunks_prompt.md.j2` | 弹幕行加 `[#idx]` 前缀 |
| `scoring_rubric.md` | 新增「§7 单条弹幕标注」小节，说明产出 `danmaku_labels.json` + neutral 判据 |
| `render_report.py` | 读 `danmaku_labels.json`（缺失则传空），注入 HTML 新 script 块 `data-danmaku-labels` |
| `report.html.j2` | 新增 `<script type="application/json" id="data-danmaku-labels">` |
| `app.js` | `renderDanmakuList()` 改读单条 label；新增 neutral 处理与筛选行为 |

### 渲染层行为（app.js）

1. 读取 `DANMAKU_LABELS`（新常量），构建 `idx → dim` 查表
2. `renderDanmakuList()`：每条弹幕的 `dim` 改为查 label 表
   - 命中 8 维 → 对应颜色圆点，`data-dim` 设为该维
   - `neutral` 或查不到 → 灰色圆点，`data-dim="neutral"`
3. 筛选行为：
   - **ALL**：显示全部弹幕（含 neutral），计数保持全量
   - **点某情绪键**：只显示 `data-dim` == 该维的弹幕；neutral 和其它维一起隐藏
   - 搜索框逻辑不变，与情绪筛选取交集
4. 顶部 `Danmaku stream` 计数保持 `total_danmaku`（全量）不变

### 缺省与兜底

- `danmaku_labels.json` 缺失或为空数组（旧报告 / Agent 未标注）→ **回退现有 `dominantDim(chunk)` 逻辑**，不报错、不留空白列表
- label 表只覆盖部分 idx（dense chunk 采样导致）→ 未覆盖的 idx 视为 `neutral`
- 这样保证向后兼容：已有 demo 报告无需重跑

## 测试

- `test_stage2_slice.py`：断言 `danmaku_labels.json` 空骨架被创建；`chunks.md` 弹幕行含 `[#idx]`
- `test_stage5_render.py`：断言 HTML 含 `data-danmaku-labels` script 块；labels 缺失时仍能渲染（兜底）
- 手动验收：重跑两个第五人格视频，确认「吵死了」归 disgust、「本来还点赞了…取消」归 disgust/anger、「?」「0分钟前」归 neutral 且情绪筛选时被隐藏

## 影响面小结

- 新增 1 个产物文件、1 个 HTML script 块、rubric 1 小节
- 修改 5 个文件，均为增量、带兜底，不破坏既有报告
- chunk 级分析链路零改动
