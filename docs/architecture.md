# 架构说明（v0.4）

## 目录分层

```
cn-trend-trade-skill/
├── adapters/           # 可插拔数据源（registry.yaml + apply）
├── contracts/schemas/  # JSON Schema 契约（权威）
├── core/               # Python 引擎（assemble / validate / enrich / render）
├── skill/              # Agent 推理层（lenses、playbooks）
├── reports/templates/  # Jinja2 报告模板
├── config/             # 规则、指数、数据源元数据
├── fixtures/           # 离线样例
└── schemas/            # Schema 兼容副本（逐步弃用，以 contracts/ 为准）
```

## 数据流

```
adapters (market live + consultation slot)
  → market_pack.json + fact_index
    → Agent (skill/lenses) → trade_trace.json
      → enrich (resolved / audit)
        → validate (rules.yaml)
          → reports/*.md (Jinja2)
```

## 扩展咨询数据（P3）

1. 实现 `adapters/your_feed.py` 的 `apply(pack)`，写入 `pack.slots.consultation.items[]`
2. 在 `adapters/registry.yaml` 注册，替换或排在 `consultation_stub` 之后
3. 新增 `skill/lenses/consultation-context.md`（可选），规定：咨询 slot **不得**产生新数字，仅 `[qualitative]` 引用条目 `id`

## 结构化 observations（P2）

```json
{
  "kind": "fact",
  "text": "vol_ratio_5_20=1.12",
  "fact_keys": ["symbol:600519.SH.derived_hints.vol_ratio_5_20"]
}
```

- `fact`：数字须可对照 `fact_keys` 与 evidence
- `qualitative`：纯推断描述，禁止未验证数字
- `mixed`：兼容旧式字符串（逐步迁移）
