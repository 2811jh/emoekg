---
name: emoekg
description: Use when the user asks to analyze the emotional arc of a Bilibili video through its danmaku, generate an "emotional ECG" / 情绪心电图 / 弹幕情绪时间线 report, identify hype moments (炸点) / cold moments (冷场) / emotional shifts (情绪反转) in a video, or produce an interactive HTML report overlaying Plutchik 8-dim emotion timeline on a Bilibili video. Triggers on phrases like 弹幕情绪分析, 情绪心电图, 炸点分析, 情绪曲线, B 站弹幕报告, bilibili danmaku emotion, emotional ECG.
---

# emoekg — Bilibili Danmaku Emotional ECG

## Overview

**Core principle:** 把一个 B 站视频的数十万条弹幕压成一张"情绪心电图"——
8 维（Plutchik）情绪分量随时间演化的交互式 HTML 报告，
带峰值 / 谷值 / 情绪反转 3 类转折点识别，以及每个转折点的佐证弹幕。

emoekg 是 **Agent-driven** 的：纯 Python 负责数据 I/O + 算法，
**情绪打分（Stage 3）由你（AI Agent）在对话中直接完成**。
不需要外部 LLM API、不需要用户手动标注。

面向 UX 研究员、内容分析师、游戏体验研究，产出单文件 HTML 报告（无需联网即可离线查阅）。

## When to Use

- 用户说「分析一下这个 B 站视频的弹幕情绪」、「帮我画一下这个视频的情绪曲线」
- 用户给出 B 站 URL / BV 号，要求识别**炸点 / 冷场 / 情绪反转**
- 内容研究场景：对比多个视频的情绪节奏、找剪辑教学样本、抓体验研究引用片段
- 用户要求产出**可交互的 HTML 报告**来过目多条弹幕

**不适用：**
- 其他平台（YouTube / Twitch / 抖音）——本工具只解 Bilibili
- 纯数据抓取（不含情绪分析）——用户只要 CSV 的话不需要本 skill
- 实时直播弹幕——本工具只处理已完结视频的历史弹幕

## Core Framework

### 5 阶段流水线

| Stage | 职责 | 谁做 | 产出 |
|---|---|---|---|
| **S1 Fetch** | 拉视频元信息 + 全量历史弹幕 | Python | `meta.json`, `danmaku.json` |
| **S2 Slice** | 按自适应窗口切片，渲染给 Agent 看的 prompt | Python | `chunks.md`, 空 `scores.json`, 空 `insights.json` |
| **S3 Score + Summarize** | **8 维 0–10 打分 + 写 Executive Summary** | **你（Agent）** | 填回 `scores.json` 和 `insights.json` |
| **S4 Detect** | 峰值检测 + JS 散度对比 + 合并 | Python | `turnpoints.json` |
| **S5 Render** | 渲染交互式 HTML | Python | `emoekg_report.html` |

S1+S2 和 S4+S5 是两个子进程调用；**Stage 3 夹在中间**，由你在对话里完成
两件事：(a) 按 rubric 给每个 chunk 打分，(b) 写一份 TL;DR + 三条 insight。

### 打分维度（Plutchik 8）

| 维度 | 中文 | 典型弹幕信号 |
|---|---|---|
| joy | 喜悦 | `哈哈哈`、`233`、`笑死` |
| trust | 信任 | `yyds`、`稳`、`专业` |
| fear | 恐惧 | `要出事了`、`慌`、`完蛋` |
| surprise | 惊奇 | `卧槽`、`啊这`、`???` |
| sadness | 悲伤 | `破防`、`emo`、`泪目` |
| disgust | 厌恶 | `恶心`、`下头`、`辣眼` |
| anger | 愤怒 | `退游`、`策划死`、`滚` |
| anticipation | 期待 | `蹲下一集`、`催更`、`求出` |

详细判据见 `docs/scoring_rubric.md`（是 Stage 3 的权威参考）。

## Workflow

```
用户：帮我分析 https://www.bilibili.com/video/BV... 的弹幕情绪
           ↓
[1] emoekg prepare <url> -o emoekg_<BV>_<date>/
       → Stage 1（拉弹幕）+ Stage 2（切片）
       → 产出 chunks.md 给你（Agent）看
           ↓
[2] 你读 chunks.md，按 docs/scoring_rubric.md 打分
       → 写回 scores.json（数组长度 = chunk 数，13 字段/行）
           ↓
[3] emoekg finalize -o emoekg_<BV>_<date>/
       → Stage 4（识别转折点）+ Stage 5（渲染 HTML）
       → emoekg_report.html 交付给用户
           ↓
[4] 用户在浏览器打开 HTML 报告（自动缩放 / 筛选维度 / 点击跳转视频）
```

### 执行步骤

**Step 1 — 确认输入**

向用户确认：
- B 站视频 URL / BV 号（必需）
- 是否需要 `--with-video` 模式（可选，需本地 MP4，触发时告诉用户要先用 `yutto` 或其他工具下载视频到 `video.mp4`）

**Step 2 — 准备数据**

```bash
emoekg prepare <url_or_bvid> -o emoekg_<BV>_<YYYYMMDD>/
```

CLI 会：
- 在 `<working_dir>/` 下生成 `meta.json` + `danmaku.json`
- 切片成 ~90 个 chunk，生成 `chunks.md`（给你看的 prompt）
- 写入空骨架 `scores.json`（`[]`）

完成后 CLI 会提示 `Waiting for Agent scoring`。

**Step 3 — Agent 打分 + 写洞察（你在对话里直接做）**

1. `read_file` 读 `<working_dir>/chunks.md`
2. 读一遍 `emoekg/docs/scoring_rubric.md`（如果记忆里不够清楚）
3. 为每一个 chunk 按 rubric 逐一打分：
   - 8 个维度（joy / trust / fear / surprise / sadness / disgust / anger / anticipation）
   - 每个 0–10 整数
   - `n_danmaku < 3` 或 header 标 `【SPARSE】` → 全 0 + `note="SPARSE"`
   - 普通块 `note` ≤30 字概括情绪场面
4. **`write` 工具**把完整 JSON 数组写回 `<working_dir>/scores.json`
   - 数组顺序严格对齐 chunk 顺序（C001 → Cxxx）
   - 每行 13 个字段：`chunk_id` / `time_start` / `time_end` / `n_danmaku` / 8 个情绪 / `note`
5. **通读全部 scores 找规律，写 `insights.json`**（rubric §6 有完整指南）：
   - `summary`：30–80 字一句话，**洞察性**语言（不是描述）
   - `insights`：严格 3 条，每条 `title` 4–8 字 + `body` 40–80 字
   - 三条要覆盖**节奏 + 机制 + 反差**三种视角，不能三条讲同一件事
6. 自检（rubric §5 + §6.6），确保没字段缺失 / 越界 / 三条 insight 同质

> **不要请求用户**手动打分或写洞察，不要调用外部 API，不要写额外 Python 脚本——
> 直接用 `read_file` + `write` 就能完成全部工作。

> **新协议（v0.1.1 起）：** 如果你跳过 `insights.json`，报告仍能渲染，
> 但 Hero 区会缺 Executive Summary——研究员打开报告第一眼就发现没 TL;DR。
> **一定要写**，这是 emoekg 交付的核心价值。

**Step 4 — 渲染报告**

```bash
emoekg finalize -o emoekg_<BV>_<YYYYMMDD>/
```

或者如果用户要本地视频双向同步：

```bash
emoekg finalize -o emoekg_<BV>_<YYYYMMDD>/ --with-video
```

产出 `emoekg_report.html`（~1 MB，自带 ECharts，可完全离线打开）。

**Step 5 — 质量自检**

交付前确认：
- [ ] `scores.json` 长度 == chunks 数
- [ ] `insights.json` 有 `summary`（30–80 字）+ 恰好 3 条 `insights`（每条 `title` + `body`）
- [ ] 三条 insight 覆盖节奏 / 机制 / 反差三种视角，不是同一件事换三种说法
- [ ] `turnpoints.json` 至少有 3 条（典型 30 分钟视频应该有 5–15 条）
- [ ] HTML 打开后图表非空、至少能看到一条情绪曲线
- [ ] HTML Hero 区 TL;DR 和 Insights 能正常显示
- [ ] 非 SPARSE chunk 不要全 0（警示线：见 S4 `WARN` 输出）

## Quick Reference

### CLI 命令速查

| 命令 | 用途 |
|---|---|
| `emoekg prepare <url> -o <dir>` | 跑 S1+S2，然后停住等你打分 |
| `emoekg finalize -o <dir>` | 跑 S4+S5，要求 scores.json 已填 |
| `emoekg finalize -o <dir> --with-video` | 同上，但切到本地 video.mp4 双向同步 |
| `emoekg run <url> -o <dir>` | 一条命令跑完；如果 scores.json 还空会等你 |
| `emoekg <任意命令> --force` | 忽略已存在的中间产物重跑 |
| `emoekg --version` | 打印版本 |

### 输出目录结构

```
emoekg_BV1xxxxxx_20260507/
├── meta.json               # S1 输出
├── danmaku.json            # S1 输出（可能 1–50 MB）
├── chunks.md               # S2 输出 — Agent prompt
├── scores.json             # S2 空骨架 → S3 你填
├── turnpoints.json         # S4 输出
├── emoekg_report.html      # S5 输出 — 最终交付
└── (可选) video.mp4         # --with-video 模式用
```

### 打分小抄（0/3/6/9 四锚点）

| 分数 | 含义 |
|---|---|
| 0 | 一条相关表达都没有 |
| 3 | 有 1–2 条，但不是主流 |
| 6 | 多条，接收者一眼能辨认这个情绪 |
| 9 | 刷屏、占一半以上弹幕 |

详细见 `docs/scoring_rubric.md`。

## Common Mistakes

| 陷阱 | 应对 |
|---|---|
| **跳过 Stage 3 直接 `finalize`** | CLI 会拒绝并提示你打分；不要改 CLI 去绕过 |
| **`scores.json` 长度 ≠ chunks 数** | S4 会 ERROR 退出；回去补齐 |
| **把 SPARSE 块硬打分** | 按 rubric §4.1 写 `[0]*8` + `note="SPARSE"`，别想当然 |
| **非 SPARSE 块全 0** | S4 会 WARN；说明你漏看了；回去重打 |
| **非整数 / >10 / 负数** | `plutchik.validate_score_entry` 会抛错；老实 0–10 整数 |
| **误判情绪方向** | `笑死` 在嘲讽语境是 anger/disgust，不是 joy；读上下文 |
| **自己写 Python 算分** | 别。rubric 的重点就是**你自己理解弹幕**，算法层会毁掉这件事的价值 |
| **把全部弹幕抄回 scores.json** | 不用。只打 8 维分 + note |

## Red Flags — STOP and Reconsider

看到这些征兆，说明打分没到位：

- 所有 chunk 的 joy 都是 5（你在偷懒求平均）
- 所有 chunk 的 note 都一样（你没真的读）
- `note` 里写了 `"根据数据分析"、"该区间"、"综合考虑"` 之类的算法腔
- S4 的 WARN 说 `>20% 非 SPARSE chunks 全零`
- `turnpoints.json` 只有 0–1 条（要么视频太短要么打分太平）

**所有这些都意味着：回去重读 `chunks.md` 和 `docs/scoring_rubric.md`，重来。**

## Files

- `SKILL.md`（本文件）— Skill 契约 + 工作流
- `docs/scoring_rubric.md` — Stage 3 打分细则（**你必读**）
- `docs/2026-05-07-emoekg-design.md` — 系统设计文档（架构 / 算法）
- `src/emoekg/cli.py` — CLI 入口（`emoekg prepare / finalize / run`）
- `src/emoekg/stages/` — 4 个 Python stage（S1/S2/S4/S5）
- `src/emoekg/_lib/` — 底层算法（窗口、峰值、JS 散度、佐证采样）
- `src/emoekg/templates/` — HTML 模板 + 内联 ECharts + `app.js`
- `tests/` — 157+ 个单测（`pytest` 跑通）
- `requirements.txt` — Python 依赖

## Installation

```bash
pip install -e .
```

可选：`pip install -e ".[video]"` 安装 `yutto` 支持 `--with-video` 本地视频下载。
