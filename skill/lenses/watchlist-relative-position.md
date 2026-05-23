# Lens: watchlist-relative-position（观察池 · 周/月相对位置）

## 目标

对**每一只**自选标的，结合日/周/月 K 与量能事实，推理：

- 当前在周 K、月 K 上处于什么**相对位置**（距历史高/低、结构、均线）
- 近期放量/缩量属于**底部启动**、**健康回踩**还是**冲顶/派发**
- **站岗风险**（trap_risk）：高 / 中 / 低

**禁止**用固定百分比阈值写死结论；须根据 Pack 中完整 K 线与 hints **综合推理**。

## 输入（只读 Pack）

- `derived_hints`：`structure`、`vol_ratio_5_20`、`amount_ratio_5_20`、`distance_from_*_high_pct`、周/月 MA 斜率等
- `bars.weekly` / `bars.monthly`（最近若干根，见 `--show-pack screen-brief`）
- `fundamentals.*`：市值、成交额、换手、PE（客观数字，用于质地对比）

## 推理要点

1. **周 K 相对位置**：对照近 52 周（或 Pack 内全部）周线 high/low/close，判断是在历史高位区、中继、还是低位修复区
2. **月 K 大级别**：月线图是否仍远离前高，还是已进入顶部密集区
3. **量能情境**：放量发生在突破平台/均线 reclaimed，还是贴近前高/新高的冲刺量
4. **底部放量 + 离顶远** → 通常 trap_risk 偏低；**顶部放量 + 近新高** → trap_risk 偏高（即使日线趋势仍强）

## 输出（写入 `decisions[ts_code].screen`）

- `weekly_position`：文字描述（可含 `[qualitative]`）
- `volume_context`：`bottom_accumulation` | `healthy_pullback` | `top_chase` | `distribution` | `unclear`
- `trap_risk`：`low` | `medium` | `high`
- `facts_used`：须引用 `fact_index.flat` 键
- `evidence_ids`：至少 1 个 weekly/monthly bar id（若 Pack 有 K 线）

**全自选每一只都要填**（方案 A：149 只全部 AI 评估）。
