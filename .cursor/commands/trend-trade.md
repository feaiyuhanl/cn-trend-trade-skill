# /trend-trade

执行 [trend-trade Skill](../skills/trend-trade/SKILL.md) 完整流程：

1. **intake** — 确认 `session_mode`、symbols、持仓（见 playbooks/intake.md）
2. `python cli.py --assemble`（实盘加 `--live` + `TUSHARE_TOKEN`）
3. 按 playbook 写 `trade_trace.json` 并 validate
4. 输出 `templates/trade-report.md` 格式报告
