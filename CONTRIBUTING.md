# Contributing

Thanks for taking a look at `sy4py`!

## 开发环境

```bash
git clone https://github.com/YOURNAME/sy4py.git
cd sy4py
python -m pip install -e ".[dev]"
python -m pytest -q
```

## 代码约定

- 只支持 Python 3.9+；不要使用 `match`、`X | None` 运行时注解等 3.10 语法
  （文件顶部可以 `from __future__ import annotations`）。
- 解析层（`decoder.py` / `encoder.py`）的字段顺序必须与 `docs/FORMAT.md` 一致；
  改字段顺序时同步修改测试与文档。
- 新增 CLI 参数时，`cli.py` 的 `BOOL_FLAGS` / `VALUE_FLAGS` 与 `USAGE` 一起更新。
- 不提交真实抓包文件；本地验证用环境变量指向样本目录：

```bash
SY4_SAMPLES=/path/to/captures python -m pytest tests/test_samples.py -q
```

## 提交 PR

1. 补充或更新测试（`tests/`）。
2. 确认 `python -m pytest -q` 全绿。
3. 说明动机与行为变化，必要时附上一小段脱敏后的输出。
