# Lens: exit-signals（出场信号）

## 目标

为每标的（尤其已有 `positions[]`）制定出场计划。

## 类型（按需选用，说明优先级）

| 类型 | 框架 |
|------|------|
| 移动止损 | 跟踪 MA20、结构低点、Chandelier(ATR) |
| 时间止损 | N 日未创新高/横盘消耗 |
| 趋势反转止盈 | phase → reversal + 结构破坏 |
| 分批止盈 | 逼近阻力/乖离过大/阶段 → exhaustion |
| 异动出场 | 放量长阴、跳空跌破（若有新闻证据再引用） |

## 输出

`decisions[ts_code].exit_plan` + 持仓时 `holding_review`（`action`, `urgency`, `vs_cost_pct` 等）
