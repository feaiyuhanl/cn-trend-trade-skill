---
name: trend-trade
description: A-share trend trading analysis for user-specified stocks (no screening). Use for 趋势交易、突破回踩、持仓管理、/trend-trade.
---

# 趋势交易 Skill

> 地图：[skill/MAP.md](skill/MAP.md) · 试跑：[sample/README.md](sample/README.md) · 非投资建议：[DISCLAIMER.md](DISCLAIMER.md)

## 三种模式

| 模式 | Playbook | 用途 |
|------|----------|------|
| 完整分析 | [full-analysis.md](skill/playbooks/full-analysis.md) | 指定标的深度趋势分析 |
| 持仓快检 | [exit-check.md](skill/playbooks/exit-check.md) | 已有仓位加减仓/止损 |
| 自选观察池 | [watchlist-screen.md](skill/playbooks/watchlist-screen.md) | 从 watchlist 筛 **观察池**（**非买入推荐**） |
| 自选风险审计 | [watchlist-risk-audit.md](skill/playbooks/watchlist-risk-audit.md) | 垃圾股/ST/业绩预警/题材嫌疑（**一条 CLI**） |
| 复盘 | [review-session.md](skill/playbooks/review-session.md) | 计划 vs 实际；历次推荐已归档 |

## 复盘触发（对话）

用户出现 **复盘**、**回顾推荐**、**持仓回顾** 等意图时：

1. `python cli.py --review [--review-days 10]` → 读简报（历史推荐 + 持仓 + 规则提示）
2. 按 [review-session.md](skill/playbooks/review-session.md) 写 `trace.review`
3. `finalize` → `review-report.md`

每次 `finalize` 成功会自动归档到 `.trend-trade/recommendations/{run_id}/`（可用 `--no-auto-review` 关闭）。

## 流水线（不可跳步）

| 步 | 做什么 | 去哪 |
|----|--------|------|
| 1 intake | 确认模式/标的/持仓 | [skill/playbooks/intake.md](skill/playbooks/intake.md) |
| 2 assemble | 拉行情 + fact_index | `python cli.py --assemble ...` |
| 3 analyze | 按 lens 写 trace | 对应 playbook + [skill/lenses/](skill/lenses/) |
| 4 finalize | 机检 + 报告 | `python cli.py --finalize trace.json --pack pack.json` |

## 产物（脚本生成，禁止手编数字）

| 文件 | 用途 |
|------|------|
| `report.md` | 行动结论 |
| `decision-dossier.md` | 完整推理链 |
| `audit-sheet.md` | 事实审计 |
| `review-report.md` | 有 `trace.review` 时 |
| `screen_report.md` | `--screen-watchlist` 观察池全景报告 |
| `screen-dossier.md` | 观察池证据链 dossier |
| `screen-audit-sheet.md` | 观察池数据源审计 |
| `watch_pool_analysis/report.md` | watch_pool 自动 full finalize |
| `watchlist_risk_report.md` | `--audit-watchlist` 风险审计（禁表格排版） |

工作目录：`.trend-trade/tmp/` · 推荐归档：`.trend-trade/recommendations/{run_id}/` · 观察池归档：`.trend-trade/archive/{run_id}/`

## 对话 / 报告排版

- **禁止 Markdown 表格**（Cursor 聊天里 `| a | b |` 会挤成一行乱码）；用「`##` 标题 + `-` 列表」
- 每条标的单行：`- **600519.SH 贵州茅台**：续亏，市值约 2.1 万亿，见报告第二档`
- 数字用 `- **标签**：值`；操作计划用分条列出，勿整段 JSON
- 超过 8 只同类标的：列代表性 3～8 只 +「其余见 `watchlist_risk_report.md`」

## Agent 执行（免 Accept：禁止文件编辑工具）

Cursor 里对仓库文件的 **Write / StrReplace** 会弹出 Accept/Skip，打断流程。本 Skill 要求 Agent **只用 Shell + 登记 CLI** 写盘。

用户未要求「边看边分析」时：

1. **禁止** `Write`、`StrReplace`、`EditNotebook`（含 `_extract_*.py`、`_tmp_*.py`、临时 notebook）
2. **禁止**多轮「先拉行情 → 再逐只查 → 再总结」；改用登记 CLI **一次跑完**
3. 读 pack / 持仓 / facts → `python cli.py --show-pack holdings|symbols|facts --pack .trend-trade/tmp/market_pack.json`
4. 写 trace → `python cli.py --init-trace --pack ...` 后 `python cli.py --patch-trace ... --patch -`（stdin JSON），再 `--finalize`
5. **自选风险 / 垃圾股** → 仅 `--audit-watchlist`；**自选观察池** → 仅 `--screen-watchlist`；读报告后 **一次回复**
6. 中间步骤不对话、**不等待 Accept**；仅当 CLI 失败或缺 `TUSHARE_TOKEN` 时说明缺口

规则文件：`.cursor/rules/agent-exec-via-cli.mdc`

## 行情交易日（休盘后必读）

- **`meta.trade_date`**（YYYYMMDD）：K 线/涨跌幅/MA 使用的**最后一根日线交易日**；报告与结论必须与此一致。
- **`meta.as_of`**：脚本拉取完成的**墙钟时间**（ISO），不等于行情日。
- 休盘后（本地 **15:05** 起）跑 `--screen-watchlist` / `--assemble`，应看到 `trade_date` = 当日。
- **默认 fail-fast**：live 模式先 **预检**（指数 + 样本股，禁用磁盘缓存），再拉全市场；若指数或 ≥95% 个股缺当日 K 线 → **`DataStaleError` / CLI 退出码 1**，**不会**白跑 3000 只后发现仍是昨日数据。仅调试可加 `--allow-stale`。
- 判定规则：不仅看 `max(K线日期)`（指数已更新、个股仍滞后时会误判为新鲜），还要求 **大盘指数** 与 **≥min_symbol_session_ratio 个股** 均含 `expected_trade_date` 日线。
- 若 `data_stale=true`：**当日已收盘，但 Tushare/akshare 尚未给出收盘价**（外部刷新滞后或网络失败），**不是**程序把交易日算错；请 15:30–17:00 或更晚重试。
- Agent 回复用户时：用报告里的 **`trade_date`** 描述「今日/上一交易日」行情，**禁止**用 `as_of` 日期或自行推断「周一」；下一交易日由 `trade_date` + 交易日历判断。

## 铁律

1. **数字仅来自** `market_pack.fact_index.flat`（禁止手编 `vs_cost_pct` / `computed`）
2. `steps` 与 `meta.lenses_applied` **数量、顺序一致**
3. `observations` 推荐 `{ "kind": "fact|qualitative|mixed", "text": "...", "fact_keys": [] }`
4. **不选股**（全市场扫描）
5. **自选筛选 ≠ 买入推荐**：`--screen-watchlist` 仅输出 `watch_pool`；板块退潮日 `allow=no`；与持仓同主题不新增观察池升级
6. **A 股特色（0.6+）**：assemble 自动 enrich — 题材生命周期/龙头、市场情绪、事件风险、质量兜底；`tier=block` 与龙头跌停时禁止跟风新开仓
7. **不碰垃圾股**：ST、常年亏损、黑名单（`quality_gate`）— 走势再好不买；自选须标 `risk_flags`

## CLI 速查

```bash
# 演示
python cli.py --assemble --symbols 600519.SH,300750.SZ \
  --session-mode mixed --positions-file sample/positions_holdings.json

# trace 骨架 + 合并 patch（Agent 用 Shell，勿 Write 工具）
python cli.py --init-trace --pack .trend-trade/tmp/market_pack.json
python cli.py --show-pack holdings --pack .trend-trade/tmp/market_pack.json
python cli.py --patch-trace .trend-trade/tmp/trade_trace.json --patch patch.json

# 分析后
python cli.py --finalize .trend-trade/tmp/trade_trace.json \
  --pack .trend-trade/tmp/market_pack.json --out-dir .trend-trade/tmp

python cli.py --list-rules

# 自选观察池（非荐股 · 全量 AI safety_rank）
python cli.py --screen-watchlist
python cli.py --show-pack screen-brief --pack .trend-trade/tmp/screen_pack.json
python cli.py --init-trace --playbook watchlist-screen --pack .trend-trade/tmp/screen_pack.json --out .trend-trade/tmp/screen_trace.json
python cli.py --patch-trace .trend-trade/tmp/screen_trace.json --patch -
python cli.py --validate-trace .trend-trade/tmp/screen_trace.json --pack .trend-trade/tmp/screen_pack.json
python cli.py --merge-screen-trace .trend-trade/tmp/screen_trace.json --pack .trend-trade/tmp/screen_pack.json

# 自选风险审计（垃圾股/ST/业绩预警）
python cli.py --audit-watchlist
python cli.py --assemble --symbols 601016.SH,000591.SZ \
  --session-mode holdings_review --positions-file sample/positions_user_holdings.json

# 复盘简报 / 待补齐列表
python cli.py --review --review-days 10
python cli.py --fill-review-gaps
python cli.py --list-recommendations
```

实盘：`skill/reference/setup.md`

## 深入阅读

- [skill/reference/evidence-policy.md](skill/reference/evidence-policy.md)
- [skill/reference/indices-guide.md](skill/reference/indices-guide.md)
- [skill/reference/phase-definitions.md](skill/reference/phase-definitions.md)
- [skill/reference/rules-system.md](skill/reference/rules-system.md)
- [skill/reference/skill-improvements.md](skill/reference/skill-improvements.md)（复盘八维演进）
