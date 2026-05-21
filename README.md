# cn-trend-trade-skill

在 **Cursor / Claude** 中完成 **A 股趋势交易分析**（用户指定标的，不选股）。

```
intake → assemble → Lenses → trade_trace → finalize → 报告
```

> 仅供学习研究，**不构成投资建议**。[DISCLAIMER.md](DISCLAIMER.md)

## 5 秒看懂结构

| 目录 | 你做什么 |
|------|----------|
| **[skill/](skill/MAP.md)** | 读规则、写分析（playbooks + lenses） |
| **cli.py** + **core/** | 跑命令（一般不用改代码） |
| **[sample/](sample/README.md)** | 复制样例试跑 |

**Agent 入口**：[SKILL.md](SKILL.md)（根目录，唯一权威）

## 30 秒试跑

```bash
pip install -r requirements.txt

python cli.py --assemble --symbols 600519.SH,300750.SZ \
  --session-mode mixed --positions-file sample/positions_holdings.json --copy-trace

# Agent 按 SKILL.md 完善 trade_trace 后：
python cli.py --finalize .trend-trade/tmp/trade_trace.json \
  --pack .trend-trade/tmp/market_pack.json --out-dir .trend-trade/tmp
```

Cursor：打开本目录，输入 `/trend-trade`。

实盘 Token：见 [skill/reference/setup.md](skill/reference/setup.md)。

## 能力

趋势强度 / 阶段 / 突破与回踩 / 仓位与出场 / 多指数大盘过滤 / 纪律 checklist / 复盘。

**0.6.0 A 股特色**：题材生命周期与龙头传导、市场情绪（涨跌停/破板/连板）、事件风险（减持/财报/预告）、质量兜底（ST/常年亏损/黑名单）；`assemble` 自动 `enrich`。

## 版本

- **0.6.0** — A 股四块能力贯通 enrich + 机检 + 八维复盘；见 [docs/PLAN_A_SHARE_FEATURES.md](docs/PLAN_A_SHARE_FEATURES.md)
- **0.5.0** — 目录减法：`skill/` + `sample/` + 根 `SKILL.md`；删重复 lenses/schemas/templates
- **0.4.0** — finalize、Jinja 报告、结构化 observations、adapters
- **0.3.0** — fact_index、机检规则、enrich/render

## License

MIT
