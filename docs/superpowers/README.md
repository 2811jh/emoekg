# `docs/superpowers/` — Historical Archive

> ⚠️ **不再维护 — 仅作历史留痕**

本目录是 emoekg 开发过程中由 [superpowers skill](https://github.com/anthropics/courses/tree/master/tool_use) 自动生成的 specs 与 plans 文档归档，对应于 v0.4.0 之前「弹幕侧栏」方案的设计与实施记录。

## 内容

| 文件 | 时刻 | 主题 |
|---|---|---|
| [`specs/2026-05-09-danmaku-sidebar-design.md`](specs/2026-05-09-danmaku-sidebar-design.md) | 2026-05-09 | 弹幕侧栏组件设计 spec（虚拟滚动 + 8 维过滤） |
| [`plans/2026-05-11-v0.4.0-danmaku-panel.md`](plans/2026-05-11-v0.4.0-danmaku-panel.md) | 2026-05-11 | v0.4.0 弹幕面板实施计划 |

## 为什么保留？

v0.4.0 弹幕侧栏方案上线后，用户反馈"驾驶舱旁边不该是滚动列表"，方案被 v0.4.2 的 [Cockpit Console](../../2026-05-07-emoekg-design.md#15-v04x-实施回顾--cockpit-console2026-05-11) 重构取代（决策记录见 design.md §15 D7）。

这两份文档是**被替代方案**的完整记录，对**理解为什么不那样做**有价值：
- 看到了什么问题
- 试图怎么解决
- 为什么失败
- 怎么演进到当前架构

> **不要根据本目录的文件做新功能决策** —— 当前架构请阅读 [`README.md`](../../README.md) 与 [`design.md` §15`](../2026-05-07-emoekg-design.md)。
