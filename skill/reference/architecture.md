# 技术结构（维护者）

## 顶层（运营视角）

```
cn-trend-trade-skill/
├── SKILL.md              # Agent 唯一入口
├── README.md             # 人类入口
├── cli.py
├── skill/                # 读：playbooks、lenses、reference
├── sample/               # 试：样例 JSON
├── core/                 # 跑：Python 引擎
├── config/               # 规则、指数
├── contracts/schemas/    # JSON Schema
├── engine/report/templates/  # Jinja 报告
└── adapters/             # 数据源插件
```

## 数据流

```
adapters → market_pack + fact_index
  → Agent (skill/) → trade_trace
    → finalize (enrich + validate + render)
```

## 扩展咨询数据

1. `adapters/your_feed.py` → `pack.slots.consultation`
2. 注册 `adapters/registry.yaml`
3. 可选 `skill/lenses/consultation-context.md`（禁止新数字）
