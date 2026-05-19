# `docs/` — 开发者文档总入口

按目的找文档：

## 我想…

### …了解当前架构怎么运转
→ [`../README.md`](../README.md) §「📁 项目结构」、§「🧬 How it works」、§「📑 文件清单」
→ [`../SKILL.md`](../SKILL.md) Agent 视角的工作流

### …学会 Stage 3 怎么打分（**AI Agent 必读**）
→ [`scoring_rubric.md`](./scoring_rubric.md)
> 8 维 0–10 分判据 / SPARSE 规则 / Insights Protocol / 自检清单

### …看每个版本变更
→ [`CHANGELOG.md`](./CHANGELOG.md)  （浓缩版，每版一段）
→ [`release-notes/`](./release-notes/)  （长版，含动机 / 升级建议）

### …了解最初决策为什么这样定（D1–D12）
→ [`2026-05-07-emoekg-design.md`](./2026-05-07-emoekg-design.md)
> §1–§14 是 v0.1.0 原始 spec（已 freeze）
> §15 是 v0.4.x Cockpit Console 实施回顾（含 D7–D12 新决策）

### …了解 v0.1.0 是怎么从 0 到 1 实现的
→ [`2026-05-07-emoekg-plan.md`](./2026-05-07-emoekg-plan.md)  **HISTORICAL ARCHIVE**
> 102KB 实施计划，所有 Task 1–15 已完成。仅作决策留痕。

### …了解 v0.4.x 之前被弃用的「弹幕侧栏」方案
→ [`superpowers/`](./superpowers/)  **HISTORICAL ARCHIVE**
> 被 v0.4.2 Cockpit Console 重构取代，保留以供「为什么不那样做」溯源

---

## 文档生命周期约定

| 文档 | 状态 | 是否随版本更新 |
|---|---|---|
| `scoring_rubric.md` | 🟢 active | 是（Stage 3 规则演进时） |
| `CHANGELOG.md` | 🟢 active | **每个 patch 版本都追加一段** |
| `release-notes/` | 🟢 partially active | 仅重大版本（v0.x.0）单写长 note |
| `2026-05-07-emoekg-design.md` §1–§14 | 🟡 frozen | 否（v0.1.0 spec 不动） |
| `2026-05-07-emoekg-design.md` §15 | 🟢 active | 是（重大重构追加新 §） |
| `2026-05-07-emoekg-plan.md` | 🔴 archived | 否 |
| `superpowers/` | 🔴 archived | 否 |

> **新增文档时的归属规则**：
> - 是某个具体 patch 版本的说明 → 写进 `CHANGELOG.md`
> - 是新的重大功能 spec → 在 `design.md` 追加 `§16+`
> - 是 v0.5.0+ 的实施计划 → 新建 `2026-MM-DD-vX.Y-<topic>-plan.md` 平级
> - 临时 brainstorm → 写完归到 `superpowers/`（甚至直接删，git log 已留痕）
