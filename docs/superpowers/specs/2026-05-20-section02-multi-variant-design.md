# §02 Monitor 多 variant 升级设计

date: 2026-05-20
status: in-progress
context: BV1ChRQBsEQs 报告需提升 §02 视觉级别给领导汇报；不确定领导审美偏好，故并出 3 个变体让其挑选。

## 目标

§02「影像与心电 / Monitor」当前为：视频 + Vital Console + 8-DIM ECG 折线 + 6 卡 Vital Statistics。
观感"普通"，加入新模块 + 三种风格切换器，保留数据契约不变。

## 三个变体

### Variant A · Editorial（编辑报告风，默认）

沿用当前 Stripe Press × Pentagram 调性。在现有 §02 内追加：

- **Emotion Tape**（新模块）：8 行水平时间带，每行=一个 Plutchik 维度，每行内 58 个色块（chunk），透明度+高度双编码分数；顶部叠 turnpoint 三角标；左侧 70px 维度名标签；底部 0–28:31 时间刻度；hover 行高亮该维度。
- **Key Moments**（新模块）：8 张转折点高光卡，4×2 网格；每卡 = 编号 KM_01 + 类型徽章 + 时间码 + 主导情绪大字 + 8 维迷你横条 + JS 数值 + 1–2 条佐证弹幕；点击跳转视频。

### Variant B · Telemetry HUD（科幻仪表盘风）

A 全部模块在 B 模式下应用 HUD 主题层（仅 CSS 覆盖，不重排）：

- 视频上方角标：`LEAD I / SOURCE · n=551`
- 视频下方加 **Frame Scale 帧轴**（HUD 横条，0F–1711F 刻度，叠转折点小三角）
- Vital Console 头部改成 `LIVE TELEMETRY` + 大写英文 readout，主导情绪改 `DOMINANT // JOY 8.0`
- ECG 折线背景加薄扫描线网格 + acc 色 box outline
- 6 卡加 HUD 角标灯（左上+右下）
- Emotion Tape 块发光，turnpoint 三角加 acc 色 halo
- Key Moments 卡换 HUD 风：`KM_01 / READY @ 00:08:30` + 角部 L 形装饰 + 扫描线

### Variant C · Matrix（数据密集仪表风）

§02 内布局重排（仅在 C 时启用）：

- 顶部：video + Vital Console 并列（同 A）
- **新增**：`Chunks × Dims 大型热力网格`（58×8 矩阵，一眼看全片情绪密度分布）
- ECG 折线压缩到次要位置，作为底部"次仪表"
- Emotion Tape + 6 卡左右栅格摆放
- Key Moments 卡变薄改为单行紧凑栏（图3 状态事件表风）

## 切换机制

- **顶部固定切换器**：右上角浮动 `[A · Editorial] [B · HUD] [C · Matrix]`，当前选中带高亮
- 点击切换 → `body[data-variant="X"]` + 触发 ECharts resize + 重渲染 SVG 模块
- 默认 `data-variant="A"`，localStorage 记忆用户选择
- 切换器对其他 §（01/03/04/05）无影响

## 实现策略

**单 HTML 文件 + CSS variant overlay**：所有 variant 的 DOM 同时存在但 CSS 控制可见性/样式。优势：领导一份文件随意切换。劣势：HTML 体积稍增（+30KB 估算），可接受。

## 改动文件

- `src/emoekg/templates/report.html.j2`
  - 顶部加 variant switcher
  - §02 内嵌 Emotion Tape + Key Moments 两个新 DOM 块
  - §02 加 Frame Scale 帧轴 DOM（仅 B/C 显示）
  - C 专属：Chunks×Dims heatmap DOM
  - CSS 加 `body[data-variant="A|B|C"]` overlay 规则
- `src/emoekg/templates/app.js`
  - `renderEmotionTape()` — SVG 8 lanes
  - `renderKeyMoments()` — 8 卡 turnpoints
  - `renderFrameScale()` — HUD 帧轴（B/C）
  - `renderChunksHeatmap()` — 58×8 大热力（C）
  - `setupVariantSwitcher()` — 切换 + localStorage 持久化 + ECharts resize 重绘

数据来源：现有 `scores.json` + `turnpoints.json` + `danmakus.json`，不改 Python stages。

## 自检清单

- [ ] 切换 A/B/C 不报错，ECG 仍能 hover 跳转视频
- [ ] §03/04/05 三种 variant 下视觉一致
- [ ] 移动端（<860px）三种 variant 不出格
- [ ] 三种 variant 浏览器打开不卡顿（HTML <2MB）
