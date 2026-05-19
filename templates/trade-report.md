# 趋势交易分析 · {标的摘要} · {as_of}

> 模式：{session_mode}  
> Run ID：{run_id}  
> 免责声明：见项目 DISCLAIMER.md，**不构成投资建议**。

## 一、市场环境（大盘过滤）

| 项目 | 结论 |
|------|------|
| 环境判断 | {market_filter.regime_inference} |
| 新开趋势仓 | {market_filter.allow_new_trend_trade} |
| 置信度 | {market_filter.confidence} |
| 参考指数 | {market_filter.indices_considered} |

**推理摘要**：{market_filter.reasoning_summary}

## 二、个股决策

<!-- 每只标的重复以下小节 -->

### {ts_code} {name}

| 维度 | 结论 |
|------|------|
| 趋势阶段 | {phase} |
| 强度 D/W/M | {strength} |
| 入场类型 | {entry.type} |
| 建议动作 | {entry.action} |

**入场/加仓**：{entry.rationale}

**仓位计划**：{position_plan 摘要}

**出场计划**：{exit_plan 摘要}

**持仓复盘**（若有）：{holding_review}

---

## 三、交易纪律自检

| 规则 | 通过 | 备注 |
|------|------|------|
| … | ✓/✗ | … |

## 四、数据缺口（gaps）

- …

## 五、推理链摘要

| 步骤 | Lens | 核心推断 | 置信度 |
|------|------|----------|--------|
| … | … | … | … |

## 六、数据源状态

与 `sources_snapshot` 一致。
