---
name: sy4py
description: Parse and query SunnyNetV4 .sy4 capture files with the sy4py CLI (info, list, search, stats, get, body, streams, export). Use when the user gives a .sy4 path, asks to analyze SunnyNet / SunnyNetV4 capture records, 抓包记录, or wants offline querying without importing the file into the SunnyNet app.
---

# sy4 抓包记录分析（sy4py）

用 `sy4py` 只读解析 `.sy4` 文件。**不要**把文件导入 SunnyNet 主界面，也不要自己写解析器。

## 环境

```bash
pip install sy4py          # 或：pip install -e <repo>
sy4py --version
```

没有命令时退回模块方式：`python -m sy4py ...`。

## 工作流

1. `info` — 总条数、协议分布、正文体积、是否有压缩。
2. `list --noise` — 去掉 CDN / 304 / 图片字体 / 埋点；大文件加 `--limit 50`。
3. 用 `--host` / `--method` / `--url` / `--status` / `--e` 缩小到业务请求。
4. `search` 定位正文或头里的关键字，记下 `index`。
5. `get <index> --redact` 看头与摘要；正文用 `body`，需要时 `--out` 落盘再按需读片段。
6. 对用户只汇报业务结论，不要粘贴 Cookie、Authorization、取货联系人、支付单号。

`index` = 文件内从 1 开始的序号（`list` 第一列 `#`）。不是主界面「序号」，
主界面序号在 `theology` 字段，可用 `--theology` 定位。

## 常用命令

```bash
sy4py info "capture.sy4"
sy4py list "capture.sy4" --noise --method POST --host api.example.com
sy4py list "capture.sy4" --e "status=401 or status=403" --json
sy4py search "capture.sy4" checkout --in url --noise
sy4py stats "capture.sy4" --noise --by host
sy4py get "capture.sy4" 509 --redact
sy4py body "capture.sy4" 509 --part resp --decompress --out "$env:TEMP/resp.json"
sy4py streams "capture.sy4" 457
sy4py export "capture.sy4" subset.sy4 --noise --status 200
```

需要结构化结果时给所有查询命令加 `--json`。

## 筛选要点

- `--noise`：304、CDN、图片字体、埋点
- `--status 200,302` 或 `--e "status=401 or status=403"`
- `--error` 只匹配 Error 字段；无状态码用 `--no-status`
- `--wide` 显示完整 URL；`--limit` / `--offset` 分页
- 表达式：空格 AND，`or` / `||` OR，`=` 的值可用逗号 OR（`status=401,403`）

## 禁止

- 把整段响应体直接打进对话（先 `--out` 再读片段）。
- 输出 Cookie / token / 手机号 / 地址 / 支付订单号（分享前先 `--redact`）。
- 把真实 `.sy4` 提交进仓库（`.gitignore` 已忽略 `*.sy4`）。
