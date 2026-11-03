# sy4py

[![CI](https://github.com/YOURNAME/sy4py/actions/workflows/ci.yml/badge.svg)](https://github.com/YOURNAME/sy4py/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sy4py.svg)](https://pypi.org/project/sy4py/)
[![Python](https://img.shields.io/pypi/pyversions/sy4py.svg)](https://pypi.org/project/sy4py/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

用纯 Python 读取、筛选和导出 **SunnyNetV4 抓包文件（`.sy4`）**。零逆向、零 GUI 依赖：
一条命令就能看清一个 `.sy4` 里有什么、某次请求的完整头/体、以及某个关键字出现在哪。

- **只读、离线**：不需要启动 SunnyNet，也不会把文件导入任何主界面。
- **完整覆盖**：HTTP / WebSocket / TCP / UDP 四类记录，含 WebSocket 与流式帧。
- **自动解压**：SunnyNet 默认用 Brotli 压缩，`sy4py` 自动识别（也兼容未压缩文件）。
- **筛选与表达式**：`--host/--method/--status/--noise`，以及 `--e "status=401 or status=403"`。
- **JSON 输出**：所有查询命令支持 `--json`，方便脚本 / 爬虫 / Agent 消费。
- **安全默认**：`--redact` 自动打码 Cookie、Authorization、Token 类请求头与查询参数。

## 安装

```bash
pip install sy4py          # 发布到 PyPI 后可用
# 从源码安装
pip install -e ".[dev]"
```

需要 Python 3.9+，唯一运行时依赖是 `brotli`。

## 快速开始

```bash
# 1. 先看文件概览：条数、协议分布、正文体积
sy4py info capture.sy4

# 2. 列请求，去掉 CDN / 静态资源 / 埋点噪声
sy4py list capture.sy4 --noise --limit 30

# 3. 只关心某个域名上的 POST
sy4py list capture.sy4 --noise --host api.example.com --method POST

# 4. 搜索关键字落在哪个字段
sy4py search capture.sy4 checkout --in url --noise

# 5. 看某条记录的请求/响应头和正文（自动打码敏感头）
sy4py get capture.sy4 509 --redact

# 6. 把某个响应体原样导出（可选 gzip/br 解码）
sy4py body capture.sy4 509 --part resp --decompress --out resp.json

# 7. 统计
sy4py stats capture.sy4 --noise --by host

# 8. 导出子集，供他人或其它工具继续分析
sy4py export capture.sy4 subset.sy4 --noise --status 200
sy4py export capture.sy4 records.jsonl --limit 100 --full
```

`info` 的输出示例：

```text
File: capture.sy4
Compressed: yes
Header count: 779
Parsed: 779
http=761  websocket=2  tcp=16  udp=0  errors=48  frames=41  body=37.2MB
```

## 命令一览

| 命令 | 作用 |
| --- | --- |
| `info <file>` | 文件头、实际解析条数、协议/正文统计 |
| `list <file>` | 记录列表（`--wide` 显示完整 URL） |
| `get <file> <index>` | 单条记录详情（`--full` 不截断正文） |
| `search <file> <needle>` | 全字段搜索，输出命中字段与上下文片段 |
| `stats <file>` | 汇总，或 `--by host|method|status|process|type|client|server|user` |
| `streams <file> <index>` | WebSocket / TCP / UDP 帧列表 |
| `body <file> <index>` | 提取请求体 / 响应体 / 指定帧（`--out` 落盘） |
| `export <file> <out.sy4\|out.jsonl>` | 导出为 sy4（可压缩）或 JSONL |

`index` 是**文件内从 1 开始的序号**（`list` 的第一列 `#`），不是 SunnyNet 主界面的「序号」；
后者保存在记录的 `theology` 字段里，可用 `--theology` 定位。

## 筛选

所有筛选条件可以组合（AND），逗号表示 OR：

| 参数 | 说明 |
| --- | --- |
| `--type http\|ws\|tcp,udp` | 协议类型，逗号分隔 |
| `--method GET,POST` | 方法，精确匹配（忽略大小写） |
| `--host apple.com` | 主机，子串匹配 |
| `--url /v1/order` / `--path /v1` | URL / 路径子串 |
| `--status 200,302` | 状态码 |
| `--process chrome` | 进程名子串 |
| `--client 127.0.0.1` / `--server 10.0.0.` | 客户端 / 服务端地址 |
| `--note 关键字` / `--user 账号` | 注释 / 用户名 |
| `--error` | 仅保留 Error 非空的记录 |
| `--no-status` | 仅保留没有状态码的记录（未完成/中断） |
| `--noise` | 去掉 304、CDN、图片字体、埋点等噪声 |
| `--min-body 1024` | 正文总字节数下限 |
| `--limit N` / `--offset N` | 分页 |

### 表达式 `--e`

空格是 AND，`or` / `||` 是 OR，值可以用逗号列举：

```bash
sy4py list capture.sy4 --e "status=401 or status=403"
sy4py list capture.sy4 --e "host~api type=http status>=500"
sy4py list capture.sy4 --e "process~chrome frames>0"
```

可用字段：`type method host url path status process client server note user error
index theology rec sen frames`；运算符：`=` `!=` `~` `!~` `>` `<` `>=` `<=`。

## JSON 输出

```bash
sy4py info capture.sy4 --json
sy4py list capture.sy4 --json --noise
sy4py get capture.sy4 509 --json --redact
sy4py search capture.sy4 checkout --json
sy4py stats capture.sy4 --json
sy4py streams capture.sy4 457 --json
```

`get --json` 的正文规整为：可打印文本直接给字符串，二进制给
`{"encoding": "hex", "data": "..."}`；超过 2048 字节默认截断，加 `--full` 输出完整内容。

## Python API

```python
from sy4py import open_file, Query, search, SearchOptions

archive = open_file(r"D:\captures\demo.sy4")
print(archive.header_count, len(archive), archive.compressed)

# 声明式筛选
query = Query(host="api.example.com", method="POST", skip_noise=True, limit=20)
for record in query.apply(archive.records):
    print(record.index, record.status, record.url, record.body_size)

# 搜索
hits = search(archive.records, "checkout", SearchOptions(scope="url"))
for hit in hits:
    print(hit.index, hit.field, hit.snippet)

# 直接取正文
record = archive.by_index(509)
open("resp.json", "wb").write(record.resp_body)
```

也可以自己拼装记录并写出 `.sy4`（用于造测试数据）：

```python
from sy4py import Record, HTTPSession, HTTPRequest, HTTPResponse, write_file

record = Record(http=HTTPSession(
    request=HTTPRequest(method="GET", url="https://example.com/", proto="HTTP/1.1"),
    response=HTTPResponse(code="200", type="text/plain", body=b"hello"),
))
write_file("made.sy4", [record], compress=True)
```

## 数据安全

抓包文件里通常有 Cookie、Token、手机号、地址等敏感信息：

- 默认**不要把整个响应体打进对话或日志**，先 `--out` 落盘再按需读取片段。
- 分享/截图前使用 `--redact`，它会打码 `Cookie`、`Set-Cookie`、`Authorization`
  以及名字含 `token` / `session` 的头，并打码 URL 中常见的凭据查询参数。
- `.gitignore` 默认忽略 `*.sy4`，避免误把真实流量提交到 GitHub。

## 与 Go 版 `sy4` 的关系

本项目的字段顺序、压缩嗅探和统计口径对齐 SunnyNetTools 仓库里的 Go 实现
（`sy4` 包 + `cmd/sy4`），并已用真实抓包文件逐条比对：
记录数、类型分布、`bodyBytes`、`byHost/byMethod/byStatus` 分组完全一致，
`body` 导出的字节哈希一致，`export` 出的 `.sy4` 也能被 Go 版正常读取。

Python 版额外提供了：`--decompress` 自动解压 gzip/deflate/br、GBK/GB18030 文本识别、
URL 凭据参数打码、`export --full` 带正文的 JSONL。

二进制格式细节见 [docs/FORMAT.md](docs/FORMAT.md)。

## 作为 Agent Skill 使用

仓库根目录的 [`SKILL.md`](SKILL.md) 可以直接放进 Agent 的 skills 目录，
让助手按固定工作流分析 `.sy4`（先 `info`，再 `list --noise`，再 `search` 定位，最后 `get/body`）。

## 开发

```bash
git clone https://github.com/YOURNAME/sy4py.git
cd sy4py
python -m pip install -e ".[dev]"
python -m pytest -q
# 有真实样本时（注意隐私，不要提交）
SY4_SAMPLES=/path/to/captures python -m pytest tests/test_samples.py -q
```

## 上传到 GitHub 前

把下面这些占位符替换掉即可发布：

1. `pyproject.toml` 与 `README.md` 中的 `YOURNAME`（GitHub 用户名）。
2. `LICENSE` 里的版权人。
3. `pyproject.toml` 中的 `version`（后续用 tag 发版）。

```bash
git init
git add .
git commit -m "feat: initial sy4py release"
git branch -M main
git remote add origin https://github.com/YOURNAME/sy4py.git
git push -u origin main
```

构建并发布到 PyPI：

```bash
python -m pip install build twine
python -m build
twine upload dist/*
```

## English

`sy4py` parses SunnyNetV4 `.sy4` capture files (Brotli-compressed by default) in pure
Python: HTTP, WebSocket, TCP and UDP sessions, with filtering, full-text search,
body extraction and JSON export. CLI: `info`, `list`, `get`, `search`, `stats`,
`streams`, `body`, `export`. See `sy4py --help` for flags; `--json` is available on
every query command.

## License

MIT
