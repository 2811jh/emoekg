# 📈 emoekg — Emotional ECG for Bilibili Danmaku

> 把 B 站视频的弹幕压成一张"情绪心电图"，识别炸点 / 冷场 / 情绪反转，产出可离线交互的单文件 HTML 研究报告。

一个 [Agent Skills](https://github.com/anthropics/courses/tree/master/tool_use) 格式的 AI 助手技能——**AI Agent 在对话里直接按 Plutchik 八维情绪打分**，不走外部 LLM API，不要一行提示工程。适用于 Codex / CodeMaker / Claude Code 这类支持工具调用的对话环境，也可以手动当 CLI 用。

![status](https://img.shields.io/badge/status-beta-blue) ![version](https://img.shields.io/badge/version-0.5.0-EB5E28) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![tests](https://img.shields.io/badge/tests-194%20passing-brightgreen) ![license](https://img.shields.io/badge/license-MIT-lightgrey)

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

继续在命令行中执行（先 cd 进 skill 目录，再 pip install）：

```bash
cd %USERPROFILE%\.agents\skills\emoekg
pip install -e .
```

> ✅ 全部完成！现在可以在 AI 助手中使用 emoekg 了。

### 🔄 更新到最新版

如果你之前已经安装过，执行以下命令更新：

```bash
cd %USERPROFILE%\.agents\skills\emoekg
git pull
pip install -e .
```

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

### 🎨 Cockpit Console — 监护仪式信息架构（v0.4.x）
- **驾驶舱布局** — 视频 + ECG 心电图 + 8 维 Vital Readout 三联仪表盘，鼠标悬停 ECG 即时联动右侧仪表
- **Live Trace 脉冲** — 视频与心电图标题旁的呼吸红点同步，强化"监护仪"质感
- **Vital Stats 6 卡** — 总弹幕量 / 极性比 / 主导情绪 / 最炸时刻 / 最冷时刻 / 反转次数，一眼看完整片节奏
- **数字钟体字体** — `tabular-nums` + 等宽 + slashed-zero，所有计数 / 时间码统一仪表读数风格
- **跨域联动声明** — 不再假装能反向控制 B 站 iframe；UI 明示「ECG = Remote Control」，鼠标拖动 ECG 即时驱动整套仪表

### 🔍 可交互研究工作区
- **点击心电图任意位置跳视频** — canvas 反算时间 → iframe `t` 参数 seek
- **悬停心电图驱动右侧仪表** — 8 维分量条 + 主导情绪标签 + 邻域弹幕 trail 实时更新
- **转折点卡片可折叠** — 前 3 条默认展开，点卡片展开/折叠，点时间跳视频
- **佐证弹幕自动采样** — 每个 TP 附带 3–5 条按关键词 > 长度 > 时间排序的代表弹幕
- **§05 弹幕全表搜索** — 按 8 个情绪维度过滤 + 关键词搜索，承担"翻全片找原话"职能

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
5. 把 working dir 重命名为 `AI情绪心电图-<视频关键字>/` 并放到桌面，文件夹内额外生成同名 `.html` 副本，双击即可打开

> 💡 **默认输出位置**：用户桌面（Windows: `%USERPROFILE%\Desktop`、macOS/Linux: `~/Desktop`），单一文件夹收纳所有产物。
> 如果你想改，告诉 Agent 「报告放在 `D:\reports\` 里」之类的明确路径即可。

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

## 📄 数据产物（桌面布局）

跑完后桌面会出现一个**单一文件夹**，里面装下所有中间产物 + 一份双击即开的友好命名 HTML：

```
<DESKTOP>/
└── AI情绪心电图-<视频关键字>/                     ← 单一文件夹整洁收纳
    ├── meta.json                                视频元信息（BV、时长、UP 主、弹幕总数）
    ├── danmaku.json                             全量历史弹幕（time / text / color / mode）
    ├── chunks.md                                分块的 Markdown，Agent 在这里打分
    ├── scores.json                              8 维 0–10 分打分结果（Agent 产出）
    ├── insights.json                            TL;DR + 3 条洞察（Agent 产出）
    ├── turnpoints.json                          合并后的转折点 + 佐证弹幕
    ├── emoekg_report.html                       原始名 HTML（断点续跑要用）
    └── AI情绪心电图-<视频关键字>.html             ★ 友好命名副本，双击打开
```

**关键字怎么来**？由 Agent 在 Step 6 从 `meta.title` 提取 4–14 字关键短语，去除装饰符号 / 标题党词 / Windows 非法字符。例：

- 「万字攻略 一口气玩会亡者世界！惊变末日搜打撤 网易必玩神作」 → `亡者世界万字攻略`
- 「【官方】《王者荣耀》新英雄 露娜技能解读 4K超清」 → `王者荣耀露娜技能解读`

> 💡 同名文件夹已存在时会加 `_2`/`_3` 后缀（如 `AI情绪心电图-亡者世界万字攻略_2/`），不会覆盖你上次跑出来的报告。

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

按 [Anthropic Agent Skills 范式](https://github.com/anthropics/courses/tree/master/tool_use) + Python [PyPA src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) 组织：

```
emoekg/
│
├── SKILL.md                          # ★ Agent 契约（工作流 + Stage 3 产出要求 + Step 6 桌面投放）
├── README.md                         # ★ 给用户看的（安装 + 演示 + 截图）
├── LICENSE                           # MIT
├── pyproject.toml                    # 安装配置 + 依赖声明 + CLI entry point（single source of truth）
├── .gitignore
│
├── docs/                             # 设计 + 历史
│   ├── scoring_rubric.md             #   Stage 3 打分细则（0–10 刻度、SPARSE、Insights Protocol）
│   ├── 2026-05-07-emoekg-design.md   #   原始设计 spec + §15 v0.4.x 实施回顾
│   ├── 2026-05-07-emoekg-plan.md     #   v0.1.0 实施计划
│   ├── CHANGELOG.md                  #   版本谱（浓缩版，每版一段）
│   ├── release-notes/                #   单版本长 release note（按 SemVer）
│   │   ├── README.md                 #     本目录索引 + CHANGELOG 关系说明
│   │   ├── v0.3.0.md
│   │   ├── v0.3.1.md
│   │   ├── v0.4.0.md
│   │   └── v0.4.1.md
│   └── superpowers/                  #   superpowers skill 留下的 specs/plans 历史
│       ├── plans/
│       └── specs/
│
├── demos/                            # 真实端到端示例（双击即开）
│   └── bv18acmz4ell/                 #   《万字攻略 一口气玩会亡者世界》
│       ├── meta.json                 #   221 弹幕 / 15:14 时长
│       ├── danmaku.json
│       ├── chunks.md
│       ├── scores.json
│       ├── insights.json
│       ├── turnpoints.json           #   7 个合并后转折点
│       └── emoekg_report.html        #   1.1 MB 单文件报告
│
├── src/                              # PyPA src layout —— 不能改名
│   └── emoekg/                       # Python 包根（== `pip install -e .` 装出来的导入名）
│       ├── __init__.py               #   __version__
│       ├── __main__.py               #   `python -m emoekg` 入口
│       ├── cli.py                    #   `emoekg {prepare, finalize, run}` 子命令分派
│       │
│       ├── _lib/                     #   纯函数业务层（无 IO 副作用，100% 可单测）
│       │   ├── bv_parser.py          #     URL / BV 号解析
│       │   ├── time_utils.py         #     HH:MM:SS 格式化
│       │   ├── adaptive_window.py    #     自适应窗口大小计算
│       │   ├── plutchik.py           #     8 维情绪 schema + 校验
│       │   ├── danmaku_client.py     #     bilibili-api 封装（重试 / 去重 / 色值归一化）
│       │   ├── turnpoint_algo.py     #     peaks + valleys + JS 散度 + cluster merge
│       │   └── evidence_picker.py    #     佐证弹幕采样排序
│       │
│       ├── stages/                   #   4 个 Python 阶段（S1/S2/S4/S5）
│       │   ├── fetch_danmaku.py      #     Stage 1: 拉 meta + 全量弹幕
│       │   ├── slice_chunks.py       #     Stage 2: 切片 + 渲染 prompt
│       │   ├── detect_turnpoints.py  #     Stage 4: 转折检测 + 合并 + 佐证
│       │   └── render_report.py      #     Stage 5: Jinja2 + 内联 ECharts
│       │
│       └── templates/
│           ├── report.html.j2        #   Cockpit Console 报告模板
│           ├── app.js                #   ECharts 交互 + Vital Readout + 视频联动
│           ├── chunks_prompt.md.j2   #   给 Agent 看的 chunks.md
│           └── vendor/
│               └── echarts.min.js    #   ECharts 5.5 UMD（离线内联）
│
└── tests/                            # 194 个单测，覆盖全链路
    ├── conftest.py
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

### 命名澄清

- **`src/` 不是缩写**——这是 [PyPA 推荐的 src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) 范式，目的是强制让测试通过 `pip install -e .` 注入的包路径导入，避免误读未安装的源码。`pyproject.toml` 的 `[tool.setuptools.packages.find]` 配置写死 `where = ["src"]`，**不能改名**。
- **`_lib/` 前置下划线**——表示模块私有，外部不应直接 `import emoekg._lib.xxx`，而是通过 `stages/` 层调用。
- **`docs/release-notes/` vs `docs/CHANGELOG.md`**——前者是单版本长说明（含动机 / 升级建议），后者是按版本浓缩的速查；详见 [`docs/release-notes/README.md`](docs/release-notes/README.md)。

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

## 📑 文件清单（每一个 tracked 文件，一个不漏）

仓库 git 追踪范围内共 **80 个文件**，按目录分组逐一说明。**未追踪**的运行时产物（`__pycache__/`、`*.egg-info/`、`build/`、`.pytest_cache/`、`emoekg_*_*/`、`AI情绪心电图-*/`、`*.mp4` 等）见 [`.gitignore`](.gitignore)，本清单不重复。

### 根目录（5 文件）

| 文件 | 用途 | 谁会读它 |
|---|---|---|
| [`.gitignore`](.gitignore) | Git 忽略规则（分类注释 + 防御性 `-p/`/`-r/` 入口） | git 自身 |
| [`LICENSE`](LICENSE) | MIT 开源协议正文 | GitHub / PyPI / `npx skills add` 自动识别 |
| [`pyproject.toml`](pyproject.toml) | PEP 517 包构建配置 + 依赖唯一来源 + CLI entry point | `pip install -e .` / `python -m build` |
| [`README.md`](README.md) | 主入口（安装 / 演示 / 命令 / 项目结构 / 本文件清单） | 终端用户 / GitHub 主页自动渲染 |
| [`SKILL.md`](SKILL.md) | **Agent 契约**（工作流 + Stage 3 打分规则 + Step 6 桌面投放规则） | AI Agent / `npx skills add` 装载入口 |

### `docs/` — 设计 + 历史档案（5 文件）

| 文件 | 用途 | 谁会读它 |
|---|---|---|
| [`docs/README.md`](docs/README.md) | **`docs/` 总入口**（meta-doc）—— 按"我想……"路径找文档 + 文档生命周期约定（active / frozen / archived） | 接手开发者第一次进 `docs/` 时 |
| [`docs/2026-05-07-emoekg-design.md`](docs/2026-05-07-emoekg-design.md) | v0.1.0 原始设计 spec + §15 v0.4.x Cockpit Console 实施回顾（D1–D12 决策） | 接手开发者 / 想了解决策来由的 |
| [`docs/2026-05-07-emoekg-plan.md`](docs/2026-05-07-emoekg-plan.md) | v0.1.0 完整实施计划（Task 1 → Task 15 拆分）— **HISTORICAL ARCHIVE** | 历史档案 |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | **浓缩版本谱**（v0.1.0 → current，每版一段） | 想快速了解迭代脉络的 |
| [`docs/scoring_rubric.md`](docs/scoring_rubric.md) | Stage 3 打分细则（0–10 刻度 / SPARSE 规则 / Insights Protocol） | **AI Agent 必读** |

### `docs/release-notes/` — 单版本长 release note（5 文件）

| 文件 | 用途 |
|---|---|
| [`docs/release-notes/README.md`](docs/release-notes/README.md) | 本目录索引 + 与 `CHANGELOG.md` 的边界说明 |
| [`docs/release-notes/v0.3.0.md`](docs/release-notes/v0.3.0.md) | `--with-video` 本地 mp4 模式 + Live Trace 脉冲 |
| [`docs/release-notes/v0.3.1.md`](docs/release-notes/v0.3.1.md) | yutto 集成 + 弹幕 client 三类 bug 回归 |
| [`docs/release-notes/v0.4.0.md`](docs/release-notes/v0.4.0.md) | Cockpit Console 首版（弹幕侧栏 → vital readout 转型） |
| [`docs/release-notes/v0.4.1.md`](docs/release-notes/v0.4.1.md) | iframe 跨域同步现实化（best-effort postMessage） |

### `docs/superpowers/` — superpowers skill 留下的设计/计划遗产（3 文件）

| 文件 | 用途 |
|---|---|
| [`docs/superpowers/README.md`](docs/superpowers/README.md) | **本目录性质说明**——v0.4.0 之前「弹幕侧栏」方案的归档，标明已被 v0.4.2 Cockpit Console 取代 |
| [`docs/superpowers/specs/2026-05-09-danmaku-sidebar-design.md`](docs/superpowers/specs/2026-05-09-danmaku-sidebar-design.md) | v0.4.0 之前的弹幕侧栏 spec（已被 v0.4.x Cockpit 取代，作为 retro 保留） |
| [`docs/superpowers/plans/2026-05-11-v0.4.0-danmaku-panel.md`](docs/superpowers/plans/2026-05-11-v0.4.0-danmaku-panel.md) | v0.4.0 弹幕面板实施计划 |

### `demos/` — 真实端到端样例（4 BV × 7 文件 = 28 文件）

每个 `demos/<bvid>/` 子目录都是一次完整跑通的结果，**7 个文件命名严格统一**（与 SKILL Step 6 桌面输出同构）：

| 文件名 | 用途 |
|---|---|
| `meta.json` | Stage 1 输出：BV / 时长 / UP / 弹幕总数 |
| `danmaku.json` | Stage 1 输出：全量历史弹幕（time / text / color / mode） |
| `chunks.md` | Stage 2 输出：分块的 Markdown，Agent 在这里读着打分 |
| `scores.json` | Stage 3 输出：8 维 0–10 分（Agent 产出） |
| `insights.json` | Stage 3 输出：30–80 字 TL;DR + 3 条洞察（Agent 产出） |
| `turnpoints.json` | Stage 4 输出：合并后的转折点 + 佐证弹幕 |
| `emoekg_report.html` | Stage 5 输出：单文件离线交互报告（~1 MB） |

4 个 BV 子目录（共 28 个文件 = 4 × 上述 7 个）：

| 子目录 | 视频标题 | 说明 |
|---|---|---|
| [`demos/bv18acmz4ell/`](demos/bv18acmz4ell/) | 《万字攻略 一口气玩会亡者世界！惊变末日搜打撤 网易必玩神作》 | 15:14 / 221 弹幕 / 7 转折点（v0.1.1 首发 demo，文档主示例） |
| [`demos/bv1arcxz5epf/`](demos/bv1arcxz5epf/) | 《可以当作春晚看的超长钩式 MC 视频》 | 长视频场景验证（自适应窗口 → 60s 切片） |
| [`demos/bv1xcosbxenz/`](demos/bv1xcosbxenz/) | 《你真玩懂我的世界了吗？》 | v0.4.x Cockpit Console 验证样例 |
| [`demos/bv161owbueb3/`](demos/bv161owbueb3/) | 《洛克王国一定要出这个模式啊，我要爽玩！》 | 用户场景验收样例（情感反转密集） |

### `src/emoekg/` — Python 包顶层（3 文件）

| 文件 | 用途 |
|---|---|
| [`src/emoekg/__init__.py`](src/emoekg/__init__.py) | 包根，定义 `__version__`（current = 0.4.12） |
| [`src/emoekg/__main__.py`](src/emoekg/__main__.py) | `python -m emoekg ...` 入口（dispatch 到 `cli.main`） |
| [`src/emoekg/cli.py`](src/emoekg/cli.py) | `emoekg {prepare, finalize, run}` 子命令分派 + 参数解析 + 进度日志 |

### `src/emoekg/_lib/` — 纯函数业务层（8 文件，无 IO 副作用）

| 文件 | 用途 |
|---|---|
| [`src/emoekg/_lib/__init__.py`](src/emoekg/_lib/__init__.py) | 包初始化 |
| [`src/emoekg/_lib/bv_parser.py`](src/emoekg/_lib/bv_parser.py) | URL → BV 号解析；BV ↔ AV 号互转 |
| [`src/emoekg/_lib/time_utils.py`](src/emoekg/_lib/time_utils.py) | 秒数 ↔ `HH:MM:SS` / `MM:SS` 格式化与解析 |
| [`src/emoekg/_lib/adaptive_window.py`](src/emoekg/_lib/adaptive_window.py) | 根据视频时长自适应选 15s/30s/60s 切片窗口（目标 ~90 chunks） |
| [`src/emoekg/_lib/plutchik.py`](src/emoekg/_lib/plutchik.py) | Plutchik 8 维情绪 schema 常量 + `validate_score_entry` 校验 |
| [`src/emoekg/_lib/danmaku_client.py`](src/emoekg/_lib/danmaku_client.py) | bilibili-api 封装：分段 Protobuf 拼接 + 重试 + 去重 + 色值归一化 |
| [`src/emoekg/_lib/turnpoint_algo.py`](src/emoekg/_lib/turnpoint_algo.py) | scipy `find_peaks` 峰值检测 + Jensen-Shannon 散度反转检测 + 时间簇合并 |
| [`src/emoekg/_lib/evidence_picker.py`](src/emoekg/_lib/evidence_picker.py) | 转折点佐证弹幕采样排序（关键词 > 长度 > 时间） |

### `src/emoekg/stages/` — Python 流水线 4 阶段（5 文件）

| 文件 | 用途 |
|---|---|
| [`src/emoekg/stages/__init__.py`](src/emoekg/stages/__init__.py) | 包初始化 |
| [`src/emoekg/stages/fetch_danmaku.py`](src/emoekg/stages/fetch_danmaku.py) | **Stage 1**：拉视频 meta + 全量历史弹幕 → `meta.json` + `danmaku.json` |
| [`src/emoekg/stages/slice_chunks.py`](src/emoekg/stages/slice_chunks.py) | **Stage 2**：自适应切片 + 渲染 Agent prompt → `chunks.md` + 空 `scores.json` |
| [`src/emoekg/stages/detect_turnpoints.py`](src/emoekg/stages/detect_turnpoints.py) | **Stage 4**：峰值 + 散度 + cluster merge + 佐证采样 → `turnpoints.json` |
| [`src/emoekg/stages/render_report.py`](src/emoekg/stages/render_report.py) | **Stage 5**：Jinja2 渲染 + 内联 ECharts + 内联 `app.js` → `emoekg_report.html` |

> **Stage 3（打分）没有对应的 Python 文件**——它由 AI Agent 在对话里直接做，是 emoekg 的设计核心，参见 `SKILL.md` 与 `docs/scoring_rubric.md`。

### `src/emoekg/templates/` — HTML 模板 + 前端逻辑 + 第三方资源（5 文件）

| 文件 | 用途 |
|---|---|
| [`src/emoekg/templates/__init__.py`](src/emoekg/templates/__init__.py) | 让 `templates/` 成为可被 `setuptools.package_data` 打包的目录 |
| [`src/emoekg/templates/report.html.j2`](src/emoekg/templates/report.html.j2) | 报告主模板：Cockpit Console 布局 + CSS 变量 + 8 模块组件骨架 |
| [`src/emoekg/templates/app.js`](src/emoekg/templates/app.js) | ECharts 渲染 + Vital Readout + 视频联动 + ResizeObserver 高度同步 |
| [`src/emoekg/templates/chunks_prompt.md.j2`](src/emoekg/templates/chunks_prompt.md.j2) | 给 Agent 看的 `chunks.md` 模板（Stage 2 渲染用） |
| [`src/emoekg/templates/vendor/echarts.min.js`](src/emoekg/templates/vendor/echarts.min.js) | ECharts 5.5 UMD bundle（~1 MB，**离线内联**，单文件 HTML 的关键依赖） |

### `tests/` — pytest 单测套件（15 文件，194 test cases）

| 文件 | 测试目标 | case 数 |
|---|---|---|
| [`tests/__init__.py`](tests/__init__.py) | 包初始化 | — |
| [`tests/conftest.py`](tests/conftest.py) | pytest fixtures 共享（mock 数据 / 临时目录） | — |
| [`tests/test_smoke.py`](tests/test_smoke.py) | import 烟测：所有模块能加载 | 2 |
| [`tests/test_bv_parser.py`](tests/test_bv_parser.py) | `_lib.bv_parser` BV 号解析 | 20 |
| [`tests/test_time_utils.py`](tests/test_time_utils.py) | `_lib.time_utils` 时间格式化 | 25 |
| [`tests/test_adaptive_window.py`](tests/test_adaptive_window.py) | `_lib.adaptive_window` 窗口选择 | 19 |
| [`tests/test_plutchik.py`](tests/test_plutchik.py) | `_lib.plutchik` schema 校验 | 23 |
| [`tests/test_danmaku_client.py`](tests/test_danmaku_client.py) | `_lib.danmaku_client`（含 3 类历史 bug 回归） | 21 |
| [`tests/test_evidence_picker.py`](tests/test_evidence_picker.py) | `_lib.evidence_picker` 佐证采样排序 | 10 |
| [`tests/test_turnpoint_algo.py`](tests/test_turnpoint_algo.py) | `_lib.turnpoint_algo` 峰值/散度/合并 | 16 |
| [`tests/test_stage1_fetch.py`](tests/test_stage1_fetch.py) | Stage 1 集成 | 6 |
| [`tests/test_stage2_slice.py`](tests/test_stage2_slice.py) | Stage 2 集成 | 9 |
| [`tests/test_stage4_detect.py`](tests/test_stage4_detect.py) | Stage 4 集成 | 9 |
| [`tests/test_stage5_render.py`](tests/test_stage5_render.py) | Stage 5 集成（断言 Cockpit 关键 DOM 字符串存在） | 15 |
| [`tests/test_cli.py`](tests/test_cli.py) | CLI 子命令端到端 | 19 |

### 合计

```
根目录             5
docs/              5
docs/release-notes/ 5
docs/superpowers/  3
demos/            28  (= 4 BV × 7 文件)
src/emoekg/        3
src/emoekg/_lib/   8
src/emoekg/stages/ 5
src/emoekg/templates/ 5
tests/            15
─────────────────────
合计              82   ✓ 与 `git ls-files | wc -l` 一致
```

---

## 🎨 报告设计语言

- **主题**：Swiss × Editorial 暗色研究档案 → v0.4.x 升级为 **Cockpit Console 监护仪式**
- **字体**：纯系统字体栈（Inter 族 + IBM Plex 族降级 + `ui-monospace` 数字仪表），零 CDN 依赖
- **数字字符**：`font-variant-numeric: tabular-nums slashed-zero`，确保 0 与 O 可辨、列宽对齐
- **调色板**：11 阶中性灰 `#0a0a0b → #f4f4f6` + 单一强调色 `#EB5E28`（Accent Orange）
- **版式**：12 列网格 + 显式 `grid-template-rows` 锁定基线，宽屏 / 窄屏均横向对齐
- **图表**：ECharts 5.5，自定义磷光发光（shadowBlur 2 / emphasis 8），hover 聚焦单一维度
- **动效**：Live Trace 呼吸圆点（1.6s 三段 keyframes）+ hint 箭头脉冲（`hint-pulse`）

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
# 194 tests pass
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

| 版本 | 主题 | 状态 |
|---|---|---|
| **v0.1.0** | 核心流水线 + CLI + SKILL 契约 | ✅ 已发布 |
| **v0.1.1** | Swiss × Editorial UI + Insights Protocol + 真实数据验证 | ✅ 已发布 |
| **v0.2.x** | `--with-video` 本地视频模式 + iframe 双向同步尝试 | ✅ 已发布 |
| **v0.3.x** | Vital Console 第一版 + 弹幕侧栏 + 8 维仪表读数 | ✅ 已发布 |
| **v0.4.x** | Cockpit Console 重构（`vital-stats-grid` / `headline.mono` / hint-pulse / 基线锁定） + 桌面默认输出 + 单一文件夹友好命名 + 仓库结构标准化 + 逐文件清单 + 开发文档系统化 | ✅ 已发布（current = 0.4.14）|
| v0.5.0 | 多视频对比（同一 UP / 同系列横向对照仪表盘） | 计划中 |
| v0.5.0 | 导出情绪摘要 CSV / Markdown 表格，便于研究报告复用 | 计划中 |
| v0.6.0 | 抖音 / YouTube 数据源适配（保持同 SKILL 接口） | 探索中 |
| v0.6.0 | 直播实时模式（边播边打分） | 探索中 |

详细版本变更历史见 [`docs/CHANGELOG.md`](docs/CHANGELOG.md)。

---

## 📄 License

MIT © 2026 [2811jh](https://github.com/2811jh)
