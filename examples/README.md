# 使用范例

## 1. 新开仓评估（无持仓）

**用户说**：

```
/trend-trade
评估 600519.SH、300750.SZ 能否趋势开仓，账户 50 万，单笔风险 1%
```

**Agent**：intake 确认 `new_entry` →

```bash
python cli.py --assemble --symbols 600519.SH,300750.SZ \
  --session-mode new_entry \
  --positions-file examples/positions_new_entry.json \
  --equity 500000 --risk-pct 1.0
```

---

## 2. 持仓管理

**用户说**：

```
我持有茅台 100 股成本 1650，止损 1580，帮看要不要加仓或移动止损
```

**Agent**：intake 确认 `holdings_review` → 整理 positions →

```bash
python cli.py --assemble --symbols 600519.SH \
  --session-mode holdings_review \
  --positions-file examples/positions_holdings.json
```

playbook：[exit-check.md](../playbooks/exit-check.md)

---

## 3. 混合模式

**用户说**：

```
茅台我有仓位想管一下，另外帮看宁德能不能新买
```

**Agent**：`session_mode=mixed`，positions 只含茅台 →

```bash
python cli.py --assemble --symbols 600519.SH,300750.SZ \
  --session-mode mixed \
  --positions-file examples/positions_holdings.json
```

---

## 4. 仅对话提供持仓（无文件）

Agent 将对话整理为 JSON 写入 `.trend-trade/tmp/user_positions.json` 再 `--positions-file` 指向该文件。

**最低字段**：`ts_code`；建议含 `cost`, `shares`, `entry_date`, `stop_price`。

---

## 5. 复盘

**用户说**：

```
复盘上周对 600519 的突破入场，实际止损了
```

playbook：[review-session.md](../playbooks/review-session.md)，输出 [review-report.md](../templates/review-report.md)。

保存日记：

```bash
python cli.py --save-journal examples/journal/entry_sample.json
```

## 6. 实盘拉取

```bash
# 配置 TUSHARE_TOKEN 后
python cli.py --assemble --live --symbols 600519.SH --session-mode new_entry
```

详见 [docs/setup.md](../docs/setup.md)。
