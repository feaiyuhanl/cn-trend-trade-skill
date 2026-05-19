# Playbook: full-analysis（完整趋势分析）

## 前置

1. 完成 [intake.md](intake.md)
2. `python cli.py --assemble --symbols ... [--positions-file ...] [--session-mode ...]`
3. 阅读 `docs/evidence-policy.md`

## 步骤

| 步 | Lens | 产出 |
|----|------|------|
| 0 | intake | 已确认 session_mode / symbols / positions |
| 1 | market-filter | `market_filter` + step |
| 2 | trend-strength | 每标的 `strength` |
| 3 | trend-phase | 每标的 `phase` |
| 4 | entry-signals | 每标的 `entry`（新开/混合模式） |
| 5 | position-management | `position_plan` |
| 6 | exit-signals | `exit_plan` + `holding_review` |
| 7 | discipline | `discipline_checklist` |
| 8 | — | `gaps[]` |
| 9 | validate | `python cli.py --validate-trace ... --pack ...` |
| 10 | — | [templates/trade-report.md](../templates/trade-report.md) |

## 自检

- [ ] `meta.run_id` 与 pack 一致
- [ ] `evidence_ids` 均存在于 pack
- [ ] `market_filter` 列出多指数、非单一 hardcode
- [ ] 含免责声明
