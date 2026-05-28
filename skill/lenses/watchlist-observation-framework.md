# Lens: watchlist-observation-framework（观察池 · 止损/止盈框架）

## 目标

对 **watch_pool / watch_pullback** 标的给出 **观察框架**（非买入、非开仓指令）：

- 结构失效位（如 MA20、周低）
- 移动观察止损描述
- 前高/阻力区分批止盈提示
- 入场触发条件（回踩确认后再评估）

## 输入

- `decisions[].screen` 已填 relative-position + safety_rank
- `derived_hints.ma20_value`、`structure`、`distance_from_*_high_pct`
- `market_filter.allow_new_trend_trade`

## 输出（`decisions[ts_code].screen.observation_plan`）

| 字段 | 说明 |
|------|------|
| `framework` | 固定 `observation_only` |
| `invalid_below` | 失效参考（如 MA20 数值） |
| `trail_stop_hint` | 观察止损一句话 |
| `take_profit_hint` | 止盈/减仓提示 |
| `entry_trigger` | 再评估触发（非追涨） |
| `facts_used` | fact_index 键 |

## 禁止

- 写成「买入」「开仓」「加仓」
- 手编 pack 中不存在的 MA/close

## 相关

- watch_pool 深度分析：`auto_finalize_watch_pool` 将 `observation_plan` 映射到 full trace `exit_plan`
