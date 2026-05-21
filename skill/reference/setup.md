# 环境配置

## 依赖

```bash
pip install -r requirements.txt
```

## Tushare（实盘）

当日 K 线：Tushare 常滞后 1 个交易日；`fetch_live` 在缺失时会用 **akshare** 补全至最近 A 股收盘日（见 `requirements.txt`）。

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
