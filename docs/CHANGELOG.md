# Changelog

按 [Semver](https://semver.org/) 维护，记录每个版本的关键变更。
当前版本：**v0.4.9**（current）。

---

## v0.4.x — Cockpit Console（2026-05-11 系列）

> **主题**：将报告 §02 模块从「视频 + 弹幕滚动列表」重构为「视频 + 8 维 Vital Readout 仪表盘」，建立"驾驶舱 / 监护仪"语义体系。详细设计见 [`2026-05-07-emoekg-design.md` §15](./2026-05-07-emoekg-design.md#15-v04x-实施回顾--cockpit-console2026-05-11)。

### v0.4.9 — 默认桌面输出 + 友好命名（SKILL 层规则）
- **feat (SKILL)**: Step 1 — 默认输出位置 = 用户桌面（Windows: `%USERPROFILE%\Desktop`、macOS/Linux: `~/Desktop`），用户没显式指定时不再追问"放哪里"
- **feat (SKILL)**: 新增 Step 6「友好命名 + 桌面投放」——CLI 产出 `emoekg_report.html` 后，必须复制一份到桌面根目录重命名为 `AI情绪心电图-<视频关键字>.html`
- **feat (SKILL)**: 关键字提取规则 6 条 + 重名 `_2`/`_3` 处理 + 跨平台命令模板（cmd / bash / Python）
- **feat (SKILL)**: Step 5 自检清单加 2 条桌面投放校验；Common Mistakes 加 3 条新陷阱
- **change (README)**: 数据产物布局图分两块（working dir + 桌面友好名）；触发示例增加默认桌面提示
- **rationale**: 终端用户看不到 `emoekg_report.html` 这种英文名；研究员希望产物像「截图 / 论文 PDF」一样直接落桌面，不需要进 working dir 翻

### v0.4.8 — 横屏对齐修复 + GitHub 同步
- **fix**: 横屏浏览器下 `vital-stats-grid` 6 卡基线不齐 — 用 `grid-template-rows: 18px 38px ...` 显式锁定行高
- **fix**: label 长文本（如「主导情绪 / DOMINANT」）换行挤压数字位置 — `nowrap` + `text-overflow: ellipsis`
- **chore**: `robocopy` 把开发仓与 `.agents` skill 目录同步到 v0.4.8

### v0.4.7 — 数字字体仪表化
- **change**: 所有计数 / 时间码 / 比率切换到 `ui-monospace` 700 + `tabular-nums slashed-zero`
- **change**: `.headline.mono` 全局工具类，统一仪表读数视觉
- **rationale**: 用户反馈 Bodoni serif 数字"歪七八扭"，仪表盘式 UI 要求列宽对齐 + 0/O 可辨

### v0.4.6 — Hint 文案统一 + 橙色脉冲箭头
- **change**: 所有 `monitor-head .hint` 改为 10.5px mono + 橙色脉冲箭头（`hint-pulse`）
- **change**: 区分 `live-trace`（红，呼吸）与 `hint-pulse`（橙，跳动）两套语义
- **fix**: "底部 缩放时间"等 hint 文本不再换行堆叠，改为 `nowrap` 一行展示

### v0.4.5 — DOMINANT 区域瘦身
- **fix**: 主导情绪标签从「DOMINANT喜悦 · JOY 6/10 预览中」改为「喜悦 · JOY 6/10」，腾出宽度
- **fix**: hint 文案与心电图悬停说明分离，避免误导

### v0.4.4 — Vital Readout 实装
- **feat**: `updateVitalReadout(t)` — ECG 鼠标悬停即时驱动 8 维分量条 + 主导情绪标签 + 邻域弹幕 trail
- **feat**: `renderVitalStats()` — 总弹幕量 / 极性比 / 主导情绪 / 最炸 / 最冷 / 反转次数 6 卡聚合
- **rationale**: 心电图 8 维不应只显示在一个 panel 里；hover 同一时间点应触发整套仪表

### v0.4.3 — 跨域 iframe 现实主义
- **change**: 不再假装能反向同步 B 站 iframe；UI 明示「ECG = Remote Control」
- **feat**: `bindBilibiliPostMessage()` best-effort 监听（B 站不开协议时静默 fallback）
- **feat**: `syncPanelHeight()` 用 `ResizeObserver` lock dashboard 高度到 iframe 底边

### v0.4.2 — Cockpit 布局
- **refactor**: 删除 `renderPanelList` / `findRowIdxAt` 等 200+ 行虚拟滚动逻辑
- **refactor**: `.media-row` flex → `.cockpit-grid` 2-col grid（视频 + dashboard）
- **rationale**: 驾驶舱旁边不该是滚动列表，应是即时读数

### v0.4.1 — 弹幕侧栏首版（被 v0.4.2 取代）
- 试验性虚拟滚动弹幕列表
- 实测交互不符合"驾驶舱"心智模型，立即重构

---

## v0.3.x — 视频联动 + 弹幕侧栏（2026-05-09）

- **feat**: `--with-video` 本地 mp4 模式，video 元素 + 心电图双向 seek
- **feat**: iframe 模式 fallback（默认零依赖路径）
- **feat**: 弹幕滚动侧栏 v1（按 8 维过滤 + 关键词搜索）
- **feat**: Live Trace 呼吸圆点（视频 + ECG 标题旁同步脉冲）
- **docs**: `superpowers/specs/2026-05-09-danmaku-sidebar-design.md`
- **docs**: `superpowers/plans/2026-05-11-v0.4.0-danmaku-panel.md`

---

## v0.2.x — yutto 集成探索（2026-05-08）

- **feat**: 可选依赖 `[video]` extras（`pip install -e ".[video]"`）
- **feat**: yutto 命令封装，自动下载 B 站原视频到 `video.mp4`
- **fix**: bilibili-api-python 三类 bug 回归测试（去重、色值归一化、分段 Protobuf 拼接）

---

## v0.1.1 — Swiss × Editorial UI + Insights Protocol（2026-05-08）

- **feat**: Hero 区 Executive Summary（30–80 字 TL;DR + 3 条洞察）
- **feat**: `insights.json` schema + Stage 3 强制要求
- **feat**: 暗色研究档案 UI，11 阶中性灰 + Accent Orange `#EB5E28`
- **feat**: 转折点卡片可折叠，前 3 条默认展开
- **feat**: ECharts 自定义磷光发光（shadowBlur 2 / emphasis 8）
- **demo**: `demos/bv18acmz4ell/` 端到端真实数据验证

---

## v0.1.0 — 首发（2026-05-07）

- **feat**: 5 阶段流水线（Stage 1 fetch / 2 slice / 3 Agent score / 4 detect / 5 render）
- **feat**: 自适应窗口切片（target ~90 chunks）
- **feat**: Plutchik 8 维 0–10 分打分协议（`docs/scoring_rubric.md`）
- **feat**: 双算法转折检测（scipy 峰值 + Jensen-Shannon 散度）
- **feat**: 佐证弹幕采样排序（关键词 > 长度 > 时间）
- **feat**: 单文件离线 HTML 报告（ECharts 5.5 内联）
- **feat**: CLI `prepare / finalize / run` 三子命令 + 幂等 / `--force`
- **docs**: `docs/2026-05-07-emoekg-design.md` 完整设计 spec
- **test**: 157 个单测覆盖全链路
