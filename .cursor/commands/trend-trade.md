# /trend-trade

执行 [trend-trade Skill](../skills/trend-trade/SKILL.md) 完整流程：

1. **intake** — 确认 `session_mode`、symbols、持仓（见 playbooks/intake.md）
2. `python cli.py --assemble`（实盘加 `--live` + `TUSHARE_TOKEN`）
3. 按 playbook 写 `trade_trace.json`（`facts_used` + `[qualitative]`）
4. `python cli.py --enrich-trace` → `--validate-trace` → `--render-report`
5. 见 [docs/rules-system.md](../docs/rules-system.md)
