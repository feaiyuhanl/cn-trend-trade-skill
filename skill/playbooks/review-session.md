# Playbook: review-session（复盘）

## 何时进入本 playbook

- 用户提到：**复盘**、**回顾推荐**、**持仓做得怎么样**、**计划 vs 实际**
- CLI：`python cli.py --review`（生成简报）
- 补齐：`python cli.py --fill-review-gaps`

## 输入

- **自动**：`.trend-trade/recommendations/` 历次 `finalize` 归档（`recommendation_summary.json` + 完整 trace）
- **持仓**：`.trend-trade/holdings/{run_id}.json` 与 `config/my_discipline.yaml`
- **可选**：用户粘贴的实际成交 / `python cli.py --save-journal`

## 步骤

1. 运行 `python cli.py --review [--review-date YYYYMMDD] [--review-days N]`，阅读简报中的规则提示
2. 对每条待复盘 run：读取归档目录下 `trade_trace.json` 中的计划（phase、entry、exit、holding_review）
3. 对照用户实际（或 journal），应用 [lenses/review.md](../lenses/review.md)
4. 写入 `trace.review`（含 `next_improvements[]` = **SKILL 演进方向**）
5. `python cli.py --finalize trace.json --pack pack.json` → `review-report.md`

## 复盘结论（SKILL 八维）

先读 `cli.py --review` 输出的 **SKILL 八维演进评估**，再填 `trace.review`。

| 维度 ID | 对照 |
|---------|------|
| `MF_PHASE_ENTRY` | `allow_new_trend_trade` vs 无持仓 `entry.action`；phase vs 走势 |
| `SECTOR_THEME_EXPOSURE` | `sector_retreats`、同主题持仓数、退潮日加仓 |
| `HOLDING_EXIT_DISCIPLINE` | `stop_price` / `exit_plan` vs 实际执行 |
| `WATCH_POOL_BOUNDARY` | watch_pool 是否被当买入；禁止词 |
| `EVIDENCE_TRACEABILITY` | fact_keys 覆盖率、归档是否完整 |

参考：[skill/reference/skill-improvements.md](../reference/skill-improvements.md)

## 日记

```bash
python cli.py --save-journal path/to/entry.json
python cli.py --list-journal
```

## CLI

```bash
python cli.py --review --review-days 10
python cli.py --fill-review-gaps
python cli.py --list-recommendations
python cli.py --finalize .trend-trade/tmp/trade_trace.json --pack .trend-trade/tmp/market_pack.json
```
