# 交易规则体系（可持续迭代）

## 设计目标

1. **数字事实**只来自 `market_pack.fact_index`（assemble 时脚本生成）
2. **定性判断**（阶段、大盘环境）写在 `trade_trace`，但必须 `evidence_ids` + `facts_used`
3. **机检规则**集中在 `config/rules.yaml`，改规则不改正文 Skill 也能迭代
4. **报告**用 `cli.py --render-report` 从 trace 渲染，禁止在报告里新造数字

## 文件分工

| 文件 | 职责 |
|------|------|
| `config/rules.yaml` | 规则版本、profile、machine_rules 注册表 |
| `core/pack_facts.py` | 从 pack 生成 `fact_index.flat` |
| `core/observation_verify.py` | 校验 steps.observations 中数字 |
| `core/rules_engine.py` | 执行 machine_rules |
| `core/position_calc.py` | 浮盈、止损、建议股数 |
| `core/enrich_trace.py` | 写入 `position_plan.computed` |
| `core/report_render.py` | 报告渲染 |

## Agent 工作流（防幻觉）

```
intake → assemble（含 fact_index）
→ 写 trade_trace（定性 + facts_used 引用）
→ cli.py --enrich-trace trace.json --pack market_pack.json
→ cli.py --validate-trace trace.json --pack market_pack.json
→ cli.py --render-report trace.json --pack market_pack.json
```

### observations 写法

- 引用 pack 数字：写在对应 `evidence_ids` 的 step 里，数字须可匹配
- 纯定性句：句首加 `[qualitative]`（见 `rules.yaml` → `observation_policy.unverified_marker`）

### decisions 必填

- `evidence_ids`：至少 1 个 pack 内 bar id
- `facts_used`：至少 1 个 `fact_index.flat` 的 key（`python cli.py --assemble` 后可打开 pack 查看）

### 禁止 Agent 手写字段

- `holding_review.vs_cost_pct` → 用 `--enrich-trace` 覆盖
- `position_plan.computed` → 同上

## 如何新增一条机检规则

1. 在 `config/rules.yaml` → `machine_rules` 增加：

```yaml
  - id: MY_RULE_ID
    severity: error   # 或 warn
    description: 人类可读说明
    check: my_check_function_name
```

2. 在 `core/rules_engine.py` → `_CHECK_REGISTRY` 实现 `my_check_function_name(pack, trace, profile) -> list[str]`

3. 在 `tests/test_rules_engine.py` 增加用例

4. `python cli.py --list-rules` 确认已注册

## Profile

| profile | 用途 |
|---------|------|
| `development` | fixture / 少 K 线调试 |
| `production` | 实盘：至少 20 根日线才允许 phase≠unclear |

`assemble` 按 `meta.mode` 自动设置 `rules_profile`；可用 pack.meta 覆盖。

## 迭代 changelog 建议

在仓库维护 `skill/reference/rules-changelog.md`（可选），每条记录：

- rules.yaml `version`  bump
- 新增/修改的 rule id
- 对 Agent 文案或 lens 的影响
