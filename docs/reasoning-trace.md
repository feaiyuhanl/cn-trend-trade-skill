# 推理链（Trade Trace）

| 字段 | 用途 |
|------|------|
| `sources_snapshot` | tushare 等采集状态 |
| `steps` | 按 lens 的思考过程 |
| `market_filter` | 多指数综合结论 |
| `decisions[ts_code]` | 每标的阶段/入场/仓位/出场 |
| `discipline_checklist` | 纪律自检 |
| `review` | 复盘（可选） |
| `gaps` | 数据缺口 |

示例：[fixtures/trade_trace.sample.json](../fixtures/trade_trace.sample.json)。
