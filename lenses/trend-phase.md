# Lens: trend-phase（趋势阶段）

## 目标

判断个股处于：**启动期 startup** | **加速期 acceleration** | **衰竭期 exhaustion** | **反转期 reversal** | **unclear**

## 必读

- [docs/phase-definitions.md](../docs/phase-definitions.md)

## 方法

1. 对照 phase-definitions 中的观测清单
2. 结合 trend-strength 的多周期结论
3. 写入 `decisions[ts_code].phase` + step 中的 `inference`

阶段转换须说明证据（evidence_ids），不得无依据跳变。
