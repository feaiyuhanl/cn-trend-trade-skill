# 项目地图（一眼看懂）

## 三个顶层目录

| 目录 | 动词 | 内容 |
|------|------|------|
| **[skill/](.)** | **读** | playbooks、lenses、reference 文档 |
| **core/** + **cli.py** | **跑** | 组装行情、校验 trace、渲染报告（维护者改这里） |
| **[sample/](../sample/)** | **试** | 样例 pack/trace/持仓 JSON |

配置与契约（一般只读）：`config/`、`contracts/schemas/`、`engine/report/templates/`

运行时输出：`.trend-trade/tmp/` · 筛选归档：`.trend-trade/archive/`

配置：`config/watchlist.yaml`（含 `screening_policy`）、`config/themes.yaml`、`config/my_discipline.yaml`

## 流水线

```
intake → assemble → (Agent 写 trade_trace) → finalize
```

```bash
python cli.py --assemble --symbols 600519.SH --session-mode new_entry
# … Agent 按 skill/playbooks/full-analysis.md + skill/lenses/* 写 trace …
python cli.py --finalize .trend-trade/tmp/trade_trace.json \
  --pack .trend-trade/tmp/market_pack.json --out-dir .trend-trade/tmp
```

## skill/ 索引

### Playbooks

| 文件 | 场景 |
|------|------|
| [playbooks/intake.md](playbooks/intake.md) | 交互采集 |
| [playbooks/full-analysis.md](playbooks/full-analysis.md) | 完整分析 |
| [playbooks/entry-check.md](playbooks/entry-check.md) | 仅新开仓 |
| [playbooks/exit-check.md](playbooks/exit-check.md) | 仅持仓 |
| [playbooks/review-session.md](playbooks/review-session.md) | 复盘（`cli.py --review` + 归档推荐） |
| [playbooks/watchlist-screen.md](playbooks/watchlist-screen.md) | 自选观察池（非荐股） |

### Lenses（按序 · 完整分析）

1. [lenses/market-filter.md](lenses/market-filter.md)
2. [lenses/market-sentiment.md](lenses/market-sentiment.md)
3. [lenses/theme-lifecycle.md](lenses/theme-lifecycle.md)
4. [lenses/quality-gate.md](lenses/quality-gate.md)
5. [lenses/event-risk.md](lenses/event-risk.md)
6. [lenses/trend-strength.md](lenses/trend-strength.md)
7. [lenses/trend-phase.md](lenses/trend-phase.md)
8. [lenses/entry-signals.md](lenses/entry-signals.md)
9. [lenses/position-management.md](lenses/position-management.md)
10. [lenses/exit-signals.md](lenses/exit-signals.md)
11. [lenses/sector-correlation.md](lenses/sector-correlation.md)
12. [lenses/discipline.md](lenses/discipline.md)
13. [lenses/review.md](lenses/review.md)（复盘时 · [演进维](reference/skill-improvements.md)）

配置：`config/themes.yaml`（含龙头）、`config/sentiment.yaml`、`config/event_risk.yaml`、`config/quality_gate.yaml`

### Reference

| 文件 | 说明 |
|------|------|
| [reference/evidence-policy.md](reference/evidence-policy.md) | 事实 vs 推断 |
| [reference/indices-guide.md](reference/indices-guide.md) | 大盘多指数 |
| [reference/phase-definitions.md](reference/phase-definitions.md) | 阶段定义 |
| [reference/setup.md](reference/setup.md) | Tushare |
| [reference/rules-system.md](reference/rules-system.md) | 机检规则 |
| [reference/architecture.md](reference/architecture.md) | 技术结构（维护者） |

## Cursor / Claude

- **唯一 Skill 正文**：[../SKILL.md](../SKILL.md)
- 命令：`/trend-trade` → 读根目录 `SKILL.md`
