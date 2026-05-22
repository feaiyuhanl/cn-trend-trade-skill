# A 股特色能力 · 完整实施计划

> 状态：**已完成** · 版本：Skill 0.6.0  
> 原则：见仓库根 `.cursor/rules/full-implementation-no-p0-only.mdc` — **禁止仅 P0 补丁**

## 问题确认（均成立，全做）

| # | 问题域 | 验收标准 |
|---|--------|----------|
| 1 | 板块轮动 / 题材生命周期 | `theme_context` 含阶段、龙头状态、板块强度序；龙头跌停熔断同主题；`themes.yaml` 东财 BK 概念 + `spec_lead` 动态龙头 |
| 2 | 市场情绪 | `market_sentiment` 含涨跌停比、破板率、连板统计、热点题材；与 `market_filter` / entry 机检联动 |
| 3 | 事件风险 | `event_risk` 含减持、财报窗口、业绩预警；机检阻断新开仓 |
| 4 | 质量兜底 | `quality_gate` 含 ST、常年亏损、黑名单；自选筛选排除 block；纪律项机检 |

## 架构

```
assemble / build_live_pack
  → pack_enrich.enrich_a_share_context()
       ├── theme_graph.build_theme_context()
       ├── market_sentiment.fetch_and_compute()
       ├── quality_gate.evaluate_symbols()
       └── event_risk.evaluate_symbols()
  → pack_facts（扁平化 sentiment/theme/quality/event 键）
  → Agent lenses + rules_engine 机检
```

## 交付清单

> **实施状态**：核心代码与机检已落地（v0.6.0）；实盘 enrich 依赖 `TUSHARE_TOKEN`。

### 配置
- [x] `config/themes.yaml` — 东财 BK 概念主键 + `leader_policy: spec_lead`
- [x] `core/theme_leader_resolver.py` — dc_member + limit_list_d 选举龙头
- [x] `core/theme_dc_cache.py` — 接口缓存
- [x] `config/sentiment.yaml` — 阈值档位
- [x] `config/event_risk.yaml` — 财报窗口、减持
- [x] `config/quality_gate.yaml` — ST/亏损/黑名单
- [x] `config/watchlist_risk.yaml` — 用户手工风险标记

### 核心代码
- [x] `core/theme_graph.py` — 消费 `theme_resolution`
- [x] `core/market_sentiment.py`
- [x] `core/quality_gate.py`
- [x] `core/event_risk.py`
- [x] `core/pack_enrich.py`
- [x] `core/pack_facts.py` — 扩展 flat 键
- [x] `core/fetch_live.py` / `core/assemble.py` — 挂载 enrich
- [x] `core/screen_watchlist.py` — 质量/龙头/情绪熔断
- [x] `core/rules_engine.py` — 新机检

### Skill 文档
- [x] `skill/lenses/theme-lifecycle.md`
- [x] `skill/lenses/market-sentiment.md`
- [x] `skill/lenses/event-risk.md`
- [x] `skill/lenses/quality-gate.md`
- [x] 更新 playbooks / MAP / SKILL / discipline / skill_improvements

### 契约与测试
- [x] `contracts/schemas/market_pack.schema.json`
- [x] `sample/a_share_enrich.fixture.json`
- [x] `tests/test_theme_graph.py` 等

## 不做 / 降级说明

- **全市场行业强度排名**：无免费稳定 API 时，用「主题内样本分位 + 龙头」代替全申万排名（逻辑等价于板块内强度序）。
- **精确破板率**：依赖 `limit_list_d.open_times`；缺失时用涨停家数与涨幅分布近似，并在 `gaps` 标明。
