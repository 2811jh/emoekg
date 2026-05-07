# 📈 emoekg — Emotional ECG for Bilibili Danmaku

> 把 B 站视频的弹幕压成一张"情绪心电图"，识别炸点 / 冷场 / 情绪反转，产出可离线交互的单文件 HTML 研究报告。

一个 [Agent Skills](https://github.com/anthropics/courses/tree/master/tool_use) 格式的 AI 助手技能——**AI Agent 在对话里直接按 Plutchik 八维情绪打分**，不走外部 LLM API，不要一行提示工程。适用于 Codex / CodeMaker / Claude Code 这类支持工具调用的对话环境，也可以手动当 CLI 用。

![status](https://img.shields.io/badge/status-alpha-orange) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![tests](https://img.shields.io/badge/tests-190%20passing-brightgreen) ![license](https://img.shields.io/badge/license-MIT-lightgrey)

📺 **Live Demo**：[demos/bv18acmz4ell/emoekg_report.html](demos/bv18acmz4ell/emoekg_report.html)（clone 后双击即开，完全离线）

---

## 🚀 安装

### 第 1 步：安装前置软件

需要先安装以下 2 个软件，已装过的可以跳过：

| # | 软件 | 下载地址 | 注意事项 |
|---|------|----------|----------|
| 1 | [Git](https://git-scm.com/download/win) | https://git-scm.com/download/win | 安装时保持默认选项即可 |
| 2 | [Python 3](https://www.python.org/downloads/) | https://www.python.org/downloads/ | ⚠️ 安装时**务必勾选** "Add Python to PATH"，版本要求 **3.10+** |

> 💡 两个软件都装完后，**关掉所有已打开的命令行窗口**，重新打开才能生效。

### 第 2 步：打开命令行

按键盘 `Win + R`，输入 `cmd`，按回车。

### 第 3 步：安装 skill

在命令行中粘贴以下命令，回车执行：

```bash
npx skills add 2811jh/emoekg
```

过程中如果提示 `Ok to proceed? (y)`，输入 `y` 回车即可。

### 第 4 步：安装 Python 依赖

继续在命令行中执行：

```bash
pip install -e .
```

> ✅ 全部完成！现在可以在 AI 助手中使用 emoekg 了。

### 可选：本地视频模式（双向同步心电图 ↔ 视频进度）

```bash
pip install -e ".[video]"
```

装 `yutto` 后可用 `--with-video` 参数下载 B 站原视频内嵌到报告里，实现真正的双向联动（点击心电图跳转视频、视频播放时心电图光标跟随）。

---

## ✨ 功能全景

### 🎯 一键生成情绪心电图
- **免登录全量弹幕** — 拉取 B 站历史弹幕档案（分段 Protobuf），不受前端 3000 条限制
- **自适应窗口切片** — 根据视频时长自动选择 15s / 30s / 60s 窗口（目标 ~90 chunks）
- **Agent 驱动 8 维打分** — AI 按 Plutchik 情绪轮盘直接在对话里打分，无需外部 LLM API
- **双算法转折检测** — scipy 峰值检测（PEAK / VALLEY）+ Jensen–Shannon 散度反转检测（SHIFT）
- **单文件离线报告** — ~1 MB 的 HTML，ECharts 全部内联，双击即开

### 🎨 Swiss × Editorial 研究档案风格
- **12 列网格 + 系统字体** — 0 CDN 依赖，国内外加载都稳
- **发光 ECG 曲线** — 8 条情绪时间线叠加，hover 聚焦单一维度
- **Live Trace 脉冲指示** — 视频与心电图标题旁的呼吸红点，强化"监护仪"质感
- **Executive Summary** — Hero 区 TL;DR + 三条研究洞察（节奏 / 机制 / 反差三视角）

### 🔍 可交互研究工作区
- **点击心电图任意位置跳视频** — canvas 反算时间 → iframe `t` 参数 seek
- **转折点卡片可折叠** — 前 3 条默认展开，点卡片展开/折叠，点时间跳视频
- **佐证弹幕自动采样** — 每个 TP 附带 3–5 条按关键词 > 长度 > 时间排序的代表弹幕
- **弹幕列表多维筛选** — 按 8 个情绪维度过滤 + 关键词搜索

### 🤖 AI Agent 契约（SKILL.md）
- **Stage 3 评分规则** — `docs/scoring_rubric.md` 定义 0–10 分刻度、SPARSE 处理、反讽判定
- **Insights Protocol** — 强制 30–80 字 TL;DR + 恰好 3 条洞察，三视角互斥
- **五阶段自检清单** — scores.json 长度 / insights 字段完整 / 非 SPARSE 不全 0 等

---

## 📖 使用方式

### 方式 A：在 AI 助手里对话触发（推荐）

安装后，在你的 AI 编程助手中直接说：

| 场景 | 示例表达 |
|------|----------|
| 分析视频 | "帮我分析这个视频的弹幕情绪 https://www.bilibili.com/video/BV18acMz4ELL/" |
| 用 BV 号 | "用 emoekg 跑一下 BV1xxxx" |
| 指定输出目录 | "分析 BV1xxxx，报告放在 reports/game_review/" |
| 带本地视频 | "分析 BV1xxxx 并下载原视频内嵌到报告里" |

Agent 会自动：
1. 读 `SKILL.md` → 调 `emoekg prepare` 拉弹幕 + 切片
2. 读 `chunks.md` → 按 rubric 在对话里给每个 chunk 打 8 维 0–10 分
3. 写 `scores.json` + `insights.json`
4. 调 `emoekg finalize` → 生成 `emoekg_report.html`

### 方式 B：CLI 手动跑（你负责打分）

适合用别的模型打分、自己标注、或批量处理多视频：

```bash
# 1. 拉弹幕 + 切片
emoekg prepare BV18acMz4ELL -o my_report/

# 2. 打开 my_report/chunks.md，按 docs/scoring_rubric.md 的 rubric
#    给每个 chunk 打 8 维 0–10 分，填回 my_report/scores.json
#    可选：同时写 my_report/insights.json（summary + 3 insights）

# 3. 生成报告
emoekg finalize -o my_report/

# 可选：用本地视频替代 B 站 iframe，获得双向同步
emoekg finalize -o my_report/ --with-video
```

### 典型工作流

```
1. 粘贴视频 URL            →  "帮我分析 BV18acMz4ELL"
2. 自动拉弹幕 + 切片        →  Stage 1 + 2（Python）
3. Agent 按 rubric 打分    →  Stage 3（对话里完成，几十秒到几分钟）
4. 自动检测转折 + 渲染      →  Stage 4 + 5（Python）
5. 打开 emoekg_report.html →  阅读、复盘、导出截图
```

---

## 🔧 CLI 命令一览

```bash
# 完整流水线 — 只在 scores.json 已存在时能端到端跑完
emoekg run BV18acMz4ELL -o my_report/

# 分阶段跑（Agent 工作流）
emoekg prepare  BV18acMz4ELL -o my_report/      # Stage 1 + 2
emoekg finalize              -o my_report/      # Stage 4 + 5
```

| 命令 | 功能 | 关键参数 |
|------|------|----------|
| `prepare` | 拉弹幕 + 切片，产出 `chunks.md` 给 Agent 打分 | `-o` 输出目录、`--force` 清旧缓存 |
| `finalize` | 读 `scores.json` → 检测转折 → 渲染 HTML | `-o`、`--force`、`--with-video` |
| `run` | 跑完整 4 个 Python stage（要求 `scores.json` 已就位） | `-o`、`--with-video` |

所有命令都接受 BV 号或完整 URL，比如 `BV18acMz4ELL`、`https://www.bilibili.com/video/BV18acMz4ELL/?spm_id_from=...`。

---

## 📄 数据产物（working dir 布局）

每次分析会在输出目录下生成 7 个文件，中间态全部落盘支持断点续跑：

```
my_report/
├── meta.json              视频元信息（BV、时长、UP 主、弹幕总数）
├── danmaku.json           全量历史弹幕（time / text / color / mode）
├── chunks.md              分块的 Markdown，Agent 在这里打分
├── scores.json            8 维 0–10 分打分结果（Agent 产出）
├── insights.json          TL;DR + 3 条洞察（Agent 产出）
├── turnpoints.json        合并后的转折点 + 佐证弹幕
└── emoekg_report.html     单文件离线交互报告（~1 MB）
```

### scores.json 字段

每行 13 个字段，与 `chunks.md` 严格同序：

```json
{
  "chunk_id":    "C001",
  "time_start":  0,
  "time_end":    15,
  "n_danmaku":   13,
  "joy":         3,
  "trust":       5,
  "fear":        0,
  "surprise":    2,
  "sadness":     1,
  "disgust":     0,
  "anger":       0,
  "anticipation": 4,
  "note":        "开场价格讨论：'10块钱''已取餐'，轻度惊喜+信任"
}
```

- **8 维情绪** `joy / trust / fear / surprise / sadness / disgust / anger / anticipation`
- **0–10 分刻度**：0 完全没有 → 4–6 主流情绪 → 8+ 强烈爆发 → 10 刷屏级
- **SPARSE 规则**：`n_danmaku < 3` → 八维全 0 + `note="SPARSE"`

### insights.json 格式

```json
{
  "summary": "一支讲模组的 15 分钟视频，弹幕却被价格和彩蛋彻底改写成购物派对。",
  "insights": [
    {"title": "双峰结构",   "body": "情绪强度在 09:15 电锯人彩蛋..."},
    {"title": "购买转化段", "body": "前 90s 弹幕被 '10块钱/700已入手/已取餐'..."},
    {"title": "冷热反差",   "body": "C041 突然出现 sadness+trust 组合..."}
  ]
}
```

- `summary`：**30–80 字**一句话 TL;DR，要是**洞察**，不是描述
- `insights`：**严格 3 条**，`title` 4–8 字 + `body` 40–80 字
- 三条必须覆盖**节奏 / 机制 / 反差**三个视角，不能是同一件事换三种说法

---

## 🧬 How it works — 5 阶段流水线

```
BV URL
   ↓  Stage 1: 免登录拉元信息 + 全量历史弹幕
              （bilibili-api-python，分段 Protobuf 自动拼接）
meta.json + danmaku.json
   ↓  Stage 2: 自适应窗口切片（target ~90 chunks），渲染给 Agent 的 prompt
chunks.md + scores.json (空骨架)
   ↓  Stage 3: Agent 按 rubric 打 8 维 0–10 分             ← 人/Agent 介入点
              同时写 insights.json（TL;DR + 3 洞察）
scores.json (已填) + insights.json
   ↓  Stage 4: scipy find_peaks 峰值检测
              + Jensen–Shannon 散度情绪反转检测
              + 时间簇合并去重（≤15 个）
              + 按关键词 > 长度 > 时间采样佐证弹幕
turnpoints.json
   ↓  Stage 5: Jinja2 渲染 Swiss Dark 模板
              + 内联 ECharts 5.5 + app.js
emoekg_report.html
```

### 为什么 Agent 来打分？

情绪分级不是简单查词典能搞定的事——一句"笑死"可能是正向笑点（joy=7）也可能是讽刺（disgust=6），需要理解上下文、识别复读梗、忽略无意义刷屏。把这一步交给对话里的 AI，相比调用外部 LLM API 有三个好处：

1. **零 API Key**——终端用户装了 skill 就能用，不需要配置 OpenAI / Anthropic 密钥
2. **上下文原生**——Agent 看得到完整 `chunks.md`，能做跨 chunk 的语义参考
3. **成本可控**——算法密集的部分（峰值检测 / 散度计算）跑在本地 Python，Agent 只做它最擅长的语义打分

---

## 📁 项目结构

```
emoekg/
├── SKILL.md                          # Agent 契约（工作流 + Stage 3 产出要求）
├── README.md
├── LICENSE
├── pyproject.toml                    # 安装配置 + 依赖声明 + CLI entry point
├── .gitignore
│
├── docs/
│   └── scoring_rubric.md             # Stage 3 打分细则（0–10 分刻度、SPARSE、Insights Protocol）
│
├── demos/                            # 真实端到端示例
│   └── bv18acmz4ell/                 #   《万字攻略 一口气玩会亡者世界》
│       ├── meta.json                 #   221 danmakus / 15:14
│       ├── danmaku.json
│       ├── chunks.md
│       ├── scores.json
│       ├── insights.json
│       ├── turnpoints.json           #   7 merged turnpoints
│       └── emoekg_report.html        #   1.1 MB 单文件报告
│
├── src/emoekg/
│   ├── __init__.py
│   ├── __main__.py                   # python -m emoekg 入口
│   ├── cli.py                        # emoekg {prepare, finalize, run}
│   │
│   ├── _lib/                         # 纯函数业务层（无 IO 副作用）
│   │   ├── bv_parser.py              #   URL / BV 号解析
│   │   ├── time_utils.py             #   HH:MM:SS 格式化
│   │   ├── adaptive_window.py        #   自适应窗口大小计算
│   │   ├── plutchik.py               #   8 维情绪 schema + 校验
│   │   ├── danmaku_client.py         #   bilibili-api 封装（重试 / 去重 / 色值归一化）
│   │   ├── turnpoint_algo.py         #   peaks + valleys + JS 散度 + cluster merge
│   │   └── evidence_picker.py        #   佐证弹幕采样排序
│   │
│   ├── stages/                       # 4 个 Python 阶段（S1/S2/S4/S5）
│   │   ├── fetch_danmaku.py          #   Stage 1: 拉 meta + 全量弹幕
│   │   ├── slice_chunks.py           #   Stage 2: 切片 + 渲染 prompt
│   │   ├── detect_turnpoints.py      #   Stage 4: 转折检测 + 合并 + 佐证
│   │   └── render_report.py          #   Stage 5: Jinja2 + 内联 ECharts
│   │
│   └── templates/
│       ├── report.html.j2            # Swiss × Editorial 报告模板
│       ├── app.js                    # ECharts 交互 / 视频联动 / 过滤搜索
│       ├── chunks_prompt.md.j2       # 给 Agent 看的 chunks.md
│       └── vendor/
│           └── echarts.min.js        # ECharts 5.5 UMD（离线内联）
│
└── tests/                            # 190 个单测，覆盖全链路
    ├── test_smoke.py
    ├── test_bv_parser.py
    ├── test_time_utils.py
    ├── test_adaptive_window.py
    ├── test_plutchik.py
    ├── test_danmaku_client.py
    ├── test_evidence_picker.py
    ├── test_turnpoint_algo.py
    ├── test_stage1_fetch.py
    ├── test_stage2_slice.py
    ├── test_stage4_detect.py
    ├── test_stage5_render.py
    └── test_cli.py
```

### 架构设计

采用**三层职责分层**，单向依赖：

```
CLI / Stages（编排层）  ──依赖──→  _lib（纯业务逻辑）  ──依赖──→  第三方库
```

- **`_lib/` 层**：纯函数，无 IO 副作用，100% 可单测。情绪算法、时间处理、弹幕采样都在这里。
- **`stages/` 层**：每个 Stage 一个文件，负责**读文件 → 调 `_lib` → 写文件**。阶段间只通过 JSON 落盘通信，天然支持断点续跑。
- **`cli.py` 层**：薄包装，把 3 个子命令（`prepare / finalize / run`）dispatch 到对应 stage 脚本。

这样 Agent 可以只关心 Stage 3（打分）一件事，其它阶段全自动——这是 SKILL 契约能做到"只告诉 Agent 打分规则就够了"的关键。

---

## 🎨 报告设计语言

- **主题**：Swiss × Editorial 暗色研究档案风（参考 Stripe Press / Pentagram）
- **字体**：纯系统字体栈（Inter 族 + IBM Plex 族降级），零 CDN 依赖
- **调色板**：11 阶中性灰 `#0a0a0b → #f4f4f6` + 单一强调色 `#EB5E28`
- **版式**：12 列网格，ample negative space，超大字号对比（display 60px ↔ micro 10px）
- **图表**：ECharts 5.5，自定义磷光发光（shadowBlur 2 / emphasis 8）
- **动效**：Live Trace 呼吸圆点（1.6s 三段 keyframes）

打印模式（`@media print`）自动翻转为浅色高对比版，可直接 PDF 导出做调研报告附录。

---

## 🔐 安全与隐私

- **免登录** — 整个流水线不需要 B 站账号，不访问私有接口，只拉公开弹幕档案
- **不发外部 API** — Agent 打分全程在对话上下文内完成，弹幕原文不会出站
- **离线可用** — 生成的 HTML 所有依赖（ECharts）都内联，可直接分发给不能连网的用户
- **本地缓存** — 所有中间 JSON 文件留在你指定的输出目录，可随时删除

---

## 🧪 测试

```bash
pip install pytest
python -m pytest
# 190 tests pass
```

测试覆盖：BV 解析、时间格式化、自适应窗口、Plutchik schema 校验、弹幕 client 三类 bug 回归、峰值 / JS 散度算法、佐证采样、5 个 stage 集成、CLI subcommands。

---

## 📊 Demo 数据

仓库内的 [`demos/bv18acmz4ell/`](demos/bv18acmz4ell/) 是一次真实端到端运行：

| 项 | 值 |
|---|---|
| 视频 | 《万字攻略 一口气玩会亡者世界！惊变末日搜打撤 网易必玩神作！》 |
| BV 号 | BV18acMz4ELL |
| 时长 | 15:14 |
| 弹幕总数 | 221 条 |
| 切片数 | 61 chunks @ 15s 窗口 |
| 检测转折 | 7 个（2 PEAK + 5 SHIFT，已合并去重） |
| 报告大小 | 1.1 MB（含内联 ECharts） |

直接下载 `emoekg_report.html` 双击打开即可，所有交互（心电图点击 / 弹幕筛选 / 转折点佐证）完全离线工作。

---

## 📝 路线图

- [x] v0.1.0 — 核心流水线 + CLI + SKILL 契约
- [x] v0.1.1 — Swiss × Editorial UI + Insights Protocol + 真实数据验证
- [ ] v0.2.0 — 多视频对比（同一 UP / 同一系列横向分析）
- [ ] v0.2.0 — 导出情绪摘要 CSV / Markdown 表格
- [ ] v0.3.0 — yutto 集成完善，一键 `--with-video` 下载内嵌
- [ ] v0.3.0 — 抖音 / YouTube 数据源适配（同 SKILL 接口）

---

## 📄 License

MIT © 2026 [2811jh](https://github.com/2811jh)
