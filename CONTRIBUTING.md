# Contributing

## 改分析逻辑

优先改 `skill/lenses/*.md` 与 `skill/reference/phase-definitions.md`。

## 改数据

- 指数列表：`config/indices.yaml`
- 适配器注册：`adapters/registry.yaml`
- 行情拉取：`adapters/tushare_market.py`（委托 `core/fetch_live.py`）
- 衍生指标：`core/hints.py`（仅数字，不含买卖信号）

## 改报告

- Jinja 模板：`engine/report/templates/*.j2`
- 上下文构建：`core/report_context.py`

## 本地检查

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
python cli.py --validate-pack sample/market_pack.sample.json
```
