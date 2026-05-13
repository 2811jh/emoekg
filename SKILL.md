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

**Step 1 — 确认输入 + 解析输出位置**

向用户确认：
- B 站视频 URL / BV 号（必需）
- 是否需要 `--with-video` 模式（可选，需本地 MP4，触发时告诉用户要先用 `yutto` 或其他工具下载视频到 `video.mp4`）
- **输出位置**（重要）：
  - **默认 = 用户桌面**（Windows: `%USERPROFILE%\Desktop`、macOS/Linux: `~/Desktop`）
  - 仅当用户**显式指定** `-o`、`--output`、"放到 xxx 目录"、"输出到 yyy/" 等表达时，才用用户给的路径
  - 用户没说时不要追问"放哪里"——默认桌面即可，省掉一轮交互

**Step 2 — 准备数据**

```bash
# 默认（推荐）：放桌面，working dir 命名 emoekg_<BV>_<YYYYMMDD>
emoekg prepare <url_or_bvid> -o <DESKTOP>/emoekg_<BV>_<YYYYMMDD>/

# Windows 实例
emoekg prepare BV18acMz4ELL -o %USERPROFILE%/Desktop/emoekg_BV18acMz4ELL_20260513/

# macOS / Linux 实例
emoekg prepare BV18acMz4ELL -o ~/Desktop/emoekg_BV18acMz4ELL_20260513/
```

CLI 会：
- 在 `<working_dir>/` 下生成 `meta.json` + `danmaku.json`
- 切片成 ~90 个 chunk，生成 `chunks.md`（给你看的 prompt）
- 写入空骨架 `scores.json`（`[]`）

完成后 CLI 会提示 `Waiting for Agent scoring`。

> **注意 — 文件名约定的两层含义**：
> - `working dir` 仍叫 `emoekg_<BV>_<YYYYMMDD>/` ——保持目录可识别 + 多次跑同视频不冲突
> - 最终交付给用户的 HTML **会另存一份友好名**，见 Step 6

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
emoekg finalize -o <DESKTOP>/emoekg_<BV>_<YYYYMMDD>/
```

或者如果用户要本地视频双向同步：

```bash
emoekg finalize -o <DESKTOP>/emoekg_<BV>_<YYYYMMDD>/ --with-video
```

产出 `<working_dir>/emoekg_report.html`（~1 MB，自带 ECharts，可完全离线打开）。

**Step 5 — 质量自检**

交付前确认：
- [ ] `scores.json` 长度 == chunks 数
- [ ] `insights.json` 有 `summary`（30–80 字）+ 恰好 3 条 `insights`（每条 `title` + `body`）
- [ ] 三条 insight 覆盖节奏 / 机制 / 反差三种视角，不是同一件事换三种说法
- [ ] `turnpoints.json` 至少有 3 条（典型 30 分钟视频应该有 5–15 条）
- [ ] HTML 打开后图表非空、至少能看到一条情绪曲线
- [ ] HTML Hero 区 TL;DR 和 Insights 能正常显示
- [ ] 非 SPARSE chunk 不要全 0（警示线：见 S4 `WARN` 输出）
- [ ] **Step 6 已执行**：桌面有 `AI情绪心电图-<关键字>/` 文件夹，文件夹里同时有 `emoekg_report.html`（原始）+ `AI情绪心电图-<关键字>.html`（友好名副本）
- [ ] **告知用户的路径**是桌面那个文件夹和文件夹内的友好名 HTML，不要再提 `emoekg_<BV>_<日期>` 临时目录或 `emoekg_report.html` 原始名

**Step 6 — 文件夹改名 + 友好 HTML 副本（必做，v0.4.9+）**

CLI 跑完后，working dir 名是 `emoekg_<BV>_<日期>`，HTML 名是 `emoekg_report.html`——对终端用户都不友好。**你必须把整个 working dir 改名为 `AI情绪心电图-<视频关键字>`，并在文件夹内额外放一份同名 HTML 副本**。

```
<DESKTOP>/AI情绪心电图-<视频关键字>/
├── meta.json
├── danmaku.json
├── chunks.md
├── scores.json
├── insights.json
├── turnpoints.json
├── emoekg_report.html              ← CLI 原始产出（保留，断点续跑要用）
├── (可选) video.mp4
└── AI情绪心电图-<视频关键字>.html    ← 友好命名副本，让用户双击的就是这个
```

**关键字提取规则**：
1. 从 `<working_dir>/meta.json` 的 `title` 字段读视频标题
2. 去掉装饰性符号：`【】《》「」()[]『』""''!?！？` 全角半角都去
3. 去掉广告 / 标题党词：`最新`、`必看`、`重磅`、`官方`、`独家`、`完整版`、`超清`、`高清`、`4K` 等
4. 提取 4–14 个汉字 / 数字 / 字母的核心短语，删除空格和分隔符
5. 总文件夹/文件名长度 ≤ 60 字符（含 `AI情绪心电图-` 前缀和 `.html` 后缀）；过长则截断到尾部
6. 替换 Windows 非法字符 `< > : " / \ | ? *` 为空字符串

**示例**：

| `meta.title` | 关键字 | 桌面文件夹 / 内含友好 HTML |
|---|---|---|
| 「躁动的地平线 RLcraft现代版本 MC生存试玩」 | `RLcraft现代MC试玩` | `AI情绪心电图-RLcraft现代MC试玩/` + 同名 `.html` |
| 「万字攻略 一口气玩会亡者世界！惊变末日搜打撤 网易必玩神作」 | `亡者世界万字攻略` | `AI情绪心电图-亡者世界万字攻略/` + 同名 `.html` |
| 「【官方】《王者荣耀》新英雄 露娜技能解读 4K超清」 | `王者荣耀露娜技能解读` | `AI情绪心电图-王者荣耀露娜技能解读/` + 同名 `.html` |

**操作方式**（**强烈推荐 Python 单行**——跨平台、避中文编码坑、改名+复制原子完成）：

```bash
python -c "import shutil, pathlib, os; src=pathlib.Path(r'<working_dir>'); name='AI情绪心电图-<关键字>'; dst=pathlib.Path(os.path.expanduser('~/Desktop'))/name; n=2; orig=dst; \
  exec('while dst.exists():\n    dst = orig.with_name(orig.name + f\"_{n}\"); n += 1'); \
  shutil.move(str(src), str(dst)); shutil.copy2(dst/'emoekg_report.html', dst/(name+'.html')); print(dst)"
```

或分两步更直观：

```bash
# Windows cmd
move "<DESKTOP>\emoekg_<BV>_<日期>" "<DESKTOP>\AI情绪心电图-<关键字>"
copy "<DESKTOP>\AI情绪心电图-<关键字>\emoekg_report.html" "<DESKTOP>\AI情绪心电图-<关键字>\AI情绪心电图-<关键字>.html"

# macOS / Linux
mv "$HOME/Desktop/emoekg_<BV>_<日期>" "$HOME/Desktop/AI情绪心电图-<关键字>"
cp "$HOME/Desktop/AI情绪心电图-<关键字>/emoekg_report.html" "$HOME/Desktop/AI情绪心电图-<关键字>/AI情绪心电图-<关键字>.html"
```

**重名处理**：桌面已存在同名文件夹时，新文件夹追加 `_2`、`_3` 后缀（例如 `AI情绪心电图-亡者世界万字攻略_2/`），**不要覆盖**用户上次跑出来的报告。

**最终告知用户**时，给出**文件夹路径**和**文件夹内 HTML 路径**两条信息，让用户清楚双击哪个文件即可：

> 报告已生成：
> 📁 文件夹：`C:\Users\xxx\Desktop\AI情绪心电图-亡者世界万字攻略\`
> 🖱️ 双击打开：`C:\Users\xxx\Desktop\AI情绪心电图-亡者世界万字攻略\AI情绪心电图-亡者世界万字攻略.html`

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

### 输出位置 & 命名规范（v0.4.9+）

| 阶段 | 路径 | 名称 | 说明 |
|---|---|---|---|
| **Step 2 临时 working dir** | `<DESKTOP>/emoekg_<BV>_<YYYYMMDD>/` | `emoekg_<BV号>_<日期>` | CLI 不知道视频标题，先用 BV 号占位 |
| **Step 6 改名后最终目录** | `<DESKTOP>/AI情绪心电图-<视频关键字>/` | `AI情绪心电图-<关键字>` | 拿到 `meta.json` 后整个目录 rename |
| **目录内友好 HTML** | `<DESKTOP>/AI情绪心电图-<关键字>/AI情绪心电图-<关键字>.html` | 同名 `.html` 副本 | 用户双击的就是这个 |

**判断"用户是否指定了输出位置"**：
- 触发用户指定模式的表达：`-o`、`--output`、`放到 X`、`输出到 X`、`存到 X`、`保存到 X`、`报告放 X`
- 没说就**默认桌面**——不要追问；按 Step 1–6 流程跑

### 输出目录结构

**Step 2–4 进行中（临时占位名）**：

```
<DESKTOP>/
└── emoekg_BV1xxxxxx_20260513/      # CLI 跑流水线时的 working dir
    ├── meta.json                   #   S1 输出
    ├── danmaku.json                #   S1 输出（可能 1–50 MB）
    ├── chunks.md                   #   S2 输出 — Agent prompt
    ├── scores.json                 #   S3 你填（8 维分 + note）
    ├── insights.json               #   S3 你写（summary + 3 insights）
    ├── turnpoints.json             #   S4 输出
    ├── emoekg_report.html          #   S5 输出（原始名）
    └── (可选) video.mp4             #   --with-video 模式用
```

**Step 6 完成后（最终交付给用户的样子）**：

```
<DESKTOP>/
└── AI情绪心电图-亡者世界万字攻略/                 # 整个目录被改名
    ├── meta.json
    ├── danmaku.json
    ├── chunks.md
    ├── scores.json
    ├── insights.json
    ├── turnpoints.json
    ├── emoekg_report.html                       # 原始名保留（断点续跑要用）
    ├── (可选) video.mp4
    └── AI情绪心电图-亡者世界万字攻略.html         # ★ 友好命名副本，双击打开
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
| **追问"放哪里？"** | 不要。默认桌面；除非用户说 `-o XXX` 之类显式路径 |
| **跳过 Step 6 直接交付临时目录路径** | `emoekg_<BV>_<日期>` 终端用户看不懂；必须改名为 `AI情绪心电图-<关键字>` 并放一份同名 HTML 副本进去 |
| **只复制 HTML 不改文件夹名** | 桌面会同时存在临时目录 + 散落的 HTML，看起来很乱；要的是一个文件夹装下所有产物 |
| **把视频原标题直接当文件名/夹名** | 标题里有 `《》【】！？` 之类符号，Windows 写不进；按 Step 6 关键字提取规则做净化 |
| **覆盖用户上次跑出来的报告** | 桌面同名文件夹已存在时加 `_2`/`_3`，不要 overwrite 整个目录 |

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
- `tests/` — 194 个单测（`pytest` 跑通）
- `pyproject.toml` — 安装配置 + 依赖声明（single source of truth，无 `requirements.txt`）

## Installation

```bash
pip install -e .
```

可选：`pip install -e ".[video]"` 安装 `yutto` 支持 `--with-video` 本地视频下载。
