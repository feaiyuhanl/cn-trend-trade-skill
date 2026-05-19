# /trend-trade

执行仓库根目录 **[SKILL.md](../../SKILL.md)**：

1. **intake** — [skill/playbooks/intake.md](../../skill/playbooks/intake.md)
2. `python cli.py --assemble ...`
3. 按 [skill/playbooks/full-analysis.md](../../skill/playbooks/full-analysis.md) 写 `trade_trace.json`
4. `python cli.py --finalize .trend-trade/tmp/trade_trace.json --pack .trend-trade/tmp/market_pack.json`

地图：[skill/MAP.md](../../skill/MAP.md)
