# 环境配置

## 依赖

```bash
pip install -r requirements.txt
```

## Tushare（实盘）

### 休盘后几分钟为何还是昨天收盘？

**常见原因：外部数据源尚未刷新，不是本 Skill 交易日算错。**

| 来源 | 典型情况 |
|------|----------|
| **Tushare Pro** | 日线 `daily` / `index_daily` 常在收盘后 **30 分钟～数小时** 才入库；15:05 立刻跑可能仍只有上一交易日。 |
| **akshare** | 用于在 Tushare 缺 bar 时**补当日 K 线**；若接口尚未更新或网络中断，补数为空，程序会标 `data_stale`。 |

程序逻辑：15:05 后起认为「应使用当日」`expected_trade_date`。live 跑批**默认先预检**（指数 + 样本股，不用磁盘缓存）；若指数 K 线或 ≥95% 个股缺当日 bar → **`data_stale` + 退出码 1**（`--allow-stale` 仅调试用）。全市场扫描前即失败，避免跑完 3000 只仍是昨日数据。建议 15:30–17:00 重试。

当日 K 线拉取：`fetch_live` 先 Tushare，缺失再 akshare（见 `requirements.txt`）。

1. 注册 [Tushare Pro](https://tushare.pro/) 获取 Token
2. 设置环境变量：

```bash
# Windows PowerShell
$env:TUSHARE_TOKEN = "your_token"

# Linux / macOS
export TUSHARE_TOKEN=your_token
```

3. 检查：

```bash
python cli.py --status
```

4. 实盘拉取：

```bash
python cli.py --assemble --live --symbols 600519.SH,300750.SZ --session-mode mixed
```

## 无 Token

使用 fixture 演示全流程：

```bash
python cli.py --assemble --symbols 600519.SH,300750.SZ --copy-trace
```

## 指数权限

部分 `optional` 指数（如中证2000、行业指数）可能因积分不足拉取失败，会自动跳过并写入 `meta.fetch_messages`；Agent 应在 `gaps[]` 说明。
