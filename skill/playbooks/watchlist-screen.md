# Playbook: watchlist-screen（自选趋势观察池 · AI 排序）

**不是选股/荐股。** 输出仅为 `watch_pool` / `watch_pullback` / `near_high_trim` / `wait` / `avoid`。

## 架构（方案 A）

1. **脚本**：拉全自选 pack（日/周/月 K + fundamentals + quality/event）→ `screen_pack.json`
2. **AI**：对**每一只**标的推理 `safety_rank` + `action`（无写死阈值）
3. **脚本**：合并 trace + policy 熔断 → `watchlist_screen.json` / `screen_report.md`

## 前置

1. `config/watchlist.yaml`（含 `screening_policy`）
2. `config/themes.yaml`、`config/my_discipline.yaml`
3. `TUSHARE_TOKEN`

## 步骤

| 步 | 动作 | 产出 |
|----|------|------|
| 0 | 确认 `trade_date` / `data_stale` | 报告页眉 |
| 1 | `python cli.py --screen-watchlist` | `screen_pack.json` + `screen_trace.json`（骨架） |
| 2 | `python cli.py --show-pack screen-brief --pack .trend-trade/tmp/screen_pack.json` | AI 读数（可分批 `--ts-code`） |
| 3 | `--init-trace --playbook watchlist-screen --pack screen_pack.json`（若需重建骨架） | `screen_trace.json` |
| 4 | Agent 按 lens 顺序推理，**每只** `--patch-trace` 写入 `decisions[].screen` | 已填 rank 的 trace |
| 5 | `python cli.py --validate-trace screen_trace.json --pack screen_pack.json` | 机检通过 |
| 6 | `python cli.py --merge-screen-trace .trend-trade/tmp/screen_trace.json --pack .trend-trade/tmp/screen_pack.json` | 最终观察池报告 |
| 7 | 仅对 `watch_pool` 按需 `assemble` + 深度分析 | `trade_trace` |

可选：`--screen-data-only` 仅执行步骤 1 后停止，等待 Agent patch。

## Lens 顺序

1. [market-sentiment.md](../lenses/market-sentiment.md)（环境）
2. [watchlist-relative-position.md](../lenses/watchlist-relative-position.md)
3. [watchlist-safety-rank.md](../lenses/watchlist-safety-rank.md)

## 熔断规则（脚本强制执行，非 AI 打分）

- **quality_gate tier=block** → `avoid`
- **event_risk block_entry** → 降级 `wait`
- 1 日跌幅 > 阈值、跌破 MA20（policy）、同主题上限、板块退潮、龙头跌停 — 见原 playbook
- **trap_risk=high** 且 AI 误标 `watch_pool` → validate 失败

## Agent 禁止

- 手编 pack 中不存在的 close/市值/距高 %
- 用写死百分比规则替代推理（阈值由你综合 K 线判断）
- 跳过任一只自选的 `safety_rank`
- 使用「买入推荐」等词

## 相关

- [watchlist-risk-audit.md](watchlist-risk-audit.md)（垃圾股审计，独立 CLI）
