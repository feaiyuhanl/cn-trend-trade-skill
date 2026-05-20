# Lens: sector-correlation（板块相关性）

## 目标

控制**主题暴露**，避免观察池与持仓在同一赛道过度集中（如电力/绿能链集体回撤）。

## 必读

- `config/themes.yaml`
- `config/my_discipline.yaml` → `holdings[]`
- 筛选结果 `market_filter.sector_retreats`

## 检查项

1. **持仓主题**：从 `holdings` 读取 `theme`，列出当前暴露
2. **候选主题**：每只 `watch_pool` 标的映射 `themes.yaml` 中的 theme
3. **同主题上限**：每主题最多 `max_per_theme` 只进入 `watch_pool`（脚本已裁切，Agent 复述即可）
4. **板块退潮**：若主题内 ≥50% 样本 1 日收跌且中位跌幅 >2% → `allow_new_trend_trade=no`，当日不加仓、不推荐同主题新开
5. **与持仓同主题**：已有持仓的主题下，**不**将其他标的标为可开仓；仅可 `wait` 或深度分析后 `hold`

## 输出（写入 trace 或 screen 备注）

- `sector_exposure_summary`：各主题持仓数 + 观察池数
- `correlation_warnings[]`：文字警告
- 与 `market_filter.allow_new_trend_trade` 一致

## 禁止

- 忽视持仓已集中在电力/绿能仍批量推荐同板块「观察池」作为买入理由
