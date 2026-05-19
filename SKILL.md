---
name: trend-trade
description: A-share trend trading analysis for user-specified stocks (no screening). Use for 趋势交易、突破回踩、持仓管理、/trend-trade.
---

# 趋势交易 Skill

> 地图：[skill/MAP.md](skill/MAP.md) · 试跑：[sample/README.md](sample/README.md) · 非投资建议：[DISCLAIMER.md](DISCLAIMER.md)

## 流水线（不可跳步）

| 步 | 做什么 | 去哪 |
|----|--------|------|
| 1 intake | 确认模式/标的/持仓 | [skill/playbooks/intake.md](skill/playbooks/intake.md) |
| 2 assemble | 拉行情 + fact_index | `python cli.py --assemble ...` |
| 3 analyze | 按 lens 写 trace | [skill/playbooks/full-analysis.md](skill/playbooks/full-analysis.md) + [skill/lenses/](skill/lenses/) |
| 4 finalize | 机检 + 报告 | `python cli.py --finalize trace.json --pack pack.json` |

## 产物（脚本生成，禁止手编数字）

| 文件 | 用途 |
|------|------|
| `report.md` | 行动结论 |
| `decision-dossier.md` | 完整推理链 |
| `audit-sheet.md` | 事实审计 |
| `review-report.md` | 有 `trace.review` 时 |

工作目录：`.trend-trade/tmp/`

## 铁律

1. **数字仅来自** `market_pack.fact_index.flat`（禁止手编 `vs_cost_pct` / `computed`）
2. `steps` 与 `meta.lenses_applied` **数量、顺序一致**
3. `observations` 推荐 `{ "kind": "fact|qualitative|mixed", "text": "...", "fact_keys": [] }`
4. **不选股**

## CLI 速查

```bash
# 演示
python cli.py --assemble --symbols 600519.SH,300750.SZ \
  --session-mode mixed --positions-file sample/positions_holdings.json

# 分析后
python cli.py --finalize .trend-trade/tmp/trade_trace.json \
  --pack .trend-trade/tmp/market_pack.json --out-dir .trend-trade/tmp

python cli.py --list-rules
```

实盘：`skill/reference/setup.md`

## 深入阅读

- [skill/reference/evidence-policy.md](skill/reference/evidence-policy.md)
- [skill/reference/indices-guide.md](skill/reference/indices-guide.md)
- [skill/reference/phase-definitions.md](skill/reference/phase-definitions.md)
- [skill/reference/rules-system.md](skill/reference/rules-system.md)
