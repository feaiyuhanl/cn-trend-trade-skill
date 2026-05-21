# Playbook: watchlist-risk-audit（自选风险 / 垃圾股审计）

用户问「自选里哪些是垃圾股、ST、退市风险、纯题材炒作」时走本 playbook。

## 原则（减少 Accept 打断）

1. **只跑一条登记命令**，禁止新建 `_tmp_*.py` / 临时分析脚本
2. **中间过程不对话**：命令跑完前不要分段汇报、不要逐只罗列 API 结果
3. **最终只交付**：摘要 + 指向报告路径；全文以脚本生成的 `watchlist_risk_report.md` 为准

## 步骤（单轮完成）

| 步 | 动作 | 产出 |
|----|------|------|
| 1 | `python cli.py --audit-watchlist`（需 `TUSHARE_TOKEN`） | `watchlist_risk_audit.json` + `watchlist_risk_report.md` |
| 2 | 阅读 `.trend-trade/tmp/watchlist_risk_report.md` | 按档摘录要点回复用户 |
| 3 | 可选：建议用户把确认标的写入 `config/watchlist_risk.yaml` | 与 `quality_gate` 合并 |

演示/无 token：`python cli.py --audit-watchlist --fixture`（仅结构，无 live 风险数据）

## 回复排版（Cursor 聊天）

- **禁止 Markdown 表格**（`| col |` 在聊天里会挤成一行）
- 用 `## 标题` + `- **代码 名称**：一句话原因`
- 每档最多列 **8 只**；其余写「共 N 只，见报告」
- 数字、预告类型**仅引用报告/JSON**，禁止手编

## 分档含义（脚本自动）

| 档 | 含义 |
|----|------|
| block | ST / 常年亏损 / 黑名单 / `watchlist_risk` |
| high | 业绩预告 **续亏** 或 **首亏**，且市值偏小 |
| warn | 其他业绩预警（预减、略减等） |
| concept | 小市值 + 极高 PE（题材炒作嫌疑） |

## 相关

- Lens：[../lenses/quality-gate.md](../lenses/quality-gate.md)、[../lenses/event-risk.md](../lenses/event-risk.md)
- 配置：`config/quality_gate.yaml`、`config/event_risk.yaml`、`config/watchlist_risk.yaml`
