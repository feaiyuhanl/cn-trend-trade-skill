# Lens: discipline（交易纪律）

## 目标

每次分析结束必须填写 `discipline_checklist`（≥3 条），且每项带 **`rule_id`**（机检用）。

## 必检项（从 `config/rules.yaml` → `discipline_registry` 选填）

| rule_id | 说明 |
|---------|------|
| `MF_NO_AGGRESSIVE` | 尊重 `market_filter`（no/reduced 不激进） |
| `NO_SIGNAL_NO_TRADE` | 无信号不交易 |
| `STOP_RECORDED` | 止损与 `exit_plan` / 用户 `stop_price` 一致 |
| `T1_LIMIT_AWARE` | T+1、涨跌停流动性 |
| `POSITION_LIMITS` | 未超 portfolio 上限 |

自定义项用 `CUSTOM_*` 前缀；`passed` 须与 `rules_engine` 结果一致（尤其 `MF_NO_AGGRESSIVE`）。

每项：`rule_id`, `rule`, `passed` (bool), `note`
