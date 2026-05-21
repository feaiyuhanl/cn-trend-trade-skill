---
name: trend-trade
description: A-share trend trading analysis for user-specified stocks (no screening). Use for 趋势交易、突破回踩、持仓管理、/trend-trade.
---

# 趋势交易 Skill

> 地图：[skill/MAP.md](skill/MAP.md) · 试跑：[sample/README.md](sample/README.md) · 非投资建议：[DISCLAIMER.md](DISCLAIMER.md)

## 三种模式

| 模式 | Playbook | 用途 |
|------|----------|------|
| 完整分析 | [full-analysis.md](skill/playbooks/full-analysis.md) | 指定标的深度趋势分析 |
| 持仓快检 | [exit-check.md](skill/playbooks/exit-check.md) | 已有仓位加减仓/止损 |
| 自选观察池 | [watchlist-screen.md](skill/playbooks/watchlist-screen.md) | 从 watchlist 筛 **观察池**（**非买入推荐**） |
| 复盘 | [review-session.md](skill/playbooks/review-session.md) | 计划 vs 实际；历次推荐已归档 |

## 复盘触发（对话）

用户出现 **复盘**、**回顾推荐**、**持仓回顾** 等意图时：

1. `python cli.py --review [--review-days 10]` → 读简报（历史推荐 + 持仓 + 规则提示）
2. 按 [review-session.md](skill/playbooks/review-session.md) 写 `trace.review`
3. `finalize` → `review-report.md`

每次 `finalize` 成功会自动归档到 `.trend-trade/recommendations/{run_id}/`（可用 `--no-auto-review` 关闭）。

## 流水线（不可跳步）

| 步 | 做什么 | 去哪 |
|----|--------|------|
| 1 intake | 确认模式/标的/持仓 | [skill/playbooks/intake.md](skill/playbooks/intake.md) |
| 2 assemble | 拉行情 + fact_index | `python cli.py --assemble ...` |
| 3 analyze | 按 lens 写 trace | 对应 playbook + [skill/lenses/](skill/lenses/) |
| 4 finalize | 机检 + 报告 | `python cli.py --finalize trace.json --pack pack.json` |

## 产物（脚本生成，禁止手编数字）

| 文件 | 用途 |
|------|------|
| `report.md` | 行动结论 |
| `decision-dossier.md` | 完整推理链 |
| `audit-sheet.md` | 事实审计 |
| `review-report.md` | 有 `trace.review` 时 |
| `screen_report.md` | `--screen-watchlist` 观察池报告 |

工作目录：`.trend-trade/tmp/` · 推荐归档：`.trend-trade/recommendations/{run_id}/` · 观察池归档：`.trend-trade/archive/{run_id}/`

## 对话 / 报告排版

- **禁止 Markdown 表格**（Cursor 聊天里易挤成一行）；用「标题 + 无序列表」
- 数字用 `- **标签**：值`；操作计划用分条列出，勿整段 JSON

## 铁律

1. **数字仅来自** `market_pack.fact_index.flat`（禁止手编 `vs_cost_pct` / `computed`）
2. `steps` 与 `meta.lenses_applied` **数量、顺序一致**
3. `observations` 推荐 `{ "kind": "fact|qualitative|mixed", "text": "...", "fact_keys": [] }`
4. **不选股**（全市场扫描）
5. **自选筛选 ≠ 买入推荐**：`--screen-watchlist` 仅输出 `watch_pool`；板块退潮日 `allow=no`；与持仓同主题不新增观察池升级
6. **A 股特色（0.6+）**：assemble 自动 enrich — 题材生命周期/龙头、市场情绪、事件风险、质量兜底；`tier=block` 与龙头跌停时禁止跟风新开仓
7. **不碰垃圾股**：ST、常年亏损、黑名单（`quality_gate`）— 走势再好不买；自选须标 `risk_flags`

## CLI 速查

```bash
# 演示
python cli.py --assemble --symbols 600519.SH,300750.SZ \
  --session-mode mixed --positions-file sample/positions_holdings.json

# 分析后
python cli.py --finalize .trend-trade/tmp/trade_trace.json \
  --pack .trend-trade/tmp/market_pack.json --out-dir .trend-trade/tmp

python cli.py --list-rules

# 自选观察池（非荐股）
python cli.py --screen-watchlist --max 30
python cli.py --assemble --symbols 601016.SH,000591.SZ \
  --session-mode holdings_review --positions-file sample/positions_user_holdings.json

# 复盘简报 / 待补齐列表
python cli.py --review --review-days 10
python cli.py --fill-review-gaps
python cli.py --list-recommendations
```

实盘：`skill/reference/setup.md`

## 深入阅读

- [skill/reference/evidence-policy.md](skill/reference/evidence-policy.md)
- [skill/reference/indices-guide.md](skill/reference/indices-guide.md)
- [skill/reference/phase-definitions.md](skill/reference/phase-definitions.md)
- [skill/reference/rules-system.md](skill/reference/rules-system.md)
- [skill/reference/skill-improvements.md](skill/reference/skill-improvements.md)（复盘八维演进）
