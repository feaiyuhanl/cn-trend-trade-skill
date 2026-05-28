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
| 0 | 预检 `trade_date`（滞后则 CLI 立即失败，勿继续） | 启动时 `preflight_fresh_session` |
| 0b | 确认 `trade_date` / `data_stale` | 报告页眉 |
| 1 | `python cli.py --screen-watchlist` | `screen_pack.json` + `screen_trace.json`（骨架） |
| 2 | `python cli.py --show-pack screen-brief --pack .trend-trade/tmp/screen_pack.json` | AI 读数（可分批 `--ts-code`） |
| 3 | `--init-trace --playbook watchlist-screen --pack screen_pack.json`（若需重建骨架） | `screen_trace.json` |
| 4 | Agent 按 lens 顺序推理，**每只** `--patch-trace` 写入 `decisions[].screen` | 已填 rank 的 trace |
| 5 | `python cli.py --validate-trace screen_trace.json --pack screen_pack.json` | 机检通过 |
| 6 | `python cli.py --merge-screen-trace .trend-trade/tmp/screen_trace.json --pack .trend-trade/tmp/screen_pack.json` | 最终观察池报告 |
| 7 | （panoramic 模式自动）`watch_pool` → assemble + full finalize | `.trend-trade/tmp/watch_pool_analysis/report.md` |

可选：`--screen-data-only` 仅执行步骤 1 后停止，等待 Agent patch。

## 扫描模式（`screening_policy.universe_mode`）

| 模式 | CLI | 说明 |
|------|-----|------|
| `watchlist` | `--universe-mode watchlist`（默认） | 仅自选；`trend_top10` 来自自选纯排名 |
| `mainboard` | `--universe-mode mainboard` | 主板全量（去 ST/连续亏损/黑名单，`universe_mainboard.yaml`）；并发拉取见 `fetch_concurrency.yaml` |
| `both` | `--universe-mode both` | 自选全量 + 主板额外候选；观察池仍来自自选子集；`trend_top10` 默认来自主板 |

质量兜底：`quality_gate`（ST、常年亏损）+ `quality_blacklist.yaml`（造假手工名单）+ `watchlist_risk.yaml`（fraud 标记）。

## 中低位过滤（新大陆模式）

- 机检键：`price_percentile_2y`、`position_band`（见 `config/position_filter.yaml`）
- `watch_pool` 须 `position_band=mid_low` 且距 52 周高 ≤ -8%、2 年分位 ≤ 65%
- 纯分排行见 `trend_top10.json` / 报告「趋势分 TOP10」节（**非观察池推荐**）

## 全景报告产物（`panoramic_report: true`）

| 文件 | 内容 |
|------|------|
| `screen_report.md` | 全景摘要（含趋势分 TOP10 节） |
| `trend_top10.json` | 纯 safety_rank 排行（不受观察池策略上限限制） |
| `screen-dossier.md` | 证据链全文（Lens steps + 题材周期规则 + 全分层标的 score_breakdown/trap/量能） |
| `screen-audit-sheet.md` | fetch_status / sources_snapshot 审计 |
| `watch_pool_analysis/report.md` | watch_pool 标的 full finalize 深度报告 |

## Lens 顺序

1. [market-sentiment.md](../lenses/market-sentiment.md)（环境）
2. [watchlist-relative-position.md](../lenses/watchlist-relative-position.md)
3. [watchlist-safety-rank.md](../lenses/watchlist-safety-rank.md)
4. [watchlist-observation-framework.md](../lenses/watchlist-observation-framework.md)（观察止损/止盈框架，非开仓）

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
