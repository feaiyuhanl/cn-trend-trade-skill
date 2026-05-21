# Lens: quality-gate（质量兜底）

## 目标

**不碰垃圾股**：ST/*ST、常年亏损、黑名单、用户 `watchlist_risk.yaml` 标记 — 走势再好也不买。

## 必读

- `pack.slots.quality_gate.symbols[ts_code]`
- `config/quality_gate.yaml`、`config/quality_blacklist.yaml`、`config/watchlist_risk.yaml`

## 检查项

1. **tier**：`ok` | `warn` | `block` — `block` 时 entry 仅 wait/none
2. **risk_flags**：`st`, `chronic_loss`, `blacklist`, `fraud` 等须在报告与自选输出中**标红**
3. **纪律**：`NO_JUNK_STOCK`、`NO_ST_RISK` 须 passed（block 标的为 false 且 entry 已 wait）
4. 观察池筛选：`tier=block` 不得进入 `watch_pool`

## 禁止

- 对 `tier=block` 标的写「优先推荐」「突破买入」
- 隐瞒 `risk_flags`
