# 规则变更日志

## 1.1.0（2026-05-19，skill v0.4）

- `STEPS_MATCH_LENSES`：steps 与 lenses_applied 一一对应
- `OBSERVATION_KIND_CONSISTENT`：结构化 observation 的 fact_keys 校验
- `FRAMEWORK_NO_RAW_NUMBERS`（warn）：framework/rationale 中未验证数字

## 1.0.0（2026-05-19）

- 初始机检规则集：`config/rules.yaml`
- `fact_index` 随 assemble 生成
- 规则：`FACT_OBSERVATION_NUMBERS`、`DECISIONS_EVIDENCE_REQUIRED`、`DECISIONS_FACTS_USED`、`HOLD_PNL_FROM_PACK`、`MARKET_FILTER_INDICES_SUBSET`、`MF_NO_AGGRESSIVE_NEW_ENTRY`、`DATA_GATE_PHASE` 等
- CLI：`--enrich-trace`、`--render-report`、`--list-rules`
