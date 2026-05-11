# emoekg v0.4.0 — DanmakuPanel

**Release date:** 2026-05-11

## Highlights

v0.4.0 introduces the **§02 inline DanmakuPanel** — a right-column panel adjacent to the ECG chart that lets researchers read the raw danmaku stream without leaving the section. Watching a peak on the ECG and wondering what 1886 people actually said at that moment? Now it's right there, scrolling with the playback.

### New

- **Follow mode** — Panel auto-centers ±20s around the current playback time (local video mode) or the ECG axis pointer (iframe mode)
- **Browse mode** — Full virtual-scrolled list with debounced text search and keyword underlay highlighting; designed to stay performant on 48-minute / 1886-danmaku samples
- **▲ TP evidence badges** — Danmakus cited as turnpoint evidence show a colored `▲` (peak / valley / shift); clicking jumps to the §04 TP card and flashes it, without seeking the video
- **Manual scroll detection** — Wheel / touch / keyboard arrow scrolling in Follow mode surfaces a "↓ 回到当前" button; any chart-triggered `seekAll` auto-resumes follow
- **SPARSE-aware** — Samples under 20 danmakus show all rows with an informative subtitle
- **Responsive** — Stacks under ECG at < 1280px, hidden at < 768px (Panel is desktop-research-grade; mobile users get §01-§05 unchanged)

### Changed

- `turnpoints.json` `evidence_danmakus[]` entries now include a `dm_index` field (0-based index into `danmaku.json`). This is additive and backward-compatible — older reports render fine, just without ▲ badges.
- `seekAll(t)` extended to also update `PanelStore.currentTime` and resume Follow mode; all existing callers work unchanged.

### Unchanged (coexistence)

- **§04 Analysis Danmaku stream** (`#danmaku-list`, `#dm-search`, `#dm-filter`) still works exactly as in v0.3.x. The two lists share the same `<script id="data-danmakus">` JSON embed but own independent UI state. The legacy list remains the recommended place to read danmakus per-dimension or per-TP; the new Panel is the place to read them next to the ECG peak that caught your eye.

## Upgrade notes

- If you regenerate old `emoekg_*_*/` working directories under v0.4.0, rerun `emoekg finalize --force` to pick up both the new Panel and the `dm_index` tagging in Stage 4.
- No breaking API changes. All existing CLI flags work identically.
- `__init__.py.__version__` was out of sync in v0.3.x (stuck at `"0.1.0"`); this release corrects it to match `pyproject.toml`.

## Known limitations

- iframe mode Follow relies on user hovering the ECG — it can't auto-advance with Bilibili playback (cross-origin iframe forbids reading `currentTime`). Use `--with-video` for full bidirectional sync.
- `▲` badge coloring assumes TP types in the canonical set (`peak` / `valley` / `shift`). Unknown types fall back to the peak color.
- Frontend unit tests are out of scope for this release; verification is handled by Python render tests (Stage 4 `dm_index` roundtrip, §02 DOM presence, §04 coexistence) plus a manual integration checklist in `docs/superpowers/specs/2026-05-09-danmaku-sidebar-design.md`.

## Test suite

194 pytest tests, all passing:
- Stage 1 / 2 / 4 / 5 full coverage preserved
- 3 new v0.4.0 tests: `test_render_includes_panel_root`, `test_render_preserves_legacy_danmaku_stream`, `test_render_preserves_dm_index_in_turnpoints`, `test_evidence_danmakus_include_dm_index`

## Spec / plan artifacts

- Spec: `docs/superpowers/specs/2026-05-09-danmaku-sidebar-design.md`
- Plan: `docs/superpowers/plans/2026-05-11-v0.4.0-danmaku-panel.md`
