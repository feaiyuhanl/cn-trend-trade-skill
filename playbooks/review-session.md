# Playbook: review-session（复盘）

## 输入

- 历史 `trade_trace.json` 或用户粘贴的交易记录
- 可选：`examples/journal/` 下按日 JSON（M2）

## 步骤

1. 读取当时计划（phase、entry、stop）
2. 对照实际结果（用户描述或 journal）
3. 应用 [lenses/review.md](../lenses/review.md)
4. 输出 [templates/review-report.md](../templates/review-report.md)

## 日记

```bash
python cli.py --save-journal examples/journal/entry_sample.json
python cli.py --list-journal
```

## CLI

```bash
python cli.py --validate-trace path/to/trade_trace.json --pack path/to/market_pack.json
```
