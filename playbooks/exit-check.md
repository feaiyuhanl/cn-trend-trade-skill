# Playbook: exit-check（持仓管理快检）

适用：`session_mode=holdings_review`。

## 前置

必须有 `user_context.positions[]`（intake 或 `--positions-file`）。

## Lenses（精简）

`market-filter`（allow 对加仓的影响）→ `trend-phase` → `exit-signals` → `position-management`（加仓/减仓）→ `discipline`

`entry.type` 对已有仓位用 `not_applicable`。
