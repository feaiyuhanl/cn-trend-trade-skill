# Lens: entry-signals（入场信号）

## 目标

在**不预设**「只做突破」或「只做回踩」的前提下，判断当前更适合哪种入场逻辑，或 `wait` / `none`。

## 前置

- `market_filter.allow_new_trend_trade` 为 `no` 时，新开仓建议 `wait`（持仓复盘标的用 `not_applicable`）
- `trend-phase` 为 `exhaustion` / `reversal` 时，默认不新开仓

## 突破入场（breakout）检查框架

- [ ] 阻力位明确（`derived_hints.resistance_levels` 或 Pack 前高）
- [ ] 有效突破（收盘站上，说明你的判定标准）
- [ ] 放量：`vol_ratio_5_20` 等来自 Pack
- [ ] 周线不强烈反对

## 回踩入场（pullback）检查框架

- [ ] 阶段为 startup / acceleration
- [ ] 回调至关键均线/趋势线附近（引用 hints）
- [ ] 回调缩量
- [ ] 企稳形态（描述 K 线，数字仍引用 Pack）

## 输出

`decisions[ts_code].entry`：

- `type`: `breakout` | `pullback` | `wait` | `none` | `not_applicable`
- `action`: 具体操作语义（如 `wait_for_breakout_1700`）
- `rationale`: 为何选此类型而非另一种

**两种类型并列评估**，选证据更充分者，勿 hardcode 偏好。
