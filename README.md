# sy4py

[![CI](https://github.com/YOURNAME/sy4py/actions/workflows/ci.yml/badge.svg)](https://github.com/YOURNAME/sy4py/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sy4py.svg)](https://pypi.org/project/sy4py/)
[![Python](https://img.shields.io/pypi/pyversions/sy4py.svg)](https://pypi.org/project/sy4py/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

用纯 Python 读取、筛选和导出 **SunnyNetV4 抓包文件（`.sy4`）**。
**本仓库本身就是一个 Agent Skill**：克隆到 skills 目录即可使用，不需要 `pip install`、不需要启动 SunnyNet。

- **技能即仓库**：根目录 `SKILL.md` 定义技能，`scripts/` 里是自带 CLI，装完直接跑。
- **只读、离线**：不导入 SunnyNet 主界面，不依赖 GUI。
- **完整覆盖**：HTTP / WebSocket / TCP / UDP，含 WebSocket 与流式帧。
- **自动解压**：SunnyNet 默认 Brotli 压缩，自动识别，也兼容未压缩文件。
- **筛选与表达式**：`--host/--method/--status/--noise` 与 `--e "status=401 or status=403"`。
- **JSON 输出**：所有查询命令支持 `--json`，方便脚本与 Agent 消费。
- **安全默认**：`--redact` 打码 Cookie、Authorization、Token 类头与 URL 凭据参数。

## 安装

```powershell
# 作为 Agent Skill：直接克隆进 skills 目录
git clone https://github.com/YOURNAME/sy4py.git $env:USERPROFILE\.dsh\skills\sy4py
```

```bash
# Linux / macOS
git clone https://github.com/YOURNAME/sy4py.git ~/.dsh/skills/sy4py
```

也可以当普通 Python 包安装（可选）：

```bash
pip install sy4py            # 发布到 PyPI 后可用，提供 sy4py 命令
```

运行时依赖只有 `brotli`（真实 `.sy4` 默认 Brotli 压缩）：

```bash
python -c "import brotli" || python -m pip install brotli
```

## 使用

技能目录下直接运行，无需安装：

```bash
python scripts/sy4py info capture.sy4
python scripts/sy4py list capture.sy4 --noise --limit 30
python scripts/sy4py list capture.sy4 --noise --host api.example.com --method POST
python scripts/sy4py search capture.sy4 checkout --in url --noise
python scripts/sy4py stats capture.sy4 --noise --by host
python scripts/sy4py get capture.sy4 509 --redact
python scripts/sy4py body capture.sy4 509 --part resp --decompress --out resp.json
python scripts/sy4py export capture.sy4 subset.sy4 --noise --status 200
```

不在技能目录时用绝对路径：`python D:\skills\sy4py\scripts\sy4py info capture.sy4`。
装过 pip 包或设置了 `PYTHONPATH=scripts` 时，`sy4py ...` 与 `python -m sy4py ...` 等价。

| 命令 | 作用 |
| --- | --- |
| `info` | 条数、协议分布、正文体积、是否压缩 |
| `list` | 记录列表（`--wide` 显示完整 URL） |
| `get` | 单条记录详情（`--full` 不截断正文） |
| `search` | 全字段搜索，输出命中字段与上下文 |
| `stats` | 汇总或 `--by host\|method\|status\|process\|type` |
| `streams` | WebSocket / TCP / UDP 帧列表 |
| `body` | 提取请求体 / 响应体 / 指定帧 |
| `export` | 导出 `.sy4`（可压缩）或 JSONL |

`index` 是**文件内从 1 开始的序号**（`list` 第一列 `#`），不是 SunnyNet 主界面的序号；
主界面序号保存在 `theology` 字段，可用 `--theology` 定位。

完整参数见 [references/flags.md](references/flags.md)，二进制格式见 [references/format.md](references/format.md)。

## 仓库结构

```
sy4py/
├── SKILL.md              # 技能入口（name + description + 工作流）
├── scripts/
│   ├── sy4py/            # 解析器与 CLI（自带，无需安装）
│   └── build_skill.py    # 打包成 dist/sy4py.skill
├── references/
│   ├── flags.md          # 完整参数、JSON 结构、退出码
│   └── format.md         # .sy4 二进制格式说明
├── tests/
└── .github/workflows/ci.yml
```

打包成单个 `.skill` 分发：

```bash
python scripts/build_skill.py     # -> dist/sy4py.skill
```

## 与 Go 版 `sy4` 的关系

字段顺序、压缩嗅探和统计口径对齐 SunnyNetTools 仓库里的 Go 实现（`sy4` 包 + `cmd/sy4`），
并用真实抓包逐条比对：记录数、类型分布、`bodyBytes`、`byHost/byMethod/byStatus` 完全一致，
`body` 导出字节哈希一致，`export` 出的 `.sy4` 能被 Go 版正常读取。

Python 版额外提供：`--decompress` 自动解压 gzip/deflate/br、GBK/GB18030 文本识别、
URL 凭据参数打码、`export --full` 带正文的 JSONL。

## 开发

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
# 有真实样本时（注意隐私，不要提交）
SY4_SAMPLES=/path/to/captures python -m pytest tests/test_samples.py -q
```

## 发布前

1. 把 `README.md`、`pyproject.toml`、`CONTRIBUTING.md` 里的 `YOURNAME` 换成 GitHub 用户名。
2. 替换 `LICENSE` 的版权人。
3. `git init`（已初始化可跳过）后 `git remote add origin https://github.com/YOURNAME/sy4py.git && git push -u origin main`。
4. 需要发布 PyPI 时：`python -m build && twine upload dist/*`。

## 安全提示

抓包文件常含 Cookie、Token、手机号、地址。不要整段粘贴响应体，分享前先 `--redact`；
`.gitignore` 已忽略 `*.sy4`，避免误提交真实流量。

## License

MIT
