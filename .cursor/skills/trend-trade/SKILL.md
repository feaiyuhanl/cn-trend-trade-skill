---
name: trend-trade
description: A-share trend trading analysis for user-specified stocks (no screening). Multi-timeframe strength, phase (startup/acceleration/exhaustion/reversal), breakout/pullback entry, position and exit frameworks, comprehensive index market filter via AI reasoning, discipline and review. Use for 趋势交易、突破回踩、持仓管理、/trend-trade, cn-trend-trade-skill.
---

# A股趋势交易 (trend-trade)

**脚本采集行情事实 + fact_index** → **Agent 定性推理（facts_used）** → **enrich + 机检规则** → **render 报告**。

## 何时使用

- `/trend-trade`、趋势阶段、突破/回踩、加仓止损、持仓复盘
- 项目含 `cn-trend-trade-skill`

## 护栏

1. [DISCLAIMER.md](../../DISCLAIMER.md) — 非投资建议
2. **数字仅来自** `market_pack.fact_index.flat`（禁止手编 `vs_cost_pct` / `computed`）
3. **intake → assemble → trace → enrich → validate → render-report** 顺序不可跳
4. 规则迭代见 [docs/rules-system.md](../../docs/rules-system.md)；机检表 `config/rules.yaml`
5. **大盘**：多指数组 AI 推理，见 [docs/indices-guide.md](../../docs/indices-guide.md)
6. **不选股**

---

## 第一步：intake（必须）

[skill/playbooks/intake.md](../../skill/playbooks/intake.md) — assemble **之前**向用户确认：

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

输出：`.trend-trade/tmp/market_pack.json`（含 D/W/M K 线、`derived_hints`、`fact_index`、全面 `indices[]`）

---

## 第三步：分析 → trade_trace.json

按场景选 Playbook：

| Playbook | 场景 |
|----------|------|
| [full-analysis.md](../../skill/playbooks/full-analysis.md) | 默认完整 |
| [entry-check.md](../../skill/playbooks/entry-check.md) | 仅新开仓 |
| [exit-check.md](../../skill/playbooks/exit-check.md) | 仅持仓 |
| [review-session.md](../../skill/playbooks/review-session.md) | 复盘 |

### Lenses（按序）

1. [market-filter.md](../../skill/lenses/market-filter.md)
2. [trend-strength.md](../../skill/lenses/trend-strength.md)
3. [trend-phase.md](../../skill/lenses/trend-phase.md) + [phase-definitions.md](../../docs/phase-definitions.md)
4. [entry-signals.md](../../skill/lenses/entry-signals.md) — 突破/回踩**并列评估**
5. [position-management.md](../../skill/lenses/position-management.md)
6. [exit-signals.md](../../skill/lenses/exit-signals.md)
7. [discipline.md](../../skill/lenses/discipline.md) — **必填** checklist
8. [review.md](../../skill/lenses/review.md) — 复盘时

写入 `.trend-trade/tmp/trade_trace.json`：

| 字段 | 要求 |
|------|------|
| `meta.run_id` | 与 pack 一致 |
| `meta.rules_version` | 与 `config/rules.yaml` version 一致 |
| `steps[].observations` | 推荐结构化 `{kind, text, fact_keys}`；见 [docs/architecture.md](../../docs/architecture.md)。纯定性用 `kind=qualitative` 或 `[qualitative]` 字符串 |
| `decisions[ts].evidence_ids` | ≥1，pack 内 bar id |
| `decisions[ts].facts_used` | ≥1，须为 pack `fact_index.flat` 的 key |
| `decisions[ts].position_plan.framework` | Agent 只写定性框架 |
| `discipline_checklist[].rule_id` | 见 `config/rules.yaml` discipline_registry |

**禁止**手填 `holding_review.vs_cost_pct`、`position_plan.computed`。

---

## 第四步：finalize（推荐，一键完成 enrich + 校验 + 三份报告）

```bash
python cli.py --finalize .trend-trade/tmp/trade_trace.json \
  --pack .trend-trade/tmp/market_pack.json --out-dir .trend-trade/tmp
```

产出：

| 文件 | 用途 |
|------|------|
| `report.md` | 行动结论（简洁） |
| `decision-dossier.md` | 完整推理链（复盘） |
| `audit-sheet.md` | 事实 vs 引用审计（防胡诌） |

失败时生成 `validation-errors.md`，根据 `[RULE_ID]` 修正 trace。

### 分步执行（可选）

```bash
python cli.py --enrich-trace .trend-trade/tmp/trade_trace.json --pack .trend-trade/tmp/market_pack.json
python cli.py --validate-trace .trend-trade/tmp/trade_trace.json --pack .trend-trade/tmp/market_pack.json
python cli.py --render-report .trend-trade/tmp/trade_trace.json --pack .trend-trade/tmp/market_pack.json --out .trend-trade/tmp/report.md
python cli.py --render-report ... --report-kind dossier --out .trend-trade/tmp/decision-dossier.md
python cli.py --render-report ... --report-kind audit --out .trend-trade/tmp/audit-sheet.md
```

**trace 写作要求**：`steps` 数量与顺序须与 `meta.lenses_applied` 一一对应（机检 `STEPS_MATCH_LENSES`）。

复盘：在 trace 写入 `review` 块后，`finalize` 会额外生成 `review-report.md`（模板 `reports/templates/review-report.md.j2`）。

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
python cli.py --list-rules
python cli.py --enrich-trace ... --pack ...
python cli.py --render-report ... --pack ...
python scripts/compute_hints.py   # 刷新 hints
```

---

## 固定 vs 动态

| 固定（仓库） | 动态（Agent） |
|--------------|---------------|
| Schema、`config/rules.yaml`、fact_index、机检 | 阶段、入场类型、大盘结论 |
| K 线、hints、computed（脚本） | 突破 vs 回踩择优 |
| enrich + render-report | position_plan.framework / exit 定性描述 |

---

## 示例对话

**用户**：`/trend-trade` 茅台 100 股成本 1650，再看宁德能否买

**Agent**：
1. intake 确认 mixed + 持仓
2. `--assemble --live` 或 fixture
3. assemble → full-analysis → trace → finalize（或 enrich → validate → render）
