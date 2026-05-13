# emoekg v0.4.1 — DanmakuPanel hotfix

**Release date:** 2026-05-11

紧急修复 v0.4.0 上线后发现的 4 个关键问题。

## Fixed

### 🔴 布局塌陷（v0.4.0 最大问题）
v0.4.0 把 video + ECG + Panel 塞进一个 `.ecg-row` flex 容器，导致：
- ECG 方格纸图被挤到左列 65% 宽度内，无法看清曲线
- Panel 撑到整个 §02 section 高度，把 §03/§04/§05 挤到页面下方

**v0.4.1**：改为只让 video 和 Panel 并排（`.media-row`），ECG 恢复全宽独立放在下方。Panel 高度自动匹配 video（约 260–380 px），再长也不会影响整体滚动。

### 🔴 Follow 模式"Panel 是静态页面"
v0.4.0 的 `scrollToCenter` 仅设置 `viewport.scrollTop`，依赖浏览器 scroll 事件异步 re-render。当目标 scrollTop 与当前一致时，scroll 事件不 fire，整个列表看起来冻结。

**v0.4.1**：`scrollToCenter` 每次都**显式调用** `renderPanelList()` + `updateCurrentHighlight()`，不再依赖 scroll 事件。点击心电图/播放视频（local 模式）都能让 Panel 实时跟随。

### 🔴 viewport 最小高度把 overflow 堵死
v0.4.0 给 `.panel-viewport` 设了 `min-height: 400px`，但 `.danmaku-panel` 作为 flex 子项没有 `min-height: 0`，导致 flex column 计算出的高度把内部列表撑开，`overflow-y: auto` 无效。

**v0.4.1**：`.danmaku-panel` 和 `.panel-viewport` 都加 `min-height: 0`，允许 flex 子项缩小到比内容更小，overflow 正确生效。

### 🌏 全面中文化
- Tab 文案：`Follow / Browse` → `跟随 / 浏览`
- 副标题：`跟随视频播放时刻` → `跟随视频播放 / 点击心电图同步`
- 搜索框：`搜索弹幕文本...` → `搜索弹幕...`
- iframe 降级提示：`hover ECG 曲线即跟随` → `点击或悬停心电图同步`
- ▲ 徽章 title：`TP evidence · ...` → `此弹幕为情绪转折点佐证 · ...`
- 空数据占位：`弹幕数据未加载` → `暂无弹幕`
- 初始占位：`Panel mounting...` → `面板加载中…`

## Known non-issues (by design)

- iframe 模式（默认）下点击 bilibili iframe 内的视频**无法**触发 Panel 跟随——这是 Bilibili 跨域限制，不是 bug。解决办法：用 `--with-video` + 本地 mp4，或在报告里点击心电图来同步。

## Upgrade

```bash
pip install -e . --upgrade   # or re-clone tag v0.4.1
emoekg finalize -o /path/to/emoekg_BV*/ --force   # re-render existing reports
```

## Test suite

194 pytest tests, all passing（v0.4.0 测试从 `ecg-row`/`ecg-main` 更新到 `media-row`/`video-col`）。
