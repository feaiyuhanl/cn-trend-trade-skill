# Playbook: full-analysis（完整趋势分析）

## 前置

1. 完成 [intake.md](intake.md)
2. `python cli.py --assemble --symbols ... [--positions-file ...] [--session-mode ...]`
3. 阅读 [reference/evidence-policy.md](../reference/evidence-policy.md)

## 步骤

| 步 | Lens | 产出 |
|----|------|------|
| 0 | intake | 已确认 session_mode / symbols / positions |
| 1 | market-filter | `market_filter` + step |
| 2 | market-sentiment | 涨跌停/破板/连板 → 与 allow 联动 |
| 3 | theme-lifecycle | `theme_context` / sector_retreats / 龙头 |
| 4 | quality-gate | 每标的 tier / risk_flags |
| 5 | event-risk | 减持/财报/预告 |
| 6 | trend-strength | 每标的 `strength` |
| 7 | trend-phase | 每标的 `phase` |
| 8 | entry-signals | 每标的 `entry`（新开/混合模式） |
| 9 | position-management | `position_plan` |
| 10 | exit-signals | `exit_plan` + `holding_review` |
| 11 | sector-correlation | 主题暴露（持仓+新开） |
| 12 | discipline | `discipline_checklist` |
| 13 | — | `gaps[]` |
| 14 | finalize | `python cli.py --finalize ... --pack ... --out-dir .trend-trade/tmp` |
| 14a | （或分步）enrich | `python cli.py --enrich-trace ... --pack ...` |
| 15 | validate | `python cli.py --validate-trace ... --pack ...` |
| 16 | report | report + decision-dossier + audit-sheet |

## 自检

- [ ] `meta.run_id` 与 pack 一致
- [ ] `steps` 与 `meta.lenses_applied` 数量、顺序一致
- [ ] `evidence_ids` / `facts_used` 均存在于 pack
- [ ] 已 `--finalize`（或 enrich + validate）；无 `[RULE_ID]` 错误
- [ ] `market_filter` 列出多指数、非单一 hardcode
- [ ] 含免责声明
