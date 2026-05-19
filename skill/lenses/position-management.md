# Lens: position-management（仓位管理）

## 目标

给出**框架化**仓位计划，由 Agent 代入 `user_context.portfolio` 与 Pack 中的价格/ATR 计算。

## 模式

| session_mode | 重点 |
|--------------|------|
| `new_entry` | 首仓、止损距离、最大仓位 |
| `holdings_review` | 是否加仓/减仓、金字塔规则 |
| `mixed` | 分标的处理 |

## 首仓框架

- 单笔风险额 = `total_equity × risk_per_trade_pct / 100`
- 股数 ≈ 风险额 / (入场价 − 止损价)
- 止损：结构低点 或 N×ATR（N 在 rationale 中说明，建议 1.5～2.5）

## 加仓框架

- 仅 **acceleration** + 浮盈 + 二次确认（突破或健康回踩）
- **exhaustion / reversal**：禁止加仓
- 最多 2～3 笔；总仓位 ≤ `max_total_exposure_pct`

## 输出

`decisions[ts_code].position_plan`：

| 子字段 | 谁写 |
|--------|------|
| `framework` | Agent（定性：加仓条件、止损逻辑描述） |
| `computed` | **仅脚本** `cli.py --enrich-trace`（股数、ATR 止损、浮盈%） |

禁止在 `computed` 或 `holding_review.vs_cost_pct` 手填数字。
