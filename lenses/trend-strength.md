# Lens: trend-strength（多周期趋势强度）

## 目标

对**用户指定**的每只股票，评估日线 / 周线 / 月线趋势强度（非选股）。

## 输入

- `symbols[].bars`（D/W/M）
- `symbols[].derived_hints`（MA 斜率、结构标签、量比、ATR 等）

## 强度维度（逐项对照 Pack 填写 observations）

| 周期 | 关注点 |
|------|--------|
| 日线 | 结构(HH/HL)、均线排列、量价配合、波动 |
| 周线 | 中期方向是否与日线一致 |
| 月线 | 大级别是否支持（数据缺失 → gaps） |

## 输出（写入 `decisions[ts_code].strength`）

- `daily` / `weekly` / `monthly`：`strong` | `neutral` | `weak` | `unknown`
- `alignment`：`aligned` | `mostly_aligned` | `conflicted`

**数字仅引用 Pack**；强度等级由你推理，不写死在 Python 里。
