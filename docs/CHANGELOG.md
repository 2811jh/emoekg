# Changelog

按 [Semver](https://semver.org/) 维护，记录每个版本的关键变更。
当前版本：**v0.4.14**（current）。

---

## v0.4.x — Cockpit Console（2026-05-11 系列）

> **主题**：将报告 §02 模块从「视频 + 弹幕滚动列表」重构为「视频 + 8 维 Vital Readout 仪表盘」，建立"驾驶舱 / 监护仪"语义体系。详细设计见 [`2026-05-07-emoekg-design.md` §15](./2026-05-07-emoekg-design.md#15-v04x-实施回顾--cockpit-console2026-05-11)。

### v0.4.14 — 开发文档系统化（7 处优化）

> **诊断**：旧版开发文档存在"措辞冲突 / 信息陈旧 / 缺 deprecated 标记 / 缺总入口"四类问题，本次一次清理到位。

- **fix**: `scoring_rubric.md §6.7` 步骤编号与 SKILL.md 冲突 —— 改用 rubric 自己的章节号（§5 / §6），并加注释说明 "rubric §6 ≠ SKILL Step 6"，防止 Agent 误把"写洞察"理解为"做桌面投放"
- **fix**: `release-notes/README.md` 索引中「v0.4.2 ~ v0.4.10 不再单写」改为「v0.4.2 之后」，避免每次 patch 都跟着 bump
- **chore**: `2026-05-07-emoekg-design.md §15` 顶部 `Status: Shipped (current = v0.4.8)` 改为「v0.4.x 系列，首发 v0.4.2，patch 不在 spec 追踪」 —— 避免文档反复 bump
- **chore**: `2026-05-07-emoekg-design.md §10` 顶部加 deprecated banner —— 标注 `requirements.txt` 已移除（v0.4.12）、`examples/` 实为 `demos/`、`CHANGELOG.md` 在 `docs/` 下；正文保留作 v0.1.0 决策留痕
- **chore**: `2026-05-07-emoekg-plan.md` 文件头加 HISTORICAL ARCHIVE banner —— 102KB 实施计划已 100% 完成，明示接手者「不要据此做新开发决策」
- **new**: `docs/superpowers/README.md` —— 说明本目录是 v0.4.0 之前「弹幕侧栏」方案的归档，被 v0.4.2 Cockpit 取代（决策 D7），保留以供"为什么不那样做"溯源
- **new**: `docs/README.md` —— `docs/` 总入口（meta-doc），按「我想做什么」给读者导航；附文档生命周期约定表（active / frozen / archived）与「新增文档归属规则」
- **docs (主 README)**: 同步「📑 文件清单」—— `docs/` 分组 4→5、`docs/superpowers/` 分组 2→3、合计 80→82，与 `git ls-files | wc -l` 重新对账

### v0.4.13 — README 加「📑 文件清单」逐文件说明
- **docs (README)**: 新增 `## 📑 文件清单` 模块，按目录分组覆盖**全部 80 个 git tracked 文件**
  - 9 个分组：根目录 / `docs/` / `docs/release-notes/` / `docs/superpowers/` / `demos/` / `src/emoekg/` / `_lib/` / `stages/` / `templates/` / `tests/`
  - 每个文件 3 列说明：文件路径（点击直达）、用途、谁会读它（target audience）
  - `demos/` 28 文件采用「7 文件命名规则 + 4 BV 子目录列表」结构（4 BV × 7 文件笛卡尔积），避免机械重复但 100% 覆盖
  - tests 表加 case 数列（合计 194）
  - 末尾给出 9 分组数量加和 80 ✓ 与 `git ls-files | wc -l` 互验
- **docs (README demos)**: 修正 4 个 BV 子目录的真实视频标题（直接读 `meta.json` 的 `title` 字段）
- **rationale**: 用户希望"每个文件都不能跳过"，确保 README 是仓库的精确地图，而不是抽样描述

### v0.4.12 — 删除冗余 `requirements.txt`
- **chore**: `requirements.txt` 内容与 `pyproject.toml` 的 `dependencies = [...]` 完全一致（4 行对 4 行），保留两份会产生 "谁是 source of truth" 的歧义；删除以遵循现代 Python 包工程标准（pyproject.toml 单一来源）
- **docs**: README 项目结构树 + SKILL Files 列表去除该文件引用，并补一句 "single source of truth" 说明
- **不影响安装**: README 推荐的 `pip install -e .` 走 pyproject.toml，不依赖 requirements.txt；唯一受影响的是历史上通过 `pip install -r requirements.txt` 装的脚本（如有）需要切到 `pip install -e .` 或 `pip install .`
- **历史档案**: `docs/2026-05-07-emoekg-design.md` 与 `docs/2026-05-07-emoekg-plan.md` 内的 `requirements.txt` 引用**保留不动**——这两份是 v0.1.0 时刻的设计快照，不回溯修订

### v0.4.11 — 仓库结构整理（标准范式）
- **chore**: 清理仓库根目录碎屑——删除 `-p/`（mkdir 误用产物）、`build/`、`.pytest_cache/`、`.superpowers/`（已 ignored，但本地碎屑未清）
- **chore**: 4 份散落的 `RELEASE_NOTES_v0XX.md` 移到 `docs/release-notes/` 并按 SemVer 重命名（`v0.3.0.md` 等）
- **docs**: 新建 `docs/release-notes/README.md` 索引，明确与 `CHANGELOG.md` 的边界（前者长，后者短）
- **chore**: `.gitignore` 重写——加分类注释，加 `-p/`/`-r/`/`-rf/` 防御性入口（防 mkdir 误用）、`AI情绪心电图-*/`（v0.4.10 默认输出文件夹）、`.mypy_cache/`/`.ruff_cache/`/`.coverage`/`wheels/` 等 Python 工具链遗漏项
- **docs (README)**: 「📁 项目结构」段重写——加链接到 PyPA src layout 解释，新增「命名澄清」段说明 `src/` 不是缩写、`_lib/` 下划线含义、`docs/release-notes/` vs `CHANGELOG.md` 边界
- **rationale**: 用户截图反馈仓库根目录看起来"乱"——`-p` 不知道是什么、release notes 散落、build 缓存到处都是；按 PyPA + Anthropic Skills 标准范式整理

### v0.4.10 — 单一文件夹收纳（refine v0.4.9）
- **change (SKILL Step 6)**: 不再「桌面散一份 HTML」，改为**整个 working dir 改名为 `AI情绪心电图-<关键字>/`**，文件夹内额外放一份同名 `.html` 副本
- **rationale**: v0.4.9 的「桌面 HTML + 旁边一个临时目录」让桌面看起来很乱；用户希望"一次跑完只产出一个文件夹"
- **change (SKILL)**: 重名冲突处理对象从「同名 HTML」改为「同名文件夹」，加 `_2`/`_3` 后缀
- **change (SKILL)**: 跨平台命令模板由「`copy`/`cp`」改为「`move`+`copy`」组合，强烈推荐 Python 单行（`shutil.move` + `shutil.copy2`）
- **change (SKILL)**: 输出目录结构图分两阶段（Step 2–4 临时占位 + Step 6 改名后）
- **change (SKILL Common Mistakes)**: 加新陷阱「只复制 HTML 不改文件夹名」
- **change (README)**: 数据产物布局图重画为「单文件夹收纳」视图

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
