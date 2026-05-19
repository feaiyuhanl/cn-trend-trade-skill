# 使用范例

地图：[skill/MAP.md](../skill/MAP.md) · 流程：[SKILL.md](../SKILL.md)

## 1. 新开仓评估

```bash
python cli.py --assemble --symbols 600519.SH,300750.SZ \
  --session-mode new_entry \
  --positions-file sample/positions_new_entry.json \
  --equity 500000 --risk-pct 1.0
```

## 2. 持仓管理

```bash
python cli.py --assemble --symbols 600519.SH \
  --session-mode holdings_review \
  --positions-file sample/positions_holdings.json
```

Playbook：[skill/playbooks/exit-check.md](../skill/playbooks/exit-check.md)

## 3. 混合模式

```bash
python cli.py --assemble --symbols 600519.SH,300750.SZ \
  --session-mode mixed \
  --positions-file sample/positions_holdings.json
```

## 4. 复盘

Playbook：[skill/playbooks/review-session.md](../skill/playbooks/review-session.md)

```bash
python cli.py --save-journal sample/journal/entry_sample.json
```

## 5. 完整流水线（演示）

```bash
python cli.py --assemble --symbols 600519.SH,300750.SZ \
  --session-mode mixed --positions-file sample/positions_holdings.json --copy-trace
# Agent 完善 trade_trace 后：
python cli.py --finalize .trend-trade/tmp/trade_trace.json \
  --pack .trend-trade/tmp/market_pack.json --out-dir .trend-trade/tmp
```

## 6. 实盘

见 [skill/reference/setup.md](../skill/reference/setup.md)。
