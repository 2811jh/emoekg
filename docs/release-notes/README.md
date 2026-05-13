# Release Notes

详细的单版本发布说明（按 SemVer 命名）。

> **CHANGELOG vs release notes**：
> - [`docs/CHANGELOG.md`](../CHANGELOG.md) — 浓缩版，每版一段，便于快速翻看
> - 本目录 — 长版，含动机 / 实现细节 / 兼容性说明 / 升级建议

## 索引

| 版本 | 主题 | 文件 |
|---|---|---|
| v0.4.1 | Iframe 跨域同步现实化 | [`v0.4.1.md`](./v0.4.1.md) |
| v0.4.0 | Cockpit Console 首版（弹幕侧栏 → vital readout） | [`v0.4.0.md`](./v0.4.0.md) |
| v0.3.1 | yutto 集成 + 弹幕 client bug 回归 | [`v0.3.1.md`](./v0.3.1.md) |
| v0.3.0 | `--with-video` 本地 mp4 模式 + Live Trace 脉冲 | [`v0.3.0.md`](./v0.3.0.md) |

> v0.4.2 之后的小版本（v0.4.2 ~ v0.4.10）只在 [`docs/CHANGELOG.md`](../CHANGELOG.md) 维护，不再每版单写长 release note，迭代节奏太快不值得。

## 命名规范

- 文件名 = `v<MAJOR>.<MINOR>.<PATCH>.md`（标准 SemVer）
- 历史上的 `RELEASE_NOTES_v0XX.md` 已统一迁移到本目录（v0.4.10 整理）
