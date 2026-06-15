# 扫码登录 + 凭证缓存 — 让全量弹幕获取对用户无感

date: 2026-06-15
status: approved
context: 当前解锁全量历史/登录态弹幕依赖用户手动从浏览器 Cookie 里抠出 `SESSDATA` 并设进环境变量 `BILI_SESSDATA`。普通用户几乎做不到。需要一种「几乎无感」的自动获取凭证方式。

## 问题

`src/emoekg/_lib/danmaku_client.py` 的 `_build_credential()` 只读环境变量 `BILI_SESSDATA`：

```python
sessdata = os.environ.get("BILI_SESSDATA", "").strip()
if not sessdata:
    return None
```

无凭证 → 回退游客实时池（弹幕量受限）。门槛在于「拿到 SESSDATA」这一步对非技术用户不可行。

## 目标与范围

**目标**：用户首次手机扫码即可解锁登录态弹幕，凭证本地缓存长期复用，之后零操作。

**运行环境**：本地 Agent 对话环境（用户机器有终端，能看到 `run_terminal_cmd` 输出，手机可扫码）。

**范围内**：
- 扫码登录获取凭证（`bilibili_api.login_v2.QrCodeLogin`，WEB 渠道）
- 凭证本地缓存 + 过期判断 + 失效重扫
- 四层回退的凭证解析
- CLI：`prepare` 自动触发、`--no-login` 跳过、`emoekg login` 手动刷新

**范围外**：
- 账号密码 / 短信登录（扫码已够，YAGNI）
- 服务器/网页后端部署形态（本次只解本地）
- 凭证加密存储（本地单用户场景，文件权限收紧即可；不引入额外密钥管理）

## 设计

### 凭证四层回退

`resolve_credential(allow_login: bool = True)` 按序尝试，返回 `Credential | None`：

```
1. 本地缓存   ~/.emoekg/credential.json   存在 & 未过期 & 字段完整 → 用
2. 环境变量   BILI_SESSDATA               兼容现有用法 → 用（并写入缓存供下次复用）
3. 扫码登录   allow_login=True 时：终端打印二维码 → 手机扫 → 拿凭证 → 存盘
4. 返回 None  以上都不可用 → 调用方静默回退游客实时池
```

### 新增模块 `src/emoekg/_lib/auth.py`

单一职责：凭证的获取/缓存/登录。`danmaku_client.py` 只调用 `resolve_credential()`，不关心来源。

| 函数 | 签名 | 职责 |
|---|---|---|
| `_cache_path()` | `() -> Path` | 返回 `~/.emoekg/credential.json`（`Path.home()`），目录不存在则创建 |
| `load_cached_credential()` | `() -> Credential \| None` | 读缓存 JSON；校验 `sessdata` 非空 + `saved_at` 未超过 `_MAX_AGE_DAYS`（25）；任一不满足返回 None |
| `save_credential(cred)` | `(Credential) -> None` | 写 `{sessdata, bili_jct, buvid3, dedeuserid, saved_at}`；尽量 `chmod 0600`（Windows 上 best-effort，失败忽略） |
| `qrcode_login(timeout=120)` | `(int) -> Credential \| None` | 见下「扫码流程」；成功后 `save_credential` 并返回；超时/失败返回 None |
| `clear_cache()` | `() -> None` | 删除缓存文件（运行期检测到凭证失效时调用） |
| `resolve_credential(allow_login=True)` | `(bool) -> Credential \| None` | 串起四层回退 |

### 扫码流程（`qrcode_login`）

基于 `bilibili_api.login_v2`：

```python
from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginChannel, QrCodeLoginEvents

login = QrCodeLogin(platform=QrCodeLoginChannel.WEB)
await login.generate_qrcode()
print(login.get_qrcode_terminal())          # 终端 ASCII 二维码
print("[emoekg] 请用 Bilibili App 扫码登录（约2分钟内完成）…")

deadline = time.time() + timeout
while time.time() < deadline:
    state = await login.check_state()         # QrCodeLoginEvents
    if state == QrCodeLoginEvents.DONE:
        cred = login.get_credential()
        save_credential(cred)
        return cred
    if state == QrCodeLoginEvents.TIMEOUT:    # 二维码本身过期
        return None
    time.sleep(2)
return None                                    # 整体超时
```

- 用 `_run`（`danmaku_client` 已有的 asyncio→sync 桥）包裹协程，保持同步接口
- 状态 `SCAN`（已扫未确认）/`CONF`（待确认）只打印一次提示，继续轮询
- 整个过程阻塞当前 CLI 调用 ~最多 `timeout` 秒；超时返回 None，不抛异常

### 缓存文件格式 `~/.emoekg/credential.json`

```json
{
  "sessdata": "...",
  "bili_jct": "...",
  "buvid3": "...",
  "dedeuserid": "...",
  "saved_at": 1750000000
}
```

- `saved_at`：unix 秒。`load_cached_credential` 校验 `now - saved_at < 25*86400`
- 缺 `sessdata` 或解析失败 → 视为无效，返回 None（不崩）

### 运行期失效兜底

`fetch_all_danmakus` 历史/登录态请求若抛出鉴权类错误（如 bilibili-api 的 `-101 账号未登录` / `ResponseCodeException`）：
- 调 `clear_cache()` 删除过期缓存
- 本次静默回退游客实时池（不中断分析）
- 下次运行 `resolve_credential` 时缓存已空 → 自然走扫码

### CLI 改动（`cli.py`）

- `prepare` / `run`：调用链最终走到 `resolve_credential(allow_login=not args.no_login)`
  - 新增 flag `--no-login`：跳过扫码（无人值守/CI），等价只用 缓存+环变量+游客池
- 新增子命令 `emoekg login`：强制走 `qrcode_login()` 刷新缓存并打印结果（已登录/失败），不跑分析
- 默认行为：无有效凭证时自动打印二维码——这就是「无感」的核心：用户跑 `prepare` 时顺手扫一下，之后再不用管

### danmaku_client.py 改动

`_build_credential()` 替换为：

```python
from emoekg._lib.auth import resolve_credential

def _build_credential(allow_login: bool = True):
    return resolve_credential(allow_login=allow_login)
```

`fetch_all_danmakus` 增加参数 `allow_login: bool = True` 透传；Stage 1 (`fetch_danmaku.run`) 透传 CLI 的 `--no-login`。

## 测试

- `tests/test_auth.py`（新增）：
  - `save_credential` + `load_cached_credential` 往返一致
  - 过期缓存（`saved_at` 很旧）→ `load_cached_credential` 返回 None
  - 缺字段 / 坏 JSON → 返回 None，不抛
  - `resolve_credential`：mock 掉 `qrcode_login`，验证四层优先级（缓存 > 环变量 > 登录 > None）
  - `clear_cache` 删除文件
  - **扫码本身不写真实网络测试**：`qrcode_login` 内部 `QrCodeLogin` 用 monkeypatch 注入假状态机，验证 DONE/TIMEOUT 分支
- `tests/test_danmaku_client.py`：`_build_credential` 改为委托 `resolve_credential`，更新相关断言
- `tests/test_cli.py`：`--no-login` flag 解析；`login` 子命令存在且调用 `qrcode_login`

## 影响面

- 新增 `_lib/auth.py`（~120 行）+ `tests/test_auth.py`
- 改 `danmaku_client.py`（`_build_credential` 委托 + `allow_login` 透传）
- 改 `fetch_danmaku.py`（透传 `allow_login`）
- 改 `cli.py`（`--no-login` flag + `login` 子命令）
- 改 `SKILL.md`（说明扫码登录的新流程，替换「手动设 SESSDATA」叙述）
- `~/.emoekg/` 是运行期目录，不入库

## 向后兼容

- `BILI_SESSDATA` 环境变量仍受支持（第 2 层），现有用法不破
- 已有报告/缓存缺失 → 自然走扫码或游客池，不报错
