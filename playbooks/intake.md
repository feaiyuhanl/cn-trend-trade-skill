# Playbook: intake（会话采集）

**在 `cli.py --assemble` 之前执行。** 配置 `config/defaults.yaml` 中 `intake.ask_before_assemble: true`。

## 必问清单

向用户确认以下项；若用户首条消息已给全，复述确认后再 assemble：

| # | 问题 | 用途 |
|---|------|------|
| 1 | **模式**：新开仓评估 / 持仓管理 / 两者都有？ | `session_mode` |
| 2 | **标的**：ts_code 列表（如 `600519.SH,300750.SZ`） | `--symbols` |
| 3 | **持仓**（模式 2 或 3）：成本、股数、入场日、止损价 | `--positions-file` 或对话整理 JSON |
| 4 | **账户**（可选）：总权益、单笔风险 % | `--equity` `--risk-pct` |
| 5 | **特殊说明**（可选）：财报、解禁、个人纪律 | `user_notes` |

## 确认话术模板

```
请确认本次分析：
- 模式：{session_mode}
- 标的：{symbols}
- 持仓：{positions 摘要或「无」}
- 权益/风险：{portfolio 或「使用默认模板」}
确认后我将拉取行情并分析。
```

用户确认 → 再运行 assemble。

## 快捷路径

用户一次性给出完整信息时，可跳过逐问，但仍须 **复述确认** 一行。

## 示例触发句

见 [examples/README.md](../examples/README.md)。
