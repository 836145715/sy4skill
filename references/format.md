# `.sy4` 文件格式

本文记录 SunnyNetV4 记录文件（`.sy4`）的二进制布局，供实现与排错参考。
结论来自对 SunnyNetTools 仓库 Go 实现的逐字段对照，以及真实抓包文件的验证。

## 1. 整体结构

```
+---------------------------+
| u64 record_count          |  文件头：记录条数（不一定等于实际可解析条数）
+---------------------------+
| record 0                  |
| record 1                  |
| ...                       |
+---------------------------+
```

每个 record 以 **1 字节类型** 开头：

| 字节 | 类型 |
| --- | --- |
| `0x31` (`"1"`) | HTTP / WebSocket 会话 |
| `0x32` (`"2"`) | TCP 会话 |
| `0x33` (`"3"`) | UDP 会话 |

解析到 EOF 即结束；出现未知类型字节视为数据损坏。

## 2. 基本编码

所有整数都是 **8 字节大端无符号**（`u64`），没有变长整数、没有长度补位。

| 名称 | 编码 |
| --- | --- |
| `int` | 8 字节 big-endian |
| `bool` | 1 字节，非 0 为真 |
| `string` | `int` 字节数 + UTF-8 原始字节（长度为 0 表示空串） |
| `body` | `int` 字节数 + 原始字节（二进制安全） |
| `header` | `int` 条目数，然后每项：`string key` + `int 值个数` + N 个 `string` |
| `int array` | `int` 元素个数 + N 个 `int` |

实现上建议给字段长度设上限（Go 版为 256 MiB、数组 5,000,000），避免损坏文件导致巨量分配。

## 3. 压缩

SunnyNet 默认对整份文件做 **Brotli** 压缩（没有额外头、没有 magic，直接就是 brotli 流）。
判断方式：

1. 读前 8 字节当作 `record_count`，若数值合理（≤5,000,000）且第 9 字节是 `1/2/3`，
   视为**未压缩**；
2. 否则尝试 Brotli 解压，再解析并做合理性校验（条数合法、有头无记录视为不可信）；
3. 仍失败则按未压缩解析，报错。

因此读取顺序是「先嗅探、后解析」，不能假设文件一定压缩。

## 4. HTTP 记录（类型 `"1"`）

字段顺序（严格）：

```
int    theology        # SunnyNet 主界面的「序号」
string ico             # 进程图标（base64/路径等，工具不解释）
--- request ---
string method
string url
string clientIP        # 形如 127.0.0.1:50000
string time            # 形如 09-43-31:090
string processName
string proto           # HTTP/1.1
header header
body   body
int    bodyLength
bool   isMaxLength
--- response ---
string time
string code            # "200"
string state
string type            # content-type
int    length
string proto
header header
body   body
string responseType
string serverIP
int    bodyLength
bool   isMaxLength
--- 其它 ---
string error
int    state
int    recLength
int    senLength
string note
frame[] streams        # 见 §7
int[]  streamKeys
bool   isWebsocket
bool   websocketDisconnect
string userName
```

## 5. TCP 记录（类型 `"2"`）

```
int    theology
string method
string ico
string note
string clientIP
string process
string remoteAddress   # 10.0.0.2:443
string host
string time
int    recLength
int    senLength
frame[] streams        # 见 §7（流帧顺序与 WS 帧不同）
int[]  streamKeys
string userName
```

## 6. UDP 记录（类型 `"3"`）

```
int    theology
string method
string ico
string note
string clientIP
string process
string remoteAddress
string time
int    recLength
int    senLength
frame[] streams
int[]  streamKeys
string userName
```

注意 UDP 没有 `host` 字段，主机名需从 `remoteAddress` 推断。

## 7. 帧（frame）

帧数组的结构是 `int 帧数`，然后每帧 `int key` + 帧体。帧体有两种**字段顺序不同**的变体：

WebSocket 帧（HTTP 记录里）：

```
int    messageId
bool   isSend
bool   isActiveSend
string time
body   body
int    websocketType
bool   isClose
```

TCP / UDP 流帧：

```
int    messageId
bool   isSend
bool   isActiveSend
string time
body   body
bool   isClose
int    websocketType
```

即最后两个字段顺序相反——写解析器时最容易在这里错位。
`isActiveSend` 为真表示「手动发送」，`isClose` 为真表示该帧是连接关闭标记。

## 8. 派生字段

文件里没有直接存 `host` / `path` / `status` 等字段，需要从请求 URL 和响应码推导：

- `host` = URL 的 authority（去掉 userinfo）
- `path` = URL path，`query` = URL query
- `status` = response.code
- `kind` = `isWebsocket ? "websocket" : "http"`
- 若 WebSocket 的 method 为空，工具显示为 `"WS"`
- TCP 的 `url` = `host`，为空则用 `remoteAddress`

`index` 是解析时按文件顺序赋的 1 基序号，**不要**和 `theology` 混用。

## 9. 参考实现

- Go：SunnyNetTools 仓库 `sy4/` 包与 `cmd/sy4`
- Python：本仓库 `scripts/sy4py/decoder.py`、`scripts/sy4py/encoder.py`

两边的字段顺序、限制值和统计口径保持一致；`sy4py export` 产物可直接被 Go 版读取。
