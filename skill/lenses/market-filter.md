# Lens: market-filter（大盘/市场环境）

## 目标

综合 **config/indices.yaml** 中已拉取的指数（按 `index_group` 分组），推理当前是否适合做 A 股趋势交易。**禁止**用单一指数 hardcode 阈值做唯一否决。

## 必读

- [reference/indices-guide.md](../reference/indices-guide.md)
- Pack 中 `indices[]` 的 `derived_hints` 与 D/W/M bars

## 推理步骤

1. **分组对照**：对 `broad_market`、`size_segment`、`style`（若有）分别写 observations
2. **一致性**：各组方向是否一致？若分化，描述「谁强谁弱」
3. **广度 / 情绪**：`market_breadth` 或 `market_sentiment`（涨跌停比、破板率、连板 — 见 market-sentiment lens）
4. **结论** → 写入 trace `market_filter`：
   - `regime_inference`：自由文本（如 `broad_uptrend`、`structural_rotation`、`choppy`）
   - `allow_new_trend_trade`：`yes` | `reduced` | `no` | `not_applicable`（纯持仓复盘时可用后者）
   - 必须列出 `indices_considered` 与 `index_groups_used`

## 禁止

- 仅因「沪深300 某日收跌 X%」就一票否决（须交叉验证）
- 编造 Pack 中不存在的指数数据
