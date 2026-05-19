# Lens: trend-phase（趋势阶段）

## 目标

判断个股处于：**启动期 startup** | **加速期 acceleration** | **衰竭期 exhaustion** | **反转期 reversal** | **unclear**

## 必读

- [reference/phase-definitions.md](../reference/phase-definitions.md)

## 方法

1. 对照 phase-definitions 中的观测清单
2. 结合 trend-strength 的多周期结论
3. 写入 `decisions[ts_code].phase` + step 中的 `inference`

阶段转换须：

- `decisions[ts_code].evidence_ids` + `facts_used`（引用 `fact_index.flat`）
- `steps` 中对应 lens 的 observations（数字可核验；定性用 `[qualitative]`）
- K 线不足时（见 `rules.yaml` profile）**必须** `phase=unclear`
