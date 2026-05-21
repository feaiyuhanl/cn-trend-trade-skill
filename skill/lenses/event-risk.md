# Lens: event-risk（事件风险）

## 目标

过滤减持、财报窗口、业绩预警等**突发基本面事件**，避免在事件窗内新开趋势仓。

## 必读

- `pack.slots.event_risk.symbols[ts_code]`
- `config/event_risk.yaml`

## 检查项

1. **减持**：`event_flags` 含 `reduction` → 新开 wait/none
2. **财报窗口**：`earnings_window` → 窗口内不开仓（见 config 前后 N 日）
3. **业绩预警**：`forecast_loss` → 禁止加仓/新开
4. **写入**：`gaps[]` 若 pack 为 skip；discipline `EVENT_RISK_CLEAR`

## 禁止

- 已知 block_entry 仍建议 breakout
