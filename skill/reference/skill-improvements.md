# SKILL 八维演进（复盘专用）

> 配置：`config/skill_improvements.yaml` · 机检：`core/skill_improvements.py` · 归档：`skill_assessment.json`

交易体系成熟的标志不是「少犯错一次」，而是**五个维度上持续可度量、可复盘、可迭代**。

## 八维一览

| ID | 维度 | 核心 lens / 规则 |
|----|------|------------------|
| `MF_PHASE_ENTRY` | 大盘过滤与个股阶段 / 开仓一致性 | market-filter, trend-phase, entry-signals |
| `SECTOR_THEME_EXPOSURE` | 板块退潮与主题暴露 | sector-correlation, SECTOR_CORRELATION_CAP |
| `THEME_LEADER_LIFECYCLE` | 题材生命周期与龙头传导 | theme-lifecycle, LEADER_RETREAT_BLOCKS_FOLLOWER |
| `MARKET_SENTIMENT` | 市场情绪 | market-sentiment, SENTIMENT_* |
| `EVENT_QUALITY_GATE` | 事件风险与质量兜底 | event-risk, quality-gate, NO_JUNK_STOCK |
| `HOLDING_EXIT_DISCIPLINE` | 持仓止损与 exit_plan 纪律 | exit-signals, STOP_RECORDED |
| `WATCH_POOL_BOUNDARY` | 观察池 vs 开仓边界 | watchlist-screen, WATCH_POOL_NOT_BUY |
| `EVIDENCE_TRACEABILITY` | 证据链与归档可追溯 | fact_keys, finalize 归档 |

## 状态含义

| status | 含义 |
|--------|------|
| `ok` | 当次 trace 机检无关键发现 |
| `warn` | 有改进空间，不必然违反纪律 |
| `gap` | 与规则或成熟信号明显冲突 |
| `na` | 本次不适用（如无持仓） |

## 复盘工作流

1. `python cli.py --review` → 阅读 **SKILL 八维演进评估**
2. 对照 `review_questions` 与用户实际，写 `trace.review`
3. 可选：填 `trace.review.skill_dimensions.{id}` = `{ status, reflection, action }`
4. `next_improvements[]` 使用维度前缀，例如：`[SECTOR_THEME_EXPOSURE] 退潮日禁止同主题加仓`
5. `finalize` → `review-report.md` + 更新 `skill_assessment.json`

## 跨 run 成熟曲线

- 某维连续多次 `ok` → 可将规则从「warn」升级为习惯
- 某维反复 `gap` → 优先改 playbook / `rules.yaml` / `my_discipline.yaml`，而非只改个股判断

## 与观察池筛选的关系

`WATCH_POOL_BOUNDARY` 仅对 **watchlist-screen** 与「观察池标的被直接买入」场景加严；完整分析 run 仍须满足 `MF_PHASE_ENTRY` 与 `SECTOR_THEME_EXPOSURE`。
