# emoekg — Emotional ECG for Bilibili Danmaku

> 一张"情绪心电图"把一个 B 站视频的数十万条弹幕压成 8 维（Plutchik）情绪时间线，
> 识别炸点 / 冷场 / 情绪反转，产出可离线交互的单文件 HTML 报告。

![status](https://img.shields.io/badge/status-alpha-orange) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![tests](https://img.shields.io/badge/tests-190%20passing-brightgreen)

## What

- 输入：一个 B 站视频 URL 或 BV 号
- 输出：`emoekg_report.html` —— 单文件、约 1 MB、**完全离线可用**的交互报告
  - 8 条情绪曲线（Plutchik 轮：joy / trust / fear / surprise / sadness / disgust / anger / anticipation）
  - 峰值 / 谷值 / 情绪反转 3 类转折点，每个带佐证弹幕
  - 点击图表跳转视频（iframe 或本地 `video.mp4` 双向同步）
  - 弹幕列表按维度过滤

## Why it's different

emoekg 的情绪打分**由 AI Agent 在会话里直接完成**，不走外部 LLM API。
适用于 Codex / CodeMaker / Claude Code 这类有工具调用能力的对话环境——
Skill 契约（`SKILL.md`）告诉 Agent：
- 什么时候跑哪个子命令
- 怎么按 rubric 给每一个 chunk 打 0–10 分
- 如何识别 SPARSE 块 / 处理复读 / 区分 `笑死` 的正负向

## Installation

```bash
git clone https://github.com/2811jh/emoekg.git
cd emoekg
pip install -e .
# 或者可选：pip install -e ".[video]" 装 yutto 支持本地视频下载
```

## Demo

仓库里自带一个真实 demo：[`demos/bv18acmz4ell/emoekg_report.html`](demos/bv18acmz4ell/emoekg_report.html)
——分析《万字攻略 一口气玩会亡者世界！》（BV18acMz4ELL，221 条弹幕、15:14），
下载后双击即开，**完全离线工作**。

## Usage (as an Agent Skill)

在一个支持 Skill 的 AI 对话环境里：

```
你：帮我分析这个视频 https://www.bilibili.com/video/BV1xxxx 的弹幕情绪
Agent：（读 SKILL.md → 调 `emoekg prepare ...` → 读 chunks.md → 按 rubric 打分
       → 写 scores.json → 调 `emoekg finalize ...` → 返回 emoekg_report.html）
```

## Usage (CLI 手动)

如果你想手动跑（自己负责打分部分，比如用别的 LLM 或自己标注）：

```bash
# 1. 拉弹幕 + 切片
emoekg prepare BV1xxxx -o my_report/

# 2. 打开 my_report/chunks.md，按 docs/scoring_rubric.md 的 rubric
#    把每一个 chunk 打 8 维 0–10 分，填回 my_report/scores.json

# 3. 生成报告
emoekg finalize -o my_report/

# 可选：用本地视频替代 B 站 iframe，获得双向同步
emoekg finalize -o my_report/ --with-video
```

### 一条命令版本（如果 `scores.json` 已经存在）

```bash
emoekg run BV1xxxx -o my_report/
```

## How it works

5 阶段流水线，中间用 JSON 文件落盘支持断点续跑：

```
BV URL
   ↓  Stage 1: 拉元信息 + 全量历史弹幕（bilibili-api-python，分段 Protobuf）
meta.json + danmaku.json
   ↓  Stage 2: 自适应窗口切片（target ~90 chunks），渲染 prompt
chunks.md + scores.json (空骨架)
   ↓  Stage 3: Agent 按 rubric 打 8 维 0–10 分          ← 人/Agent 介入点
scores.json (已填)
   ↓  Stage 4: scipy 峰值检测 + Jensen-Shannon 散度反转检测 + 合并
turnpoints.json
   ↓  Stage 5: Jinja2 渲染 + 内联 ECharts + app.js
emoekg_report.html
```

## Project Structure

```
emoekg/
├── SKILL.md                    # Agent 契约（本工具的灵魂）
├── docs/
│   ├── scoring_rubric.md       # Stage 3 打分细则
│   └── 2026-05-07-emoekg-design.md  # 架构设计文档
├── src/emoekg/
│   ├── cli.py                  # emoekg prepare / finalize / run
│   ├── __main__.py             # python -m emoekg
│   ├── stages/                 # 4 个 Python stage（S1/S2/S4/S5）
│   ├── _lib/                   # 窗口 / 峰值 / JS 散度 / 佐证采样
│   └── templates/              # HTML 模板 + app.js + vendor ECharts
└── tests/                      # 190 个单测
```

## Status

v0.1.1 — 功能完整，端到端可跑通；后续计划：
- [ ] 多视频对比（同一 UP / 同一系列）
- [ ] 导出情绪摘要 CSV
- [ ] 可选离线视频下载（yutto 集成完善）

## License

MIT © 2026 2811jh
