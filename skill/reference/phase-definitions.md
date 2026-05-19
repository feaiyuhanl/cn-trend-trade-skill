# 趋势四阶段定义（给 Agent）

| 阶段 | 英文 key | 典型观测 |
|------|----------|----------|
| 启动期 | startup | 突破盘整/前高；均线由粘合转多；量能初放 |
| 加速期 | acceleration | HH/HL；回踩不破关键均线；上涨放量回调缩量 |
| 衰竭期 | exhaustion | 新高量能跟不上；乖离过大；上影增多 |
| 反转期 | reversal | 结构破坏；关键 MA 失守；放量下跌 |
| 不明 | unclear | 数据不足或信号矛盾 |

阶段判断须引用 Pack 中 bars / derived_hints，并在 trace step 中写清**反面证据**（若存在）。
