# Playbook: watchlist-screen（自选趋势观察池）

**不是选股/荐股。** 输出仅为 `watch_pool` / `watch_pullback` / `near_high_trim` / `wait` / `avoid`。

## 前置

1. 已配置 `config/watchlist.yaml`（含 `screening_policy`）
2. 已配置 `config/themes.yaml`（含 **龙头 leaders**）、`config/my_discipline.yaml`
3. 可选：`config/watchlist_risk.yaml`（手工风险标红）、`config/quality_blacklist.yaml`
4. `TUSHARE_TOKEN`（实盘拉取 + enrich）

## 步骤

| 步 | 动作 | 产出 |
|----|------|------|
| 0 | 确认 `as_of` 交易日 | — |
| 1 | `python cli.py --screen-watchlist [--max N]` | `watchlist_screen.json` + `screen_report.md` |
| 2 | 阅读报告 **市场情绪 / 题材生命周期 / 风险标的** | `allow_new_trend_trade`、龙头状态 |
| 3 | 仅对 `watch_pool` 中标的，按需 `assemble` + 深度分析 | `trade_trace` |
| 4 | **禁止**将 watch_pool 称为「买入推荐」 | — |

## 熔断规则（脚本强制执行）

### 技术面（原有）

- 1 日跌幅 > `exclude_if_1d_drop_pct` → 不得留在 `watch_pool`
- 跌破 MA20 → `avoid` 或 `wait`
- 与持仓**同主题** → 不得新增 `watch_pool`
- 同主题 `watch_pool` 超过 `max_per_theme` → 降级
- 主题内多数收跌 → `allow_new_trend_trade=no`

### A 股特色（0.6+）

- **quality_gate tier=block**（ST / 常年亏损 / 黑名单 / `watchlist_risk`）→ `avoid`
- **event_risk block_entry**（减持 / 财报窗 / 业绩预警）→ 降级 `wait`
- **龙头跌停或题材 retreat** → 同主题 follower 不得 `watch_pool`
- **市场情绪 frozen** → 观察池降级；**euphoric + 高破板率** → 不追涨

## Agent 禁止

- 使用未登记的临时 `_*.py` 脚本输出最终结论
- 在文案中使用「优先推荐」「买入」等词（见 `forbid_output_words`）
- 对 `risk_flags` 标的隐瞒风险

## 相关

- Lens：[../lenses/sector-correlation.md](../lenses/sector-correlation.md)、[../lenses/quality-gate.md](../lenses/quality-gate.md)
- 配置：`config/watchlist.yaml` → `screening_policy`
