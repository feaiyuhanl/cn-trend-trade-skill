---
name: trend-trade
description: A-share trend trading analysis for user-specified stocks (no screening). Multi-timeframe strength, phase (startup/acceleration/exhaustion/reversal), breakout/pullback entry, position and exit frameworks, comprehensive index market filter via AI reasoning, discipline and review. Use for 趋势交易、突破回踩、持仓管理、/trend-trade, cn-trend-trade-skill.
---

# A股趋势交易 (trend-trade)

**脚本采集行情事实 + 衍生数字** → **Agent 按 Lenses 推理** → **固定报告 + `trade_trace.json`**。

## 何时使用

- `/trend-trade`、趋势阶段、突破/回踩、加仓止损、持仓复盘
- 项目含 `cn-trend-trade-skill`

## 护栏

1. [DISCLAIMER.md](../../DISCLAIMER.md) — 非投资建议
2. **数字仅来自** `market_pack.json`
3. **intake → assemble → trace → validate** 顺序不可跳
4. **大盘**：多指数组 AI 推理，见 [docs/indices-guide.md](../../docs/indices-guide.md)
5. **不选股**

---

## 第一步：intake（必须）

[playbooks/intake.md](../../playbooks/intake.md) — assemble **之前**向用户确认：

| 项 | 说明 |
|----|------|
| session_mode | `new_entry` / `holdings_review` / `mixed` |
| symbols | 必填，如 `600519.SH` |
| positions | 持仓模式必填：成本、股数、入场日、止损 |
| portfolio | 可选：权益、风险% |

确认后执行 CLI。范例：[examples/README.md](../../examples/README.md)

---

## 第二步：assemble

### 无 Token（演示）

```bash
python cli.py --assemble --symbols 600519.SH,300750.SZ \
  --session-mode mixed --positions-file examples/positions_holdings.json
```

### 实盘 Tushare

```bash
# 见 docs/setup.md
python cli.py --assemble --live --symbols 600519.SH,300750.SZ \
  --session-mode mixed --positions-file examples/positions_holdings.json
```

输出：`.trend-trade/tmp/market_pack.json`（含 D/W/M K 线、`derived_hints`、全面 `indices[]`）

---

## 第三步：分析 → trade_trace.json

按场景选 Playbook：

| Playbook | 场景 |
|----------|------|
| [full-analysis.md](../../playbooks/full-analysis.md) | 默认完整 |
| [entry-check.md](../../playbooks/entry-check.md) | 仅新开仓 |
| [exit-check.md](../../playbooks/exit-check.md) | 仅持仓 |
| [review-session.md](../../playbooks/review-session.md) | 复盘 |

### Lenses（按序）

1. [market-filter.md](../../lenses/market-filter.md)
2. [trend-strength.md](../../lenses/trend-strength.md)
3. [trend-phase.md](../../lenses/trend-phase.md) + [phase-definitions.md](../../docs/phase-definitions.md)
4. [entry-signals.md](../../lenses/entry-signals.md) — 突破/回踩**并列评估**
5. [position-management.md](../../lenses/position-management.md)
6. [exit-signals.md](../../lenses/exit-signals.md)
7. [discipline.md](../../lenses/discipline.md) — **必填** checklist
8. [review.md](../../lenses/review.md) — 复盘时

写入 `.trend-trade/tmp/trade_trace.json`，`meta.run_id` 与 pack 一致。

---

## 第四步：校验

```bash
python cli.py --validate-trace .trend-trade/tmp/trade_trace.json \
  --pack .trend-trade/tmp/market_pack.json
```

---

## 第五步：报告

严格按 [templates/trade-report.md](../../templates/trade-report.md) 输出 Markdown（不改一级标题）。

复盘用 [templates/review-report.md](../../templates/review-report.md)。

---

## 复盘日记（可选）

用户确认交易记录后，可保存：

```bash
python cli.py --save-journal examples/journal/entry_sample.json
python cli.py --list-journal
```

---

## CLI 速查

```bash
python cli.py --status
python cli.py --list-indices --profile comprehensive
python scripts/compute_hints.py   # 刷新 hints
```

---

## 固定 vs 动态

| 固定（仓库） | 动态（Agent） |
|--------------|---------------|
| Schema、报告模板、指数注册表 | 阶段、入场类型、大盘结论 |
| K 线、hints（脚本） | 突破 vs 回踩择优 |
| intake 流程 | 仓位/出场/复盘 prose |

---

## 示例对话

**用户**：`/trend-trade` 茅台 100 股成本 1650，再看宁德能否买

**Agent**：
1. intake 确认 mixed + 持仓
2. `--assemble --live` 或 fixture
3. full-analysis → trace → validate → 报告
