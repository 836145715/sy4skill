---
name: sy4py
description: Parse and query SunnyNetV4 .sy4 capture files with the sy4py CLI (info, list, get, search, stats, streams, body, export). Use when the user gives a .sy4 path, asks to analyze SunnyNet / SunnyNetV4 capture records, 抓包记录, or wants offline querying without importing the file into the SunnyNet app.
---

# sy4 抓包记录分析（sy4py）

用 `sy4py` 只读解析 `.sy4`。不要启动 SunnyNet 主界面，不要把文件导入 `records_import`，也不要自己写解析器。

## 准备

```bash
python -m pip install sy4py
sy4py --version
```

未安装时退回源码运行：`pip install -e <repo>`，或 `PYTHONPATH=<repo>/src python -m sy4py ...`。

## 工作流

1. `info` — 总条数、协议分布、正文体积、是否压缩。
2. `list --noise` — 去掉 CDN / 304 / 图片字体 / 埋点；大文件加 `--limit 50`。
3. 用 `--host` / `--method` / `--url` / `--status` / `--e` 缩小到业务请求。
4. `search` 定位正文或头里的关键字，记下命中行的 `index`。
5. `get <index> --redact` 看头与摘要；正文用 `body`，优先 `--out` 落盘再按需读片段。
6. 对用户只汇报业务结论，不要粘贴 Cookie、Authorization、手机号、地址、支付单号。

`index` = 文件内从 1 开始的序号（`list` 第一列 `#`），不是主界面「序号」；
主界面序号保存在 `theology` 字段，可用 `--theology` 定位。

## 常用命令

```bash
sy4py info "capture.sy4"
sy4py list "capture.sy4" --noise --method POST --host api.example.com
sy4py list "capture.sy4" --e "status=401 or status=403" --json
sy4py search "capture.sy4" checkout --in url --noise
sy4py stats "capture.sy4" --noise --by host
sy4py get "capture.sy4" 509 --redact
sy4py body "capture.sy4" 509 --part resp --decompress --out resp.json
sy4py streams "capture.sy4" 457
sy4py export "capture.sy4" subset.sy4 --noise --status 200
```

所有查询命令都支持 `--json`，需要结构化结果时加上。结果中正文超过 2048 字节会被截断，
`get --json --full` 才输出完整内容。

## 筛选

- `--noise`：304、CDN、图片字体、埋点
- `--status 200,302` 或 `--e "status=401 or status=403"`
- `--error` 只匹配 Error 字段；无状态码用 `--no-status`
- `--wide` 显示完整 URL；`--limit` / `--offset` 分页
- 表达式：空格 AND，`or` / `||` OR，`=` 的值可用逗号 OR（`status=401,403`）

## 注意

- 不要把整段响应体直接打进对话（先 `--out` 再读片段）。
- 分享或截图前先 `--redact`，它会打码头里的 Cookie / Authorization / Token，
  以及 URL 中常见的 `token` / `session` / `sign` 等查询参数。
- 不要把真实 `.sy4` 提交进仓库（项目 `.gitignore` 已忽略 `*.sy4`）。
- 遇到 Brotli 压缩文件需要 `brotli` 依赖；`pip install sy4py` 已自动带上。

完整参数、JSON 结构见 [references/flags.md](references/flags.md)。
