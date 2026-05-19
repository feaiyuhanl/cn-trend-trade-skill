# Claude Code — cn-trend-trade-skill

完整流程见 [.cursor/skills/trend-trade/SKILL.md](.cursor/skills/trend-trade/SKILL.md)。

1. **intake**：[playbooks/intake.md](playbooks/intake.md) 确认模式/标的/持仓  
2. `python cli.py --assemble [--live] --symbols ...`  
3. Lenses 分析 → `.trend-trade/tmp/trade_trace.json`  
4. `python cli.py --validate-trace ... --pack ...`  
5. [templates/trade-report.md](templates/trade-report.md)

Tushare：[docs/setup.md](docs/setup.md)
