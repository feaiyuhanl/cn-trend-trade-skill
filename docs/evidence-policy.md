# 证据政策

## 逻辑链

```
config/indices.yaml + 用户 symbols
  → cli.py --assemble → market_pack.json
    → lenses + playbooks → trade_trace.json
      → templates/trade-report.md
```

## 规则

1. **价格、成交量、衍生数字**仅来自 `market_pack.json`
2. **阶段、入场类型、大盘结论**写在 `trade_trace.json`，须带 `evidence_ids`
3. 数据不足 → `gaps[]`，对应章节降 `confidence`
4. **不选股**、不扫描全市场

## 校验

```bash
python cli.py --validate-pack .trend-trade/tmp/market_pack.json
python cli.py --validate-trace .trend-trade/tmp/trade_trace.json --pack .trend-trade/tmp/market_pack.json
```
