# Lens: discipline（交易纪律）

## 目标

每次分析结束必须填写 `discipline_checklist`（≥3 条）。

## 必检项（示例，可增补 note）

1. 是否尊重 `market_filter`（reduced/no 时不激进）
2. 是否「无信号不交易」
3. 止损/计划是否明确（持仓须对应 `stop_price` 或 exit_plan）
4. A 股 T+1、涨跌停流动性是否考虑
5. 是否违反用户 `max_single_position_pct` / `max_total_exposure_pct`
6. 亏损仓是否摊平（应拒绝，除非预定义且未破结构）

每项：`rule`, `passed` (bool), `note`
