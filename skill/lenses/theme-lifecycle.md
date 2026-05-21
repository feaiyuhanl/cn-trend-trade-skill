# Lens: theme-lifecycle（题材生命周期 / 龙头传导）

## 目标

评估标的所属**题材阶段**（new → ferment → divergence → consensus → retreat）及**龙头健康度**，解释跟风趋势股为何能涨/为何走弱。

## 必读

- `pack.slots.theme_context`
- `config/themes.yaml`（leaders / members / role）
- 标的 `theme_meta.role`（leader | follower）

## 检查项

1. **阶段**：从 `theme_context.themes[]` 读取 `lifecycle_stage`、`strength_rank`
2. **龙头**：`leaders[].pct_chg_1d`、`leader_limit_down`；龙头跌停 → 同主题 follower 不得 breakout/加仓
3. **板块强度序**：主题 `strength_rank` 与前几个主题对比（本 pack 内相对排名）
4. **写入 trace**：
   - `market_filter.sector_retreats` 与 pack 一致
   - `theme_assessment[]`（可选）：每主题 stage + leader 摘要
   - observations 引用 `fact_keys`：`theme:{id}.lifecycle_stage`、`symbol:{leader}.leader_pct_chg_1d`

## 禁止

- 忽视龙头大跌仍推荐同主题跟风「突破开仓」
- 手编龙头涨跌幅（须来自 pack）
