# 指数组推理指南（给 Agent）

## 原则

1. **全面采集、综合推理**：`config/indices.yaml` 的 `comprehensive` profile 会拉取多组指数；你的任务是发现**结构**与**分化**，而非套用单一阈值。
2. **分组语义**（见 yaml 中 `reasoning_hint`）：
   - `broad_market`：全市场方向
   - `size_segment`：大盘 vs 中小盘强弱
   - `style`：成长/价值/红利风格
   - `sector_sample`：是否行业性行情
3. **缺失处理**：某 optional 指数未拉到 → `gaps[]`，降置信度，用其余组继续推理。

## 推荐推理流程

```
1. 各 index_group 内：日线方向 + 周线结构（observations）
2. 跨组：是否「大盘跌、小盘涨」等分化？
3. 与用户拟交易标的的市值/风格对照（如做小盘趋势，则 size_segment 权重更高）
4. 输出 market_filter.regime_inference（描述性）
5. 输出 allow_new_trend_trade（yes/reduced/no）
```

## 勿做

- 不要写「沪深300 < MA20 则 no」这类硬编码规则进代码或 Skill 正文
- 不要忽略 `000905`/`000852` 与 `000300` 的背离

## CLI

```bash
python cli.py --list-indices --profile comprehensive
```
