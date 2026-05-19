# Contributing

## 改分析逻辑

优先改 `lenses/*.md` 与 `docs/phase-definitions.md`，提 PR 说明推理框架变更。

## 改数据

- 指数列表：`config/indices.yaml`
- 拉取逻辑：`core/fetch_live.py`
- 衍生指标：`core/hints.py`（仅数字，不含买卖信号）

## 本地检查

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
python cli.py --validate-pack fixtures/market_pack.sample.json
```
