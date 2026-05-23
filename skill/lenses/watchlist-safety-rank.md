# Lens: watchlist-safety-rank（观察池 · 综合安全排序）

## 目标

在 **watchlist-relative-position** 之后，对**每一只**自选给出 **0–100 的 safety_rank** 与 **action**，用于观察池排序。

**不是买入推荐。** 分数含义：**同趋势背景下，相对更安全、更值得优先观察**（含位置、量能、市值/流动性、基本面兜底）。

## 输入

- 上一 lens 的 `screen.weekly_position` / `volume_context` / `trap_risk`
- `quality.tier` / `risk_flags` / `event.flags`
- `fundamentals.total_mv_yi`、`avg_amount_20d_mn`、`pe_ttm` 等
- `market_sentiment.tier`、题材 `lifecycle_stage`、龙头状态

## 推理原则（不写死曲线）

1. **相对位置 + 量能**：底部/中继放量且离周/月前高较远 → 可提高 rank；顶部放量、近新高 → 降低 rank，`action` 倾向 `wait` / `near_high_trim`
2. **质地与体量**：在趋势结构相近时，**市值更大、成交额更足、无续亏/ST/黑名单** → 可提高 rank；小盘高估值题材跟风 → 降低 rank
3. **风险一票否决**：`quality.tier=block` → `action=avoid`，`safety_rank` 应极低
4. **trap_risk=high** → 不得 `action=watch_pool`（机检会拦）
5. **同主题内比较**：优先龙头或中军，慎推纯跟风小票

## 输出（`decisions[ts_code].screen`）

| 字段 | 说明 |
|------|------|
| `safety_rank` | 0–100 整数 |
| `action` | `watch_pool` \| `watch_pullback` \| `near_high_trim` \| `wait` \| `avoid` |
| `fundamental_note` | 市值/PE/流动性/业绩风险一句话 |
| `rank_rationale` | 2–4 句，说明为何高于/低于同主题其他票 |
| `facts_used` | 非空，键须在 fact_index |

## 全量覆盖

**必须为 pack 内每一只 symbol 填写** `safety_rank` 与 `action`（方案 A）。

排序：`safety_rank` 降序 → 脚本应用 policy 熔断与同主题上限 → 输出 `watch_pool`。
