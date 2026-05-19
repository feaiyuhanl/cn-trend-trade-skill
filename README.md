# cn-trend-trade-skill

在 **Cursor / Claude Code** 中完成 **A 股趋势交易分析**（用户指定标的，不选股）。

```
intake 确认 → market_pack（Tushare/ fixture）→ Lenses 推理 → trade_trace → 固定报告
```

> 仅供学习研究，**不构成投资建议**。[DISCLAIMER.md](DISCLAIMER.md)

## 能力一览

| 模块 | 说明 |
|------|------|
| 趋势强度 | 日/周/月，AI 推理 |
| 趋势阶段 | 启动/加速/衰竭/反转 |
| 入场 | 突破 & 回踩框架，AI 择优 |
| 仓位/出场 | 框架 + 公式模板，AI 代入 |
| 大盘过滤 | [全面指数注册表](config/indices.yaml)，AI 分组推理 |
| 纪律 | 强制 checklist |
| 复盘 | playbook + journal |

## 快速开始

```bash
git clone <repo> cn-trend-trade-skill
cd cn-trend-trade-skill
pip install -r requirements.txt

# 演示（无需 Token）
python cli.py --assemble --symbols 600519.SH,300750.SZ \
  --session-mode mixed --positions-file examples/positions_holdings.json --copy-trace
python cli.py --validate-trace .trend-trade/tmp/trade_trace.json --pack .trend-trade/tmp/market_pack.json
```

用 Cursor 打开本目录，输入 `/trend-trade`。

### 实盘

见 [docs/setup.md](docs/setup.md)：

```bash
$env:TUSHARE_TOKEN = "your_token"   # PowerShell
python cli.py --assemble --live --symbols 600519.SH
```

## 目录

| 路径 | 说明 |
|------|------|
| `.cursor/skills/trend-trade/SKILL.md` | Agent 入口 |
| `config/indices.yaml` | 指数注册表（非 hardcode 规则） |
| `core/fetch_live.py` | Tushare 拉取 + hints |
| `lenses/` | AI 分析框架 |
| `playbooks/intake.md` | 交互采集 |
| `schemas/` | market_pack / trade_trace |
| `cli.py` | assemble / validate / journal |

## 版本

- **0.2.0** — Tushare 实盘、hints、journal、完整 Skill 流程
- **0.1.0** — M0 fixture 骨架

## License

MIT
