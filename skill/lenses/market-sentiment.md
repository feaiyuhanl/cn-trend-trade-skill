# Lens: market-sentiment（市场情绪）

## 目标

用涨跌停比、破板率、连板高度与热点题材集中度，判断短线氛围是否支持**跟风热点**上的趋势交易。

## 必读

- `pack.market_sentiment`（`tier`, `limit_ratio`, `break_rate`, `max_lianban`, `hot_themes`）
- `config/sentiment.yaml` 档位阈值

## 检查项

1. **涨跌停**：`limit_up` / `limit_down` / `limit_ratio` → 冰点 / 正常 / 亢奋
2. **破板率**：`break_rate` 高 → 追高风险，breakout 须缩仓或 wait
3. **连板**：`lianban_count`、`max_lianban`、`lianban_stocks` → 短线热度
4. **热点题材**：`hot_themes` 与标的 `theme_meta` 重叠 → 标注「跟风热点」
5. **结论**：与 `market_filter.allow_new_trend_trade` 一致（frozen→no，euphoric→reduced 等）

## 禁止

- 仅有单一指数涨跌而忽略涨跌停生态
- 编造 pack 中不存在的情绪数字
