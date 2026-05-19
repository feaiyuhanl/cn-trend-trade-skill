# 证据政策

## 逻辑链

```
config/indices.yaml + 用户 symbols
  → cli.py --assemble → market_pack.json
    → lenses + playbooks → trade_trace.json
      → finalize → report.md / decision-dossier.md / audit-sheet.md
```

## 规则

1. **价格、成交量、衍生数字**仅来自 `market_pack.json` → `fact_index.flat`（见 [rules-system.md](rules-system.md)）
2. **阶段、入场类型、大盘结论**写在 `trade_trace.json`：
   - `steps[]`：`evidence_ids` + `observations`（推荐 `{ "kind": "fact|qualitative|mixed", "text": "...", "fact_keys": [] }`）
   - `kind=fact` 时 `fact_keys` 必填且须存在于 `fact_index.flat`
   - `decisions[ts_code]`：必填 `evidence_ids` + `facts_used`（引用 fact_index key）
3. **禁止手编**：`holding_review.vs_cost_pct`、`position_plan.computed` → 用 `cli.py --enrich-trace`
4. 数据不足 → `gaps[]`，对应章节降 `confidence`；`production` profile 下 K 线不足则 `phase=unclear`
5. **不选股**、不扫描全市场

## 校验

```bash
python cli.py --assemble --symbols ...
python cli.py --finalize .trend-trade/tmp/trade_trace.json --pack .trend-trade/tmp/market_pack.json
# 或分步：enrich-trace → validate-trace → render-report（--report-kind trade|dossier|audit）
python cli.py --list-rules
```

enrich 会写入 `trace.resolved`（facts/bars 展开 + audit），并同步 `sources_snapshot`。
