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
| 9 | finalize | `python cli.py --finalize ... --pack ... --out-dir .trend-trade/tmp` |
| 9a | （或分步）enrich | `python cli.py --enrich-trace ... --pack ...` |
| 10 | validate | `python cli.py --validate-trace ... --pack ...` |
| 11 | report | report + decision-dossier + audit-sheet |

## 自检

- [ ] `meta.run_id` 与 pack 一致
- [ ] `steps` 与 `meta.lenses_applied` 数量、顺序一致
- [ ] `evidence_ids` / `facts_used` 均存在于 pack
- [ ] 已 `--finalize`（或 enrich + validate）；无 `[RULE_ID]` 错误
- [ ] `market_filter` 列出多指数、非单一 hardcode
- [ ] 含免责声明
