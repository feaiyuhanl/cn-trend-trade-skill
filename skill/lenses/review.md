# Lens: review（复盘）

## 目标

对照历史计划与实际交易，按趋势交易规则给出复盘结论，并按 **SKILL 八维** 沉淀可迭代的改进方向。

## 何时启用

- 用户明确要求复盘（复盘、回顾推荐、持仓回顾）
- playbook `review-session.md`
- `session_mode` 为 `holdings_review` 且用户提供了事后信息
- 已运行 `python cli.py --review` 并阅读八维评估

## 八维演进（必读）

详见 [skill/reference/skill-improvements.md](../reference/skill-improvements.md)。

| ID | 复盘时问自己 |
|----|-------------|
| `MF_PHASE_ENTRY` | 环境 allow 与 phase/entry 是否自洽？ |
| `SECTOR_THEME_EXPOSURE` | 退潮日、同主题暴露是否失控？ |
| `HOLDING_EXIT_DISCIPLINE` | 止损与 exit 建议是否执行？ |
| `WATCH_POOL_BOUNDARY` | 是否把观察池当买入？ |
| `EVIDENCE_TRACEABILITY` | fact_keys、归档是否完整？ |

机检快照：归档目录 `skill_assessment.json`（finalize 自动生成）。

## 输出（trace.review）

- `planned_vs_actual[]`：`ts_code`, `planned`, `actual`, `deviation`
- `phase_accuracy`: `correct` | `early` | `late` | `unknown`
- `discipline_violations[]`：对照机检与个人纪律
- `lessons[]`：可操作的教训
- `next_improvements[]`：**必须带维度前缀**，如 `[MF_PHASE_ENTRY] …`
- `skill_dimensions`（可选）：`{ "MF_PHASE_ENTRY": { "status", "reflection", "action" } }`

### next_improvements 写法

从 `--review` 简报中各维「→」行选取 3–5 条；合并同类项；**禁止**无维度的空泛口号。

复盘：写入 `trace.review` 后由 `finalize` 渲染 `review-report.md`。
