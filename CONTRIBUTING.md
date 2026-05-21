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

## 自选筛选（观察池）

- **不是荐股**：输出 `watch_pool` / `watch_pullback`，禁止「优先推荐」措辞
- Playbook：`skill/playbooks/watchlist-screen.md`
- 配置：`config/watchlist.yaml` → `screening_policy`，`config/themes.yaml`
- 命令：`python cli.py --screen-watchlist [--max N]`
- 风险审计：`python cli.py --audit-watchlist` → `core/watchlist_risk_audit.py`
- 逻辑：`core/screen_watchlist.py`（勿新增未登记临时脚本）

## 本地检查

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
python cli.py --validate-pack sample/market_pack.sample.json
python cli.py --screen-watchlist --max 5   # 需 TUSHARE_TOKEN
```
