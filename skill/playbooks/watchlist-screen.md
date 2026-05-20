# Playbook: watchlist-screen（自选趋势观察池）

**不是选股/荐股。** 输出仅为 `watch_pool` / `watch_pullback` / `near_high_trim` / `wait` / `avoid`。

## 前置

1. 已配置 `config/watchlist.yaml`（含 `screening_policy`）
2. 已配置 `config/themes.yaml`、`config/my_discipline.yaml`（持仓主题）
3. `TUSHARE_TOKEN`（实盘拉取）

## 步骤

| 步 | 动作 | 产出 |
|----|------|------|
| 0 | 确认 `as_of` 交易日 | — |
| 1 | `python cli.py --screen-watchlist [--max N]` | `watchlist_screen.json` + `screen_report.md` |
| 2 | 阅读 `market_filter.allow_new_trend_trade` | 板块退潮则**当日不加仓** |
| 3 | 仅对 `watch_pool` 中标的，按需 `assemble` + `exit-check` 做深度分析 | `trade_trace` |
| 4 | **禁止**将 watch_pool 称为「买入推荐」 | — |

## 熔断规则（脚本强制执行）

- 1 日跌幅 > `exclude_if_1d_drop_pct` → 不得留在 `watch_pool`
- 跌破 MA20 → `avoid` 或 `wait`
- 与 `my_discipline.yaml` 持仓**同主题** → 不得新增 `watch_pool`（持仓标的标记 `holding`）
- 同主题 `watch_pool` 超过 `max_per_theme` → 降级
- 板块退潮（主题内多数收跌）→ `allow_new_trend_trade=no`，主题内观察池降级

## Agent 禁止

- 使用未登记的临时 `_*.py` 脚本输出最终结论
- 在文案中使用「优先推荐」「买入」等词（见 `forbid_output_words`）

## 相关

- Lens：[../lenses/sector-correlation.md](../lenses/sector-correlation.md)
- 配置：`config/watchlist.yaml` → `screening_policy`
