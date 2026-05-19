# emoekg · Design Spec

> **Status**: Approved (2026-05-07)
> **Owner**: lijinghui03
> **Scope**: emoekg skill v0.1.0 的完整设计与交付物标准（github 推送动作不在本 spec 范围，交 `github-ops` skill 执行）
> **Target users**: UX 研究员、内容运营、游戏策划

---

## 1. 产品定义

### 1.1 一句话

把一晚上几万条弹幕的混沌声音，压缩成一张**可读、可查、可对比**的情绪心电图，让 UX 研究员快速回答："这个视频哪里最炸、哪里最冷、谁在骂、因为什么。"

### 1.2 核心场景

- "上线 24 小时，主播直播播了 3 小时，中间有一段突然很多退游评论，我要找到那一刻。"
- "分析一下视频，看看玩家的情绪心电图，链接如下 xxx"

### 1.3 硬性需求

| # | 需求 | 可量化验收 |
|---|---|---|
| 1 | 给一个 B 站视频链接 → 输出情绪时间线 | 输入 URL 后 5 分钟内得到 HTML |
| 2 | 情绪至少区分 4 种基本类型 | 采用 Plutchik 8 维（joy / trust / fear / surprise / sadness / disgust / anger / anticipation） |
| 3 | 情绪高峰能点进去看具体弹幕（不是黑箱） | 每个转折点 ≥ 5 条原话佐证 |
| 4 | 工具可重复跑 | 幂等：同 BV 重复跑命中缓存；`--force` 强制覆盖 |
| 5 | 只支持 B 站（其他平台后续扩展） | v0.1.0 只实现 B 站 |

### 1.4 非目标（YAGNI）

- ❌ 情绪打分做成实时直播模式（v0.2+）
- ❌ 支持抖音/YouTube/Twitch（v0.3+）
- ❌ 内置 LLM API 调用（本 skill 明确走 Agent 驱动路线）
- ❌ 多视频批量对比模式（先单视频跑稳再说）

---

## 2. 核心决策汇总（5 个关键决策 + 视频嵌入 1 个）

| # | 决策 | 结果 | 理由 |
|---|---|---|---|
| D1 | 情绪打分执行方 | CodeMaker Agent 在对话中打分，脚本零 LLM 调用 | 和 `interview-research`、`game-mechanic-analyzer` 一致；下游用户零 API Key |
| D2 | 弹幕抓取策略 | `bilibili-api-python` 免登录拉 Protobuf 分段接口，拿**全量**弹幕 | UX 研究场景要求数据完整性 |
| D3 | 产出形式 | 单文件 HTML（ECharts 8 维心电图 + 转折点 + 佐证弹幕） | 便于分享、邮件、归档 |
| D4 | 转折点识别 | 双算法：峰值检测 + 滑动窗口 JS 散度对比 | 兼顾"最炸/最冷"与"情绪骤转"两种语义 |
| D5 | 切片粒度 | 自适应，目标 60–120 数据点 | 权衡心电图分辨率与 Agent 打分 token 成本 |
| D6 | 视频嵌入方式 | **混合模式**：默认 iframe（零依赖），`--with-video` 升级本地 mp4（完整双向联动） | 覆盖"日常查看"和"归档分析"两种场景 |

---

## 3. 整体架构

### 3.1 Pipeline

```
用户对话：「分析一下 https://bilibili.com/video/BVxxx」
                    ↓
           Agent 识别触发 emoekg skill
                    ↓
┌────────────────────────────────────────────────────┐
│  Stage 1 (Python)  fetch_danmaku.py                │
│    BV URL → meta.json + danmaku.json               │
├────────────────────────────────────────────────────┤
│  Stage 2 (Python)  slice_chunks.py                 │
│    danmaku.json → chunks.md + scores.json骨架       │
├────────────────────────────────────────────────────┤
│  Stage 3 (Agent)   打分                            │
│    chunks.md → scores.json                         │
├────────────────────────────────────────────────────┤
│  Stage 4 (Python)  detect_turnpoints.py            │
│    scores.json + danmaku.json → turnpoints.json    │
├────────────────────────────────────────────────────┤
│  Stage 5 (Python)  render_report.py                │
│    所有 JSON → emoekg_report.html                  │
└────────────────────────────────────────────────────┘
                    ↓
     Agent 告诉用户：报告生成在 [工作目录]
```

### 3.2 分工原则

| 执行者 | 职责 | 绝对不做 |
|---|---|---|
| Python 脚本 | 弹幕抓取、数据 I/O、切片、统计算法、模板渲染 | ❌ 不调 LLM、不做语义判断、不打情绪分 |
| CodeMaker Agent | 读 `chunks.md` 做语义判断、按 rubric 打 8 维分、写 `scores.json` | ❌ 不抓弹幕、不算数学、不碰 `danmaku.json` 原始数据 |

> 注：Agent 读的是 `chunks.md`（Stage 2 产出的结构化上下文），不是 `danmaku.json`（原始数据）。这是刻意的信息隐藏 —— 让 Agent 专注语义，让脚本专注 I/O。

### 3.3 幂等性 & 断点续跑

每个 Stage 开头检查对应产物是否存在且 schema 校验通过：
- 通过 → `[SKIP] Stage X already done`
- 不通过 → 从头执行该 Stage
- 加 `--force` → 忽略缓存强制重跑
- 加 `--from-stage N` → 从指定 Stage 开始跑

Stage 3（Agent 打分）特殊处理：每批 10 个 chunk 打分完立即 append 到 `scores.json`，中途失败可从最后一个已打分 chunk 续跑。

---

## 4. 文件 / 目录结构

### 4.1 Skill 仓库结构（GitHub repo）

```
emoekg/
├── SKILL.md                         # 给 Agent 看的主文档
├── README.md                        # 给用户看的（安装 + 演示 + 截图）
├── LICENSE                          # MIT
├── requirements.txt                 # bilibili-api-python, jinja2, numpy, scipy
├── pyproject.toml                   # 版本号、CLI entry point
├── CHANGELOG.md                     # 每版本变更记录
├── .gitignore
│
├── scripts/
│   ├── fetch_danmaku.py            # Stage 1
│   ├── slice_chunks.py             # Stage 2
│   ├── detect_turnpoints.py        # Stage 4
│   ├── render_report.py            # Stage 5
│   ├── download_video.py           # --with-video 时用到（yutto 封装）
│   └── _lib/
│       ├── __init__.py
│       ├── bv_parser.py            # URL → BV 号
│       ├── danmaku_client.py       # bilibili-api 封装
│       ├── adaptive_window.py      # 自适应切片算法
│       ├── plutchik.py             # 8 维情绪 schema + 颜色 + 关键词表
│       ├── turnpoint_algo.py       # 峰值检测 + JS 散度
│       ├── evidence_picker.py      # 转折点佐证弹幕选取
│       └── time_utils.py           # 秒 ↔ 00:12:34 + progress(ms) 归一化
│
├── templates/
│   ├── report.html.j2              # 主 HTML 模板（含 ECharts 内联）
│   ├── chunks_prompt.md.j2         # Stage 2 产出 chunks.md 模板
│   └── scoring_rubric.md           # 8 维打分细则（内嵌到 SKILL.md，但单独文件便于维护）
│
├── examples/
│   ├── BV18acMz4ELL_report.html    # 跑测示例报告
│   ├── screenshot.png              # README 封面
│   └── README.md                   # 示例说明
│
└── docs/
    ├── 2026-05-07-emoekg-design.md  # 本文件
    └── architecture.png             # 架构图（后续补）
```

### 4.2 用户运行时的工作目录

默认位置：`C:\Users\{user}\Desktop\emoekg_{BV}_{YYYYMMDD}\`

```
Desktop/emoekg_BV18acMz4ELL_20260507/
│
├── meta.json                # 视频元信息（标题/UP主/时长/BV/cid/播放量/弹幕总数/生成时间）
├── danmaku.json             # Stage 1：全量原始弹幕
│                            #   [{time: 12.3, text: "666", user_hash, color, size, mode, ...}]
├── chunks.md                # Stage 2：喂给 Agent 看的上下文
├── scores.json              # Stage 3：Agent 打完分后写入
├── turnpoints.json          # Stage 4：转折点 + 佐证弹幕
├── emoekg_report.html       # Stage 5：最终交互报告
├── video.mp4                # --with-video 时有
└── .cache/
    └── stage_status.json    # 断点缓存
```

### 4.3 Stage I/O 契约

| Stage | 脚本 | 输入 | 输出 | 失败处理 |
|---|---|---|---|---|
| 1 | `fetch_danmaku.py` | BV URL | `meta.json`、`danmaku.json` | 网络重试 3 次；仍失败 → 报错返回给 Agent |
| 2 | `slice_chunks.py` | `danmaku.json` | `chunks.md`、空 `scores.json` 骨架 | 纯本地，不会失败 |
| 3 | Agent 批量打分 | `chunks.md` | 填充 `scores.json` | 每 10 chunk 写盘，中断可续 |
| 4 | `detect_turnpoints.py` | `scores.json`、`danmaku.json` | `turnpoints.json` | 校验 scores 完整性失败 → 报告哪些 chunk 缺 |
| 5 | `render_report.py` | 以上所有 JSON | `emoekg_report.html` | 模板渲染错误定位具体模板行 |

---

## 5. Plutchik 8 维情绪评分 Rubric

### 5.1 维度定义表

| 维度 | 英文 | 颜色（ECharts） | B 站弹幕典型表达 |
|---|---|---|---|
| 喜悦 | joy | `#F4D03F` 金黄 | 233 / 哈哈哈 / 笑死 / 好活 / 太乐了 / 笑不活 |
| 信任 | trust | `#52BE80` 草绿 | 稳了 / 相信主播 / 专业 / yyds / 可以信 |
| 恐惧 | fear | `#566573` 深灰 | 害怕 / 瑟瑟发抖 / 完蛋了 / 要出事 / 慌 |
| 惊讶 | surprise | `#F39C12` 橙 | 卧槽 / 啊这 / ??? / 离谱 / 什么情况 / 震惊 |
| 悲伤 | sadness | `#5499C7` 蓝 | 破防 / 难过 / emo / 泪目 / 心疼 / 哭了 |
| 厌恶 | disgust | `#8E44AD` 紫 | 恶心 / 作呕 / 下头 / 恶臭 / 辣眼睛 |
| 愤怒 | anger | `#C0392B` 红 | 退游 / 策划死妈 / 气死 / 滚 / 辣鸡 / 垃圾 |
| 期待 | anticipation | `#EB984E` 珊瑚 | 我等你 / 快更新 / 下一集 / 蹲 / 求出 |

**关键词表**仅作为 Stage 4 选佐证弹幕时的辅助工具，**不用于 Stage 3 打分**（Agent 打分要看完整语义，不能机械匹配）。

### 5.2 0–10 打分标尺

| 分值 | 含义 | 以 joy 为例 |
|---|---|---|
| 0 | 完全不存在 | 一条都没有 |
| 1–2 | 微弱背景 | 偶尔一两个 "哈" |
| 3–4 | 一定比例（20-40%） | 夹杂 "233"、"乐" |
| 5–6 | 明显主导（40-60%） | "哈哈哈" 刷屏 |
| 7–8 | 强烈集中（60-80%） | 几乎满屏笑点 |
| 9–10 | 极端爆发（>80% + 高密度） | 窗口被 "哈哈哈哈哈哈" 淹没 |

**8 个维度互不相斥**：一个窗口可以同时 joy=7 + surprise=6（如"卧槽笑死了"）。

### 5.3 特殊 chunk 处理

- **SPARSE**（n < 3）：Agent 全维度打 0，`note: "sparse"`。心电图上用半透明虚线/底色灰条标识。
- **DENSE**（n > 150）：`chunks.md` 里采样展示（开头 30 + 结尾 30 + 中间随机 90），但 Stage 4 选佐证弹幕时从 `danmaku.json` 取全量。

---

## 6. Agent 打分协议

### 6.1 Stage 2 产出 `chunks.md` 格式

```markdown
# Danmaku Chunks for BV18acMz4ELL
Video: 《某视频标题》| UP: 某某 | Duration: 18:42 | Total: 8,432 弹幕
Window size: 15s | Total chunks: 75

## [C001] 00:00:00 – 00:00:15 (n=42)
- 00:00:02 开场
- 00:00:03 终于来了
- 00:00:03 蹲
...

## [C002] 00:00:15 – 00:00:30 (n=18)
...

## [C034] 00:08:30 – 00:08:45 (n=2, SPARSE)
- 00:08:32 ...
- 00:08:41 ...
```

### 6.2 Agent 打分输出格式（严格 schema）

```json
[
  {
    "chunk_id": "C001",
    "time_start": 0,
    "time_end": 15,
    "n_danmaku": 42,
    "joy": 7,
    "trust": 2,
    "fear": 0,
    "surprise": 4,
    "sadness": 0,
    "disgust": 0,
    "anger": 0,
    "anticipation": 8,
    "note": "开场期待+欢乐情绪主导，少量玩家惊讶"
  }
]
```

### 6.3 Agent 工作流（写入 SKILL.md）

```
1. 读 {working_dir}/chunks.md
2. 从 C001 开始，每 10 个 chunk 为一批
3. 对每批：
   a. 逐 chunk 分析弹幕语义
   b. 按 Rubric 打 8 维分
   c. 给一句 note 说明主要情绪判断
4. 每批打完立即 append 到 {working_dir}/scores.json
5. 全部打完后，报告总 chunks 数、耗时
```

### 6.4 质量自检（Stage 4 开头执行）

- 所有 chunk 都有分 → 否则报错列出缺失 chunk_id
- 每维度值 ∈ [0, 10] 整数 → 否则报错
- 若 > 20% chunk 的 8 维全为 0 且非 SPARSE → 警告 Agent 可能偷懒
- 每个 score 条目必须有 `note` 字段

---

## 7. 切片算法（Stage 2）

### 7.1 自适应窗口大小

```python
def compute_window_size(duration_sec: int) -> int:
    """目标：60–120 个 chunk"""
    target_chunks = 90  # 中位目标
    raw = duration_sec / target_chunks
    # 向上取整到 "友好" 值：5, 10, 15, 30, 45, 60, 90, 120, 180s
    friendly = [5, 10, 15, 30, 45, 60, 90, 120, 180]
    return next(f for f in friendly if f >= raw) if raw <= 180 else 180
```

举例：
- 3 分钟视频：180/90 = 2s → 向上取 5s，得 36 chunks
- 18 分钟视频：1080/90 = 12s → 向上取 15s，得 72 chunks
- 3 小时直播：10800/90 = 120s → 120s，得 90 chunks

### 7.2 切片规则

- 按固定 window_size 切，最后一个 chunk 可能短于 window_size
- chunk_id 格式：`C{3 位零填充数字}`，从 `C001` 起

---

## 8. 转折点算法（Stage 4）

### 8.1 双算法并行

**算法 A：峰值 / 谷值检测**（"最炸、最冷"）

对每个情绪维度曲线，用 `scipy.signal.find_peaks` 找局部极大值：
- 参数：`height=6`（分值至少 6 分才算峰）、`distance=3`（两峰至少隔 3 chunks）、`prominence=2`（峰凸出度 ≥2）
- 同理找极小值

**算法 B：滑动窗口 JS 散度对比**（"情绪骤转"）

- 前窗口 W_prev = chunks[i-3:i]，后窗口 W_next = chunks[i:i+3]
- 每窗口计算 8 维情绪的归一化分布 P
- 计算 `JS_divergence(P_prev, P_next)`
- 若 JS > 0.15 → 候选转折点
- 同时记录"哪个维度变化最大"（绝对差值）

**合并 & 去重**：
- 两算法结果合并，按时间排序
- 时间差 < window_size * 2 的相邻转折点合并（保留更显著那个）
- 最终转折点总数上限 15（避免 HTML 列表过长）

### 8.2 转折点数据结构

```json
[
  {
    "turnpoint_id": "TP01",
    "chunk_id": "C018",
    "time_start": 252,
    "time_end": 267,
    "type": "peak|valley|shift",           // peak=局部高峰, valley=局部低谷, shift=情绪骤转
    "main_dimension": "anger",             // 主导维度
    "direction": "up|down",                // up=该维度飙升, down=该维度骤降
    "magnitude": 7.5,                       // 变化幅度（peak/valley=分值；shift=主维度差）
    "description": "anger 1→8 急升",        // 人可读描述
    "evidence_danmakus": [
      {"time": 255.2, "text": "策划死妈", "color": "#ffffff"},
      {"time": 257.8, "text": "我直接退游", "color": "#ffffff"},
      ...  // 共 5 条
    ]
  }
]
```

### 8.3 佐证弹幕选取（Stage 4 调用 `evidence_picker.py`）

对每个转折点 TP：
1. 识别主导维度 D（变化最大的维度）
2. 从 TP 所在 chunk 的全量弹幕（从 `danmaku.json` 取）中按以下优先级排序：
   - 优先级 1：文本匹配 `plutchik.py` 中 D 的关键词表
   - 优先级 2：弹幕长度降序（长弹幕信息量大）
   - 优先级 3：去重（同一用户 hash / 完全相同文本）
3. 取 Top 5
4. 不足 5 条 → 从相邻 chunk（±1）补齐

---

## 9. HTML 报告形态（Stage 5）

### 9.1 整体布局（四分区）

```
┌───────────────────────────────────────────────────────────┐
│ 🫀 emoekg · 情绪心电图                                    │
│ 《标题》| UP: xxx | 时长: 18:42 | 8,432 弹幕 | BV18acMz4ELL │
│ 生成于 2026-05-07 13:22  |  [🔗 跳转 B 站原视频]            │
├───────────────────────────────┬───────────────────────────┤
│                               │ § 全局速览                 │
│   [视频播放器]                 │   最炸 09:12 joy=9        │
│   iframe 或 local <video>      │   最冷 14:35 全维 0.3     │
│                               │   整体：喜悦主导 + 期待    │
│                               ├───────────────────────────┤
│                               │ § 情绪心电图（主图）       │
│                               │ [ECharts 8 条分层折线]    │
│                               │ 图例开关、dataZoom 滑块    │
│                               │ 视图：分层 / 堆叠 / 标准化  │
│                               │ ⬇ 标记转折点                │
│                               ├───────────────────────────┤
├───────────────────────────────┤ § 情绪转折点              │
│ § 弹幕流（可滚动可搜索）        │                           │
│ 🔍 搜索框  [全部][joy][anger]..│ ▸ #1 02:15 期待8→1 惊讶2→7 │
│ 00:00:07 开场       🟡        │    佐证:                   │
│ 00:00:10 蹲         🟠        │    • 卧槽这是什么操作      │
│ 00:00:13 ▶ 当前高亮 🟡        │    • 我期待半天就这?       │
│ 00:00:15 ...                  │    [🔗 跳 02:15]           │
│ ...                           │                           │
│                               │ ▸ #2 09:12 joy 峰 9        │
│                               │    ...                     │
│                               │                           │
├───────────────────────────────┴───────────────────────────┤
│ § 附录：情绪维度图例 · 算法说明 · 原始数据下载              │
└───────────────────────────────────────────────────────────┘
```

### 9.2 主图（ECharts）

- **图类型**：8 条折线，同一坐标系叠加（**分层**模式，非堆叠）
- **时间轴**：秒，底部带 dataZoom 滑块和缩略图
- **转折点标记**：在主图上打 ⬇ 三角，颜色 = 主导维度色
- **视图切换**：分层（默认）/ 堆叠 / Z-score 标准化
- **图例**：点击可开关单一维度（研究员只看 anger 曲线用）

### 9.3 交互联动矩阵

| 触发动作 | iframe 模式（默认） | `--with-video` 本地视频模式 |
|---|---|---|
| 点心电图某点 | 视频 seek 到该秒（重载 iframe 的 `&t=` 参数） | 视频 seek + 弹幕列表滚到那行 + 心电图游标移动 |
| 点弹幕列表某条 | 视频 seek | 视频 seek + 心电图游标移动 |
| 点转折点"🔗"按钮 | 视频 seek + 滚动到 §3 条目 | 三面板全同步 |
| hover 心电图 | tooltip 显示该 chunk 的 8 维分值条形图 + 5 条采样弹幕 | 同左 |
| **视频自己在播放** | ⚠️ 其他面板不跟随（跨域限制） | 弹幕列表自动滚动 + 心电图游标跟随 |

### 9.4 弹幕列表（左下）

- **全量展示**（几万条分页或虚拟滚动）
- 每条带**主要情绪维度色点**（根据其所在 chunk 的主情绪染色）
- 顶部搜索框：文本筛选
- 顶部情绪筛选按钮：`[全部]` `[🟡 joy]` `[🔴 anger]` ... 点击只显示该情绪类弹幕
- 当前视频时间对应的那条弹幕**自动高亮**（仅 `--with-video` 模式）

### 9.5 单文件 & 零依赖

**默认模式（iframe 嵌入）**：
- ECharts 用 `<script>` 内联（~800KB 一次性打包进 HTML）
- 所有字体用系统字体栈
- 所有数据（meta / scores / turnpoints / danmaku）用 `<script type="application/json">` 内嵌
- 产出就是一个 `.html`，打开即用，**需要联网**（因为 iframe 要加载 B 站播放器）

**`--with-video` 模式**：
- 产出为 `emoekg_report.html + video.mp4`（同目录的两个文件）
- HTML 用相对路径 `<video src="./video.mp4">` 引用视频
- 分享时需要把整个目录打包，不再是"单文件"
- 完全离线可用（不需要联网）

### 9.6 响应式 & 打印

- 桌面：1200px 容器居中
- 移动端：主图横向滚动
- `@media print`：隐藏工具栏和 dataZoom，一键 PDF 贴研究报告

---

## 10. 仓库发布物清单

> ⚠️ **本节为 v0.1.0 时的发布物清单，部分内容已在后续版本中演进。最新的逐文件清单见 [`README.md` §「📑 文件清单」](../README.md)。**
>
> 主要演进点：
> - `requirements.txt` —— v0.4.12 删除（`pyproject.toml` 是单一依赖来源）
> - `examples/` —— 实际命名为 `demos/`，且扩展至 4 个 BV 子目录
> - `CHANGELOG.md` —— 实际位于 `docs/CHANGELOG.md`（不在仓库根）
> - `docs/release-notes/` —— v0.4.11 新增子目录归档长 release note
>
> 本节其余内容保留为 v0.1.0 决策记录。

> 本节只定义"仓库里应该有哪些文件"。实际推送 GitHub 的流程（创建 repo、配 Topics、打 tag、上传 Releases）交由 `github-ops` skill 负责执行，不在本 spec 范围内。

### 10.1 仓库元信息（交接给 github-ops）

- 仓库名：`emoekg`
- 协议：MIT
- 主分支：`main`
- GitHub Topics：`agent-skill`, `bilibili`, `danmaku`, `emotion-analysis`, `ux-research`, `plutchik`, `codemaker-skill`

### 10.2 关键发布物（本 skill 开发范围内要交付的文件）

| 文件 | 内容 |
|---|---|
| `README.md` | 给终端用户看：一句话 + 适用场景 + 演示 gif + 安装 + CLI + FAQ + Roadmap + 致谢 + License |
| `SKILL.md` | 给 Agent 看：frontmatter（name + description 密集触发词）+ 工作流 + 打分 rubric + 错误处理 |
| `examples/BV18acMz4ELL_report.html` | 用跑测视频生成的真实报告，git 提交入库 |
| `examples/screenshot.png` | README 封面图 |
| `LICENSE` | MIT 标准文本 |
| `requirements.txt` | bilibili-api-python, jinja2, numpy, scipy |
| `pyproject.toml` | 版本号 v0.1.0、CLI entry `emoekg` |
| `CHANGELOG.md` | 每版本一段 |

### 10.3 `SKILL.md` frontmatter（草稿）

```yaml
---
name: emoekg
description: |
  将 B 站视频弹幕数据转化为"情绪心电图"的 skill，
  服务于 UX 研究员、内容运营、游戏策划分析玩家观看视频时的情绪波动。

  核心能力：
  1. 给定 B 站视频 URL → 自动拉取全量弹幕
  2. 按 Plutchik 8 维情绪（喜悦/信任/恐惧/惊讶/悲伤/厌恶/愤怒/期待）打分
  3. 识别情绪转折点，每个转折点附 ≥5 条原话佐证
  4. 输出单文件 HTML 交互报告（ECharts 心电图 + 弹幕流 + 视频嵌入）

  支持 `--with-video` 下载本地视频实现完整双向联动。

  当用户要求分析 B 站视频弹幕情绪、找玩家情绪高峰/低谷、
  定位"退游评论爆发时刻"、找视频哪里最炸/最冷、
  做直播回放情绪复盘、分析观众实时反应、UX 研究写报告时触发。

  即使用户没有明确说"情绪分析"，只要涉及
  "弹幕情绪"、"观众反应"、"视频哪段最炸"、"玩家情绪拐点"、
  "直播哪里冷场"、"弹幕心电图"、"B 站情绪曲线" 等场景也应触发。

  典型触发表达：
  "分析一下这个 B 站视频的弹幕情绪"、
  "看看玩家的情绪心电图，链接是 xxx"、
  "这个直播回放哪里最炸"、
  "找一下退游评论爆发的那个时刻"、
  "帮我做一张弹幕情绪时间线"。

  不适用场景：
  - 抖音/YouTube（v0.3+ 才支持）
  - 私密视频或需登录的视频（当前免登录抓取）
  - 定量问卷分析（请用 survey-research skill）
---
```

### 10.4 `requirements.txt`

```
bilibili-api-python>=16.0.0
jinja2>=3.1.0
numpy>=1.24.0
scipy>=1.10.0
# yutto>=2.0.0          # optional, 仅 --with-video 需要
```

---

## 11. 测试策略

### 11.1 单元测试（pytest）

覆盖对象：
- `bv_parser.py`：各种 URL 形态（短链、BV 号、AV 号、带分享参数）→ 提取 BV
- `adaptive_window.py`：不同视频时长 → 窗口大小正确
- `turnpoint_algo.py`：给定合成 scores 曲线 → 能找出预埋的峰值和骤变
- `evidence_picker.py`：给定 danmaku + 目标维度 → 返回的 5 条弹幕都合理（关键词命中/长度优先）
- `time_utils.py`：秒 ↔ 格式化字符串 + 弹幕 progress(ms) → 秒 归一化

### 11.2 集成测试（手动）

- 用 `BV18acMz4ELL` 跑全流程作为验收样本
- 验收标准：
  - `emoekg_report.html` 能正常在 Chrome 打开
  - 主图 8 条线都画出来
  - 转折点 ≥ 3 个，每个至少 5 条佐证弹幕
  - iframe 嵌入的播放器能播
  - 点击心电图某点能跳转 B 站视频时间码
  - 所有维度色点和图例颜色一致

### 11.3 Agent 打分质量测试

- 用 `--with-skill` / `--without-skill` 对同一 chunks.md 跑两次
- 比较 Agent 是否：
  - 按 schema 输出 JSON
  - 打分合理（人工抽检 5 个 chunk）
  - 正确处理 SPARSE
  - note 字段不空

---

## 12. Roadmap

### v0.1.0（首发）— ✅ 已发布
- 本文档定义的完整功能
- 跑测示例 `BV18acMz4ELL`

### v0.1.1（编辑器风格 UI）— ✅ 已发布
- Swiss × Editorial 暗色主题
- Insights Protocol（TL;DR + 3 洞察）
- demos/ 真实数据验证

### v0.2.x / v0.3.x（视频联动 + 弹幕侧栏）— ✅ 已发布
- `--with-video` 本地 mp4 模式 + iframe fallback
- 弹幕滚动侧栏 + 8 维过滤
- Live Trace 脉冲指示

### v0.4.x（Cockpit Console 重构）— ✅ 已发布（current = 0.4.8）
- 见 §15 实施回顾
- Vital Readout 8 维实时仪表 + 6 卡概览
- 全部数字字符 mono + tabular-nums
- ResizeObserver 高度同步
- 路径决策：跨域不强求同步，明示 ECG = Remote Control

### v0.5.0（多视频对比）— 计划中
- 同 UP / 同系列横向情绪对比仪表盘
- 导出情绪摘要 CSV / Markdown

### v0.6.0（平台扩展）— 探索中
- 抖音评论
- YouTube 评论 + chat replay
- Twitch chat
- 直播实时模式（边播边打分）

### v0.7.0+（高级分析）— 远期
- 情绪预测（给段视频预测情绪曲线）
- 玩家人设分析（从弹幕反推用户群体特征）

---

## 13. 开放问题（以备后续迭代）

| 问题 | 现阶段决定 | 后续可能调整 |
|---|---|---|
| Agent 打分与真实情绪的一致性如何验证？ | 人工抽检 + 对照测试 | 未来可邀请 UX 研究员标注 100 个样本做验证集 |
| 视频超长（5h+ 直播）Agent 打分会不会超时？ | 批次写盘 + 断点续跑 | 未来可考虑"先采样 1/3 chunks 快速预览，再全量" |
| 中文弹幕 vs 英文弹幕 vs 表情符号 | 都当普通文本交给 Agent | 未来可加语言识别预处理 |
| 弹幕作者同一句话刷屏（n 号机器人）| 当前按字数去重 | 未来可按用户 hash 去重，或统计"刷屏用户占比" |

---

## 14. 成功标准

发布后 30 天内：
- [ ] GitHub 仓库公开 + README 完整
- [ ] `examples/BV18acMz4ELL_report.html` 可访问
- [ ] 在 CodeMaker Skills 列表中可安装
- [ ] 至少 1 位 UX 研究员同事试用并反馈
- [ ] Agent 正确触发率 ≥ 90%（说"分析 B 站弹幕情绪"时能正确启动 skill）

---

## 15. v0.4.x 实施回顾 — Cockpit Console（2026-05-11）

> **Status**: Shipped (v0.4.x 系列，首发 v0.4.2，持续维护中——具体 patch 版本见 [`docs/CHANGELOG.md`](./CHANGELOG.md)；不在本 spec 中追踪具体 patch 号以避免文档反复 bump)
> **Driver**: 真实使用反馈：v0.1.0 的 Swiss × Editorial 静态档案在交互上「太死」，研究员希望右侧成为可读的实时仪表，而不是滚动列表。

### 15.1 信息架构调整

原 §3.1 流水线产出的报告由「Hero Summary + ECG 主图 + 转折点卡 + 弹幕滚动列表」四块组成。v0.4.x 将报告 §02 模块重构为 **Cockpit Console（驾驶舱）** 三联仪表：

```
┌──────────────────┬─────────────────────────────────────┐
│                  │  Vital Readout（8 维分量条）         │
│   Bilibili       │  ── 鼠标悬停 ECG 即时驱动 ──         │
│   iframe / mp4   ├─────────────────────────────────────┤
│   播放器          │  Vital Stats Grid（6 卡概览）        │
│                  │  总弹幕 / 极性 / 主导 / 峰 / 谷 / 转  │
└──────────────────┴─────────────────────────────────────┘
              ECG 心电图（兼具时间轴 + Remote Control）
              ↓ click 跳转 / hover 驱动右侧 readout
```

弹幕**全表搜索**移交给 §05 模块（带 8 维过滤 + 关键词），§02 不再承担"翻全片找一句弹幕"的职能。这是 D7 决策（见 §15.4）。

### 15.2 关键技术约束

| # | 约束 | 现实 | 落地决策 |
|---|---|---|---|
| C1 | B 站 iframe 跨域 | 无法读取播放器当前时间 / 无法 seek 到指定秒 | 不再追求"视频驱动 ECG 同步"；UI 明示 ECG 是 Remote Control，hover 驱动整套仪表 |
| C2 | `vital-stats-grid` 需要在窄屏 / 宽屏均横向对齐 | label 长度不一会换行，导致数字基线下沉 | `grid-template-rows: 18px 38px ...` 显式锁定行高 + label `nowrap + ellipsis` |
| C3 | 数字字体一致性 | 多字体混用（serif 数字 + sans 文本）显得杂乱 | 全部计数 / 时间码 / 比率切到 `ui-monospace` 700 + `tabular-nums slashed-zero` |
| C4 | hint 文案中英混排 | 用户群体主要为中文用户 | hint 全部以中文为主 + 必要时附 8–10 字英文小注，hint 字号统一 10.5px mono |
| C5 | dashboard 高度跟随 iframe | iframe 不能 resize 时 dashboard 会显得过长 | `ResizeObserver` 监听 iframe 高度，动态 lock dashboard 高度 |

### 15.3 v0.4.x 模块清单（templates 层）

```
report.html.j2 增量
├── .cockpit-grid              # 视频 + dashboard 2-col 主布局
├── .vital-readout             # 8 维分量条 + 主导情绪标签
├── .vital-stats-grid          # 6 卡概览（vs-card * 6）
├── .vs-card / .vs-num         # mono + tabular-nums + 行高锁定
├── .monitor-head .hint        # 10.5px mono + 橙色脉冲箭头
├── .headline.mono             # 全局数字标题样式
└── @keyframes hint-pulse      # 箭头跳动（与 live-trace 区分语义）

app.js 增量
├── updateVitalReadout(t)      # ECG hover → 驱动 8 维条 + 主导 + trail
├── renderVitalStats()         # scores.json → 6 卡聚合
├── syncPanelHeight()          # ResizeObserver iframe → dashboard 高度
└── bindBilibiliPostMessage()  # best-effort 跨域监听（可能失败，不强依赖）
```

### 15.4 新增决策（D7–D11）

| # | 决策 | 结果 | 理由 |
|---|---|---|---|
| D7 | §02 改为 Cockpit Console，弹幕全表搜索移到 §05 | 接受 | 驾驶舱旁边不该是「滚动列表」，应是即时读数；研究员需要全量搜索时切到 §05 |
| D8 | 跨域 iframe 不假装能反向同步 | 接受 | 与其用 best-effort polling 误导用户，不如声明 ECG = Remote Control |
| D9 | 所有数字字符使用 `ui-monospace` + `tabular-nums slashed-zero` | 接受 | 仪表盘式 UI 要求列宽对齐 + 0/O 可辨；serif 数字在小尺寸下显得歪 |
| D10 | `vital-stats-grid` 锁定 `grid-template-rows` | 接受 | 修复横屏模式下 label 长度差异导致的基线下沉 bug |
| D11 | hint 字段统一为中文 + 橙色脉冲箭头 | 接受 | C4 约束；同时区分 live-trace（红，呼吸）与 hint-pulse（橙，跳动） |
| D12 | 默认输出位置 = 桌面；交付**单一文件夹** `AI情绪心电图-<关键字>/`，文件夹内含同名 `.html` 副本 | 接受（v0.4.9 提出 / v0.4.10 收敛为单文件夹） | 终端用户看不到 `emoekg_report.html` 这种英文名；CLI 不强改文件名（保持 demos / 断点续跑兼容），改由 SKILL Step 6 强制 Agent **整个 working dir 改名 + 内放友好 HTML 副本**——既整洁又不破坏中间产物结构 |

### 15.5 与原 §3 / §4 的兼容性

- **Pipeline 5 阶段不变**：S1–S5 输入输出 schema 全部向后兼容，老 `scores.json` / `insights.json` 直接渲染即可拿到 v0.4.x UI。
- **`_lib/` 算法层不变**：`turnpoint_algo` / `evidence_picker` / `plutchik` 校验等纯函数零改动。
- **新增依赖：无**。Cockpit Console 全部由模板层（CSS + 原生 JS）实现，未引入新的 Python 包。
- **测试新增**：`test_stage5_render` 增加 `vital-stats-grid` / `vital-readout` 字符串存在性断言（合计 194 测试通过）。

### 15.6 已知限制

1. **跨域 iframe 反向同步**：B 站 iframe 不开放 postMessage 协议，因此**视频播放进度不会驱动 ECG 光标**。`--with-video` 模式下使用本地 mp4 才能拿到完整双向联动。
2. **超宽屏 (>1920px)**：6 卡仍排成 2×3 网格，未做单行 1×6 自适应。下一版可考虑 `auto-fit, minmax(160px, 1fr)`。
3. **`syncPanelHeight` 在某些 Edge 版本回退**：少数浏览器不触发 `ResizeObserver`，dashboard 会保持模板默认高度。

---

## 附录 A：术语表

| 术语 | 含义 |
|---|---|
| Plutchik 8 维 | Robert Plutchik 1980 年提出的 8 种基本情绪：joy/trust/fear/surprise/sadness/disgust/anger/anticipation |
| chunk | 时间切片，Stage 2 产出，每个 chunk 对应一个时间窗口 |
| 转折点（turnpoint） | Stage 4 识别出的情绪拐点，包含峰值、谷值、骤转三种类型 |
| 佐证弹幕 | 每个转折点附带的 ≥5 条原弹幕，供研究员查证判断依据 |
| SPARSE chunk | 弹幕数 < 3 的时间窗口，打 0 + 视觉虚线标识 |
| JS 散度 | Jensen-Shannon divergence，度量两个概率分布差异，范围 [0, 1] |
| CodeMaker Agent | 执行 skill 的 AI agent，本 skill 依赖其完成 Stage 3 打分 |
