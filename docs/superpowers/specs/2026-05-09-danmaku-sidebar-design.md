# emoekg v0.4.0 · §02 内嵌弹幕流面板 设计文档

## Meta

| | |
|---|---|
| Status | Approved Design (pending implementation) |
| Brainstorm Date | 2026-05-09 |
| Target Version | emoekg v0.4.0 |
| Related | [2026-05-07-emoekg-design.md](../../2026-05-07-emoekg-design.md) · v0.3.1 current release |

## 背景

截至 v0.3.1，emoekg 报告提供 ECG 曲线 + 8 维情绪轮 + 3-5 条转折点佐证弹幕。研究员工作流中的一个缺口：**看到 ECG 峰值时，想对齐当时的原始弹幕上下文**，现在只能回到 §03 看少量 evidence 或手动翻 §02 tooltip。

v0.4.0 把 §02 主可视化区改为**左右双列**：左列保留 video / ECG（现有），右列新增**弹幕流面板**（`DanmakuPanel`），把全量弹幕池作为一等公民放进报告，与视频 / ECG / TP 双向绑定。面板随 §02 一起滚动，离开 §02 区域时自然消失——不做 fixed 挂件。

## 目标

**P0（MVP）**

1. §02 主可视化区拆为左右双列：左列 video / ECG 堆叠（现有），右列嵌入弹幕流面板（约 35% 宽），不侵入 §01 / §03-§05 的 DOM 与事件
2. 两种模式：**Follow**（跟视频 / TP 走）、**Browse**（全量 + 文本检索）
3. 支持 48 min × 1886 条样本零卡顿，支持 SPARSE 样本降级
4. 每条作为 TP evidence 的弹幕行打 `▲` 徽章，点击跳 §03 TP 卡片

**非目标**

- 多弹幕池对比（多视频对比需要独立设计）
- 导出选中弹幕（v0.5 候选）
- 单条弹幕情绪打分（数据层不支持）
- Live 直播弹幕（emoekg 本不做）

---

## §1 · 架构概览

**基线原则：** 不破坏 §01 / §03-§05 的现有 DOM 和事件。仅在 §02 内部把主可视化区改为左右双列——左列 video / ECG 堆叠（现有），右列新增 `DanmakuPanel`。通过全局事件总线（`emoekg.bus`）与其它组件交换数据。

**组件层级**

```
┌─ <report.html> ──────────────────────────────────────────────┐
│  §01 Hero                                                    │
│                                                              │
│  ┌─ §02 Emotional ECG ────────────────────────────────────┐  │
│  │                                                         │  │
│  │  ┌─ 主列（左, flex 65%）────┐  ┌─ DanmakuPanel ───────┐│  │
│  │  │  <video>  ←─ with-video  │  │ [Follow] [Browse]   ││  │
│  │  │  ECG 方格纸主图          │  │ ──────────────────  ││  │
│  │  │  (无 video 时只剩 ECG)   │  │   VirtualList       ││  │
│  │  │                          │  │   row[i]            ││  │
│  │  │                          │  │   ...               ││  │
│  │  │                          │  │ ──────────────────  ││  │
│  │  │                          │  │ 1886 条 · 07:42     ││  │
│  │  └──────────────────────────┘  └─────────────────────┘│  │
│  │                                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                              │
│  §03 TP Details   ← 滚到这里时 DanmakuPanel 已滚离视口       │
│  §04 Wheel                                                   │
│  §05 Method                                                  │
└──────────────────────────────────────────────────────────────┘
           ↕ emoekg.bus (已有 seekAll / TPSelect 事件)
           新增订阅: video.timeupdate / dom events
```

**面板内层结构**

```
┌─ DanmakuPanel ──────────┐
│  [Follow] [Browse]      │  ← Tab Bar（无折叠钮，直接占 §02 右列）
├─────────────────────────┤
│                         │
│   VirtualList           │  ← 两模式共用虚拟滚动容器
│     row[i]              │
│     row[i+1]            │
│     ...                 │
│                         │
├─ footer ────────────────┤
│ 当前 00:12:34 · 1886条  │  ← 状态条
└─────────────────────────┘
```

**数据注入：** `render_report.py` 在渲染 HTML 时把精简后的 `danmaku.json`（只留 `id` / `time` / `text`）内联到 `<script id="danmaku-data" type="application/json">`。48 min × 1886 条约 100-150 KB，可接受。

**状态单源：** 一个全局 `DanmakuStore` 对象。字段：
- `currentTime: number` — 当前视频时刻
- `mode: 'follow' | 'browse'`
- `filter: string` — 搜索关键词（Browse 模式）
- `followPaused: boolean` — 用户手滚后暂停自动居中
- `allDanmaku: DanmakuRow[]` — 启动时解析一次

所有 UI 是该 store 的 reflection。

**定位策略：** 面板 inline 在 §02 section 内，用 CSS flex 布局（`display: flex; flex-direction: row`）。左列 `flex: 0 0 65%`，右列 `flex: 1`（约 35%）。面板高度跟随左列的内容高度（min-height 匹配 video+ECG 的总高度，避免左右两列错位）。自然随页面滚动——滚到 §03 时面板一起离开视口，不再占据视觉空间。

---

## §2 · Follow 模式交互

**定位：** 跟着视频 / TP 时间轴走，把当前时刻 ±20s 的弹幕铺在眼前。

**跟谁（三档优先级）**

| 优先级 | 触发 | 中心时间 |
|---|---|---|
| 1 | 视频正在播放 | `video.currentTime`（浏览器节流 ~250ms） |
| 2 | 用户刚点了 TP | TP 的 `time_peak`（持续到下次 seek 或播放） |
| 3 | 其它静止态 | 最后一次中心时间（不动） |

**列表布局——居中式**

```
07:42  前面还笑        ← opacity 0.4（t-20s）
07:43  草
07:55  卧槽
07:58  这段牛
━━━━━━━━━━━━━━━━━━━━  ← 当前播放线 t=08:02（粗横线）
08:02  哈哈哈哈哈       ← 高亮（金左边框 3px + 粗体）
08:02  春晚警告
08:05  前方高能
08:08  ...              ← opacity 0.4（t+20s）
```

理由：研究员看峰值时最需要**前后文**，不是 chat-style 向下追新。居中让上 20s / 下 20s 都可见。

**时间窗口：** 固定 **±20s**（40s 窗）。不做自适应窗口。

**手动滚断 + 归位**

- 用户滚动滚轮 → `followPaused = true`，右下角浮现 `↓ 回到当前` 按钮
- 点按钮或触发 `seekAll()` → `followPaused = false`，恢复自动居中
- 视频暂停 → 保持当前居中（不跟随也不乱跳）

**视觉分层**

| 距离 | 样式 |
|---|---|
| \|t - currentTime\| < 1s | 金色左边框 3px + 粗体 |
| \|t - currentTime\| < 20s | 正常行 |
| 18s ≤ \|t - currentTime\| < 20s | `opacity: 0.4` 渐隐边缘 |

---

## §3 · Browse 模式交互

**定位：** 全量弹幕 + 文本检索，用于"找所有带『春晚』的"或漫无目的翻阅。

**功能三件套**

1. **搜索框**（唯一筛选维度）
   - 即时过滤，debounce 200ms
   - 不区分大小写，不支持正则
   - 空值 = 显示全部

2. **列表呈现**
   - 全量虚拟滚动
   - 时间升序固定
   - 行内：`MM:SS │ 弹幕文本`
   - 命中关键词：橙色 underlay 高亮

3. **点击跳转**
   - 点弹幕行 → `seekAll(time)` 触发全局 seek
   - **不自动切回 Follow 模式**——避免打断浏览流
   - ECG 图通过 `emoekg.bus` 同步跳转

**状态条文案**

```
全量 1886 条 · 搜索 "春晚" → 12 条命中 · 当前 07:42
```

**TP 佐证徽章**

若一条弹幕是某 TP 的 evidence，行尾打一个 `▲`：

- 数据来源：`turnpoints.json` 里 `evidence` 字段包含的 `danmaku_id`
- 点 `▲` 不触发 seek，只 `scrollIntoView` 到 §03 对应 TP 卡片
- 颜色跟 TP 类型：peak → `--tp-peak`，valley → `--tp-valley`，shift → `--tp-shift`
- hover 放大 1.2x（复用 §03 既有动画）

**明确不做（YAGNI）**

- ❌ 时间段筛选（ECG 主图 dataZoom 已覆盖）
- ❌ 情绪维度筛选（单条弹幕无打分）
- ❌ 密度热力条（v0.5 候选）
- ❌ 排序切换（时间升序是唯一合理排序）

---

## §4 · 双向数据绑定

**原则：** 不加新广播事件，只加新订阅。复用 `emoekg.bus.seekAll(time)`。

**信号流矩阵**

| 输入 | 触发方 | 消费方 | 效果 |
|---|---|---|---|
| `video.timeupdate` | 视频原生 | Panel (Follow) | 更新 store.currentTime → Follow 居中 |
| `seekAll(time)` | 任意组件 | 所有组件 | 全局同步 seek |
| Panel 点弹幕行 | Panel | `seekAll(t)` | 广播 |
| Panel 点 `▲` | Panel | §03 TP 卡片 | `scrollIntoView`，不广播 seek |

**四条核心数据流**

```
① 视频播放 → Follow 居中
   <video>.timeupdate
     → store.currentTime = t
        → Follow: 重算 ±20s 窗口 + scrollToCenter(t)

② 点 ECG / TP / 弹幕行 → 全局 seek → 各组件响应
   发起方 → seekAll(t)
     ├→ <video>.currentTime = t
     ├→ ECG markLine 移到 t
     └→ store.currentTime = t
          ├→ Follow: 重新居中
          └→ Browse: 列表轻滚到最近 t 行（不切 tab）

③ 点 ▲ 徽章
   Panel row.▲ click
     → getElementById(`tp-card-${id}`).scrollIntoView({behavior:'smooth'})
     → 不触发 seek，不改 currentTime

④ Tab 切换 Follow ↔ Browse
   纯 UI 状态，不广播
   Browse → Follow: 清搜索框，居中 currentTime
   Follow → Browse: 保留搜索框，定位最近 currentTime 行
```

**TP "当前选中"用 computed，不存字段**

```js
currentTP = turnpoints.find(tp => Math.abs(tp.time_peak - store.currentTime) < 2)
```

状态跟时间走，不会漂移。

**Follow 暂停（用户手滚）**

- `store.followPaused: boolean`，不广播、不影响外界
- 收到 timeupdate 时 paused → 跳过 scrollToCenter
- 用户点 `↓ 回到当前` → 清标志位
- 任意 `seekAll()` 调用 → 清标志位（外部 seek 意味着用户想要重新跟随）

**不引入**

- ❌ Panel state 持久化（刷新就重置，保持无状态）
- ❌ URL hash 同步（现有 dataZoom 也没同步，不开先例）

---

## §5 · 性能与渲染

**场景基线**

- 最差已验证样本：48 min × 1886 条（BV1arcxz5Epf）
- SPARSE 样本：11 条（无性能压力）
- 目标：Follow 每 ~250ms timeupdate 重绘不卡顿；搜索输入 < 100ms 可见

**虚拟滚动——手写不引库**

- `app.js` 是原生 JS，引 react-virtual 带 runtime 成本不值
- 手写 ~80 行 JS 足够
- 固定行高 **44px** + `text-overflow: ellipsis`，长弹幕截断，`title` 属性挂全文
- 可见行数 = `containerHeight / 44`，前后各 5 行 buffer
- 不可见行不建 DOM，用 `padding-top/bottom` 占位

```
┌─ panel viewport ────────┐
│ padding-top: 264px     │ ← 占位
├────────────────────────┤
│ row[13]                │ ← 实际渲染 ~16 个 <div>
│ ...                    │
│ row[28]                │
├────────────────────────┤
│ padding-bottom: 5500px │ ← 占位
└────────────────────────┘
```

**搜索过滤**

- 全量 `Array.filter()` → 更新 `filteredRows` → 虚拟滚动吃过滤后数组
- 1886 条 filter < 5ms，不做索引，不开 Web Worker

**Follow 居中**

- `scrollToCenter(t)`：二分找最近 row idx → 计算 targetScrollTop → 直接赋值
- **instant 不 smooth**——smooth 在 500ms 连续更新下积累卡顿
- timeupdate 自带浏览器节流（~250ms），不额外 debounce

**初始化成本**

| 阶段 | 耗时估算 |
|---|---|
| 内联 JSON.parse (100-150 KB) | ~15-20ms |
| 按 time 排序 1886 条 | <5ms |
| 首屏 DOM 渲染 16 行 | <10ms |
| **总计** | **<50ms**（人感知不到） |

**极端 degrade**

- 弹幕 > 10000 条：本版本不管，下次再说
- 无 `danmaku.json`：面板灰态 "弹幕数据未加载"，两 tab 禁用
- `JSON.parse` 失败：`console.error` + 整个 Panel `display:none`

**不引入**

- ❌ Web Worker（filter 不够慢）
- ❌ IndexedDB 持久化
- ❌ 懒加载 / 分页（全量内联 + 虚拟化最简单）

---

## §6 · 视觉语言

与 v0.3.0 美学一脉相承（ECG 方格纸、暗色主题、6seconds 轮配色 token）。

**容器（§02 右列）**

- 所在父节点：`<section id="section-ecg">` 下新增 `<div class="ecg-row">`，其内两个子项：`<div class="ecg-main">`（左，现有 video + ECG）+ `<div class="danmaku-panel">`（右，新增）
- `.ecg-row`：`display: flex; flex-direction: row; gap: 20px; align-items: stretch`
- `.danmaku-panel`：`flex: 1 1 0; min-width: 320px; max-width: 440px`——约占 §02 内部宽度的 30-35%
- `background: var(--paper-0)` 纯色——**不用 glassmorphism**，滚动性能友好
- `border-left: 1px solid var(--divider)` 分割线，不用阴影（阴影在 inline 布局里反而显脏）
- `border-radius`：跟 §02 卡片保持一致（`var(--radius-card)`）

**Tab 条**

- 下划线型切换
- active 色：`var(--accent-gold)`
- 字号 14px，uppercase，字距 0.08em
- 位置固定在面板顶部，不随列表滚动

**弹幕行**

- 行高 44px，左右 padding 16px
- 顶部对齐时间，底部对齐文本
- `MM:SS`：单色次要 `var(--text-muted)`，等宽字（`font-variant-numeric: tabular-nums`）
- 弹幕文本：`var(--text-primary)`

**当前帧行（Follow 模式）**

- 金色左边框 3px
- 文本粗体
- 背景色：`rgba(gold, 0.08)`

**边缘行（Follow 模式 t±18~20s）**

- `opacity: 0.4`
- 文本色同正常，透明度做渐隐

**▲ 徽章**

- 尺寸 10px，行尾靠右
- 颜色跟 TP 类型：`--tp-peak` / `--tp-valley` / `--tp-shift`
- hover 放大 1.2x（复用 §03 `transform: scale(1.2)` 动画）

**响应式（窄屏堆叠）**

- 视口宽度 ≥ 1280px：左右双列并排（65% / 35%）
- 视口宽度 < 1280px：`.ecg-row` 切 `flex-direction: column`，面板堆叠到主列下方，高度固定 420px
- 视口宽度 < 768px（移动）：面板 `display: none`（弹幕流不是核心内容；小屏用户主要看 §01-§03 文字洞察）——研究场景基本都在桌面，YAGNI

---

## §7 · 错误处理与降级

| 场景 | 表现 |
|---|---|
| `danmaku.json` 缺失 | 面板渲染占位 "弹幕数据未加载"，两 tab 禁用 |
| `danmaku.json` 为空数组 `[]` | 同上 |
| 极稀疏（< 20 条，SPARSE） | Follow 不居中直接显示全部；Browse 搜索框 placeholder 改为 "样本较少，全部显示" |
| `currentTime` 超出弹幕时间范围 | 空窗口 + 占位 "此时段无弹幕" |
| 搜索无命中 | 空态："未命中 '春晚' · 试试别的关键词" |
| `JSON.parse` 失败 | `console.error` + 面板 `display:none`，不破坏 §01-§05 |
| 无 `<video>`（非 `--with-video` 模式） | 布局保持 row，左列只剩 ECG 方格纸；Follow 绑定从 `video.timeupdate` 改为 ECG chart 的 `axisPointer` 变化事件；Tab 条说明文案改 "hover ECG 即跟随" |

**关键原则：** 面板失败绝不拖垮主报告。所有 Panel 相关入口包 `try-catch`，失败时 `display:none` 静默退出。§02 左列（video / ECG）继续独立渲染——研究员至少还能看到现有的主可视化。

---

## §8 · 测试策略

**Python 侧（`tests/`）**

- `test_stage5_render.py` 新增 case：
  - `danmaku_data` 正确 inline 到 `<script id="danmaku-data">`
  - TP `evidence.danmaku_id` 在 inline 数据里能查到
  - 内联体积 < 500 KB（警戒线）
- `test_render_report_smoke.py` 保留：旧报告仍能渲染（回归保护）

**前端单测（新增 `tests/frontend/`）**

使用现有 Python 测试 runner 或轻量 JS runner（Node.js）。候选方案：用 `vitest` 或手写断言。需在 writing-plans 阶段敲定。

- `test_panel_scroll.test.js`：mock 1886 条 → `scrollToCenter(300)` → 期望 scrollTop 符合
- `test_panel_filter.test.js`：关键词 "春晚" → filteredRows.length 符合
- `test_panel_follow_pause.test.js`：模拟 scroll → timeupdate 不触发 scrollTo
- `test_panel_virtual_render.test.js`：100k 条 → 可见 DOM 节点数 ≈ 16

**集成（手动 checklist）**

在 `docs/superpowers/specs/...` 留一个 checklist 小节，release 前跑一遍：

- ✅ 播放视频，Follow 每秒居中一次
- ✅ 点弹幕行，视频 seek、ECG markLine 移动
- ✅ 点 `▲` 徽章，§03 卡片滚到视口
- ✅ 切 Browse，搜索框 filter 实时
- ✅ Browse 点弹幕不切 tab
- ✅ 48 min 1886 条样本滚动无卡顿（BV1arcxz5Epf）
- ✅ SPARSE 样本（11 条）面板显示全部不报错
- ✅ 非 `--with-video` 模式，Follow 可 hover ECG 触发

---

## 开放问题

**无。** §1-§8 所有决策点已在 brainstorm 阶段闭环。

## 下一步

1. 调 writing-plans skill 生成实现计划
2. 计划应按以下阶段分解：
   - Phase A：数据层（`render_report.py` 注入 + 测试）
   - Phase B：虚拟滚动基础（只 Follow，不做 Browse）
   - Phase C：Browse 模式 + 搜索
   - Phase D：▲ 徽章 + TP 联动
   - Phase E：视觉打磨 + 响应式
   - Phase F：错误降级 + 集成测试
3. 建议分 2 个 PR：Phase A-B 合并后发 v0.4.0-alpha，Phase C-F 合并后发正式 v0.4.0
