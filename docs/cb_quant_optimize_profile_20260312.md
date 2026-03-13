# CB Quant 优化链路 Profiling 记录（2026-03-12）

## 1. 本次 profiling 目标

确认当前优化任务的热点到底还在线程/调度层，还是已经转移到候选池计算本身。

本次关注函数：

- `_build_candidate_code_map_payload(...)`
- `prepare_candidate_pool(...)`
- `build_candidate_codes(...)`

## 2. 本次样本

- 模板：`TPL-1614 / 双因子策略-remain_cap-list_days`
- 窗口：`1y`
- 组合数：`1`
- 样本交易日：`10`
- 执行方式：单进程直接 `cProfile`，调用 `_evaluate_combo_payload(...)`

说明：

- 这里不是全量实验批次，只是一个真实模板 + 真实快照的热点抽样。
- 目标是看“时间花在哪”，不是给出完整吞吐上限。

## 3. 关键结论

### 3.1 热点已经明显落在候选池构建，而不是外层任务调度

本次 `cProfile` 主要结果：

- `_evaluate_combo_payload(...)`：`0.502s`
- `_build_candidate_code_map_payload(...)`：`0.483s`
- `build_candidate_codes(...)`：`0.483s`
- `_score_candidate_frame(...)`：`0.420s`
- `prepare_candidate_pool(...)`：`0.110s`

结论：

- 单组合评估的主要耗时已经集中在“逐日生成候选债代码”这条链路。
- 外层线程池/任务池并不是当前单组合热点。
- 因此把组合评估切到 `ProcessPoolExecutor` 是正确方向，但再往后提速，主战场已经转到候选池计算。

### 3.2 `prepare_candidate_pool(...)` 已经起到作用，但不是最终热点

从结果看：

- `prepare_candidate_pool(...)` 总耗时约 `0.110s`
- `_build_candidate_code_map_payload(...)` 总耗时约 `0.483s`

这说明：

- 预计算候选池确实压掉了一部分重复工作。
- 但后续 `build_candidate_codes(...)` + `_score_candidate_frame(...)` 仍然很重。
- 下一阶段如果继续提速，重点不是再搬运更多线程，而是减少 `build_candidate_codes(...)` 里的 pandas 计算和中间对象创建。

### 3.3 真正重的不是 Python for-loop，而是 pandas 运算和 DataFrame 复制/写列

高频耗时栈里主要是：

- `pandas.core.generic.clip`
- `pandas.core.generic.where`
- `pandas.core.series._logical_method`
- `DataFrame.__setitem__`
- `astype`
- `take / copy / reindex / insert`

说明：

- 现在最重的是 pandas 列运算、布尔筛选、类型转换、列写回和复制。
- 这也解释了为什么单纯加线程后收益会逐步变小。

### 3.4 已落地一轮热点修正：`build_candidate_codes(...)` 改走轻量评分路径

2026-03-12 本轮重构里，`build_candidate_codes(...)` 已不再复用“带全部中间分数字段的明细 DataFrame”路径，
而是只计算排序所需的 `weight_score + bond_code`，避免每次组合评估都为候选池构造十几列分数字段。

补充做了一个局部微基准（240 只转债、200 次循环、包含 `list_days + remain_size` 动态因子）：

- `build_candidate_codes(...)` 平均：`21.884 ms`
- `filter_multiple_factors(...)` 平均：`37.495 ms`
- 当前轻量候选代码路径约快：`1.71x`

说明：

- 这不是全链路吞吐测试，只是验证“候选代码生成”这一层的热点修正确实有效。
- 全链路优化任务仍然会受到回测执行、SQLite 状态刷新和窗口切片等因素影响。

## 4. 当前优化方向排序

按收益优先级，建议继续做：

1. 保持组合评估走多进程。
2. 继续把很多小任务合并成 bundle，减少外层调度和落库次数。
3. 继续压缩 shard 粒度，但要边测边看吞吐。
4. 重点改 `build_candidate_codes(...) / _score_candidate_frame(...)`：
   - 减少 `copy()`
   - 减少逐列 `__setitem__`
   - 减少重复 `astype`
   - 尽量把一组分数计算合并，避免多次中间 Series 生成
5. 如果还要继续上量，做“多进程 worker + 只读快照缓存”。

## 5. 暂不建议的方向

- 继续单纯堆线程数
- 继续增加任务条数
- 继续把一个实验拆成很多超小 task

这些方向会放大调度和 SQLite 落库开销，但不会解决候选池计算的主热点。

## 6. 本次原始热点摘录

来自 `cProfile` 的前几项：

```text
_evaluate_combo_payload            0.502s
_build_candidate_code_map_payload  0.483s
build_candidate_codes              0.483s
_score_candidate_frame             0.420s
prepare_candidate_pool             0.110s
```

## 7. 对应代码位置

- `vnpy/web/services/cb_quant_service.py / _evaluate_combo_payload`
- `vnpy/web/services/cb_quant_service.py / _build_candidate_code_map_payload`
- `vnpy/web/core/cb_backtest/candidate_selection.py / prepare_candidate_pool`
- `vnpy/web/core/cb_backtest/candidate_selection.py / build_candidate_codes`
- `vnpy/web/core/cb_backtest/candidate_selection.py / _score_candidate_frame`
