# /trend-trade

执行仓库根目录 **[SKILL.md](../../SKILL.md)**。

## 按意图选 playbook（每条意图只跑对应 CLI，勿多轮临时脚本）

| 意图 | CLI | 读报告后一次回复 |
|------|-----|------------------|
| 完整分析 | `--assemble` → 写 trace → `--finalize` | `report.md` |
| 自选观察池 | `--screen-watchlist` | `screen_report.md` |
| 自选风险/垃圾股 | `--audit-watchlist` | `watchlist_risk_report.md` |
| 复盘 | `--review` → … → `--finalize` | `review-report.md` |

聊天回复：**禁止 Markdown 表格**；用标题 + 列表。

**禁止 Write/StrReplace**（会弹 Accept）。写 trace 用 `cli.py --init-trace` + `--patch-trace`；读 pack 用 `--show-pack`。中间不对话。

地图：[skill/MAP.md](../../skill/MAP.md)
