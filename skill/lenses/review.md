# Lens: review（复盘）

## 目标

对照历史计划与实际交易，改进下一阶段判断。

## 何时启用

- 用户明确要求复盘
- playbook `review-session.md`
- `session_mode` 为 `holdings_review` 且用户提供了事后信息

## 输出（trace.review）

- `planned_vs_actual[]`
- `phase_accuracy`: `correct` | `early` | `late`
- `discipline_violations[]`
- `lessons[]`

复盘：写入 `trace.review` 后由 `finalize` 渲染 `review-report.md`（模板 `engine/report/templates/review-report.md.j2`）。
