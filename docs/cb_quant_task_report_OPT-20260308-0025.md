# OPT-20260308-0025 回测任务取值推演报告

## 1. 报告用途

本报告针对优化任务 `OPT-20260308-0025`，逐项说明当前回测页面上各类数值的来源、计算路径、落库位置与展示口径。

这份报告分成两部分：

1. 当前页面实际上展示了什么值，这些值从哪里来。
2. 这些值里哪些可以对外作为“准确结果”背书，哪些目前还存在口径风险。

结论先行：

- 任务最佳组合是 `CMB-000006`，模板是 `TPL-1265 / 双因子策略-dblow-limit`。
- 该组合的真实双因子参数是 `dblow=105.0`、`limit=1.0`。
- 优化排行榜中的最佳策略摘要结果是可复算的，真实值为：
  - `总收益 33.6732%`
  - `CAGR 0.339942`
  - `MDD 0.053671`
  - `Calmar 6.333813`
  - `胜率 61.6613%`
  - `换手 1.298755`
  - `稳健分 100.0`
- 但当前页面上的“最佳策略分析结果”不是该组合的真实详细分析结果，而是丢失双因子参数后重算出来的结果：
  - 页面当前显示 `总收益 31.4619%`
  - 与真实组合结果 `33.6732%` 不一致
- 当前页面上的“转债等权基准”和“超额收益”也不能对外宣称准确，因为基准曲线当前被算成了 0。

因此：

- 这份报告可以作为内部技术审计报告。
- 如果要作为对甲方的“准确性背书材料”，建议先修正两处问题并重新生成该任务的分析快照，再对外演示。

---

## 2. 本任务的原始落库对象

### 2.1 任务主记录

来源表：`out/cb_quant/_cb_quant/cb_quant.db / cb_optimize_task`

该任务主记录为：

- `task_id`: `OPT-20260308-0025`
- `template_id`: `TPL-1265`
- `template_name`: `双因子策略-dblow-limit`
- `status`: `finished`
- `progress`: `100`
- `total_combinations`: `51`
- `evaluated_combinations`: `51`
- `windows`: `["1y"]`
- `start_date`: `2023-03-08`
- `end_date`: `2026-03-08`
- `task_config.initial_capital_wan`: `100.0`
- `task_config.benchmark_name`: `转债等权`
- `task_config.rebalance_interval_type`: `trade_day`
- `task_config.rebalance_interval_value`: `1`
- `task_config.max_hold_count`: `12`
- `task_config.max_position_pct`: `20.0`

页面上任务标题、任务状态、窗口、任务消息等字段，都是从这里来的。

### 2.2 模板配置

来源表：`out/cb_quant/_cb_quant/cb_quant.db / cb_strategy_template_config`

`TPL-1265` 的配置如下：

- `factor_keys = ["dblow", "limit"]`
- `dblow` 参数空间：`100.0 ~ 180.0`，步长 `5.0`
- `limit` 参数空间：`-1.0 ~ 1.0`，步长 `1.0`
- `combo_size = 51`

组合总数 `51` 的来源是：

- `dblow` 一共有 17 个取值：`100, 105, 110, ..., 180`
- `limit` 一共有 3 个取值：`-1, 0, 1`
- 总组合数 `17 * 3 = 51`

这与任务表里的 `total_combinations=51` 一致。

### 2.3 最佳策略摘要结果

来源表：`out/cb_quant/_cb_quant/cb_quant.db / cb_optimize_result`

最佳行是：

- `rank = 1`
- `combo_id = CMB-000006`
- `robust_score = 100.0`
- `cagr = 0.339942`
- `mdd = 0.053671`
- `calmar = 6.333812`
- `win_rate = 61.6613`
- `turnover = 1.298755`
- `recent_1y = 0.336732`
- `total_return_pct = 33.6732`

这些值对应的是优化阶段的“排序摘要结果”。

### 2.4 分析快照

来源表：`out/cb_quant/_cb_quant/cb_quant.db / cb_optimize_task_analysis_snapshot`

该任务的分析快照为：

- `task_id = OPT-20260308-0025`
- `combo_id = CMB-000006`
- `window_name = 1y`
- `benchmark_name = 转债等权`
- `initial_capital_wan = 100.0`
- `used_range_start = 2025-03-10`
- `used_range_end = 2026-03-08`

页面上“回测结果”区块里的：

- 指标表
- 回测走势
- 年/月/周分布
- 持仓轮换

都是从这张快照里来的。

---

## 3. CMB-000006 这个组合到底是哪一组参数

### 3.1 组合编号如何展开

代码位置：`vnpy/web/services/cb_quant_service.py`

- `_iter_template_settings(...)`
- `_choices_for_param_row(...)`

模板参数按照 `product(*all_choices)` 展开，左边参数慢变，右边参数快变。

因此 `TPL-1265` 的前几个组合为：

1. `CMB-000001 = (dblow=100, limit=-1)`
2. `CMB-000002 = (dblow=100, limit=0)`
3. `CMB-000003 = (dblow=100, limit=1)`
4. `CMB-000004 = (dblow=105, limit=-1)`
5. `CMB-000005 = (dblow=105, limit=0)`
6. `CMB-000006 = (dblow=105, limit=1)`

所以本任务最佳组合 `CMB-000006` 的真实参数是：

- `selected_factor_keys = ["dblow", "limit"]`
- `factor_values = {"dblow": 105.0, "limit": 1.0}`

叠加任务级运行参数后的真实 setting 为：

```json
{
  "price_benchmark": 115.0,
  "premium_benchmark": 25.0,
  "stock_weight": 0.3,
  "premium_weight": 0.3,
  "volatility_benchmark": 30.0,
  "max_candidate_price": 130.0,
  "candidate_count": 12,
  "outstanding_amount_weight": 0.15,
  "max_hold_count": 12,
  "hold_until_profit": false,
  "selected_factor_keys": ["dblow", "limit"],
  "factor_values": {"dblow": 105.0, "limit": 1.0},
  "initial_capital_wan": 100.0,
  "benchmark_name": "转债等权",
  "rebalance_interval_type": "trade_day",
  "rebalance_interval_value": 1,
  "max_position_pct": 20.0,
  "exclude_redeem_days_below": null,
  "take_profit_pct": null,
  "stop_loss_pct": null
}
```

---

## 4. 页面上“TopN 策略排行”各列是怎么来的

前端展示位置：`frontend/src/app/(admin)/cb-quant/backtest-evaluation/page.tsx`

列为：

- 排名
- 任务ID
- 模板
- 组合ID
- 稳健分
- CAGR
- MDD
- Calmar
- 收益%
- 参数

### 4.1 排名

来源代码：`vnpy/web/services/cb_quant_service.py / _rank_optimize_rows(...)`

排序键：

1. `robust_score` 降序
2. `cagr` 降序
3. `mdd` 升序

即：

```text
sorted(rows, key=lambda item: (item.robust_score, item.cagr, -item.mdd), reverse=True)
```

本任务前 5 名为：

| 排名 | combo_id | robust_score | cagr | mdd | calmar | total_return_pct |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | CMB-000006 | 100.0 | 0.339942 | 0.053671 | 6.333812 | 33.6732 |
| 2 | CMB-000004 | 100.0 | 0.338622 | 0.053671 | 6.309217 | 33.5426 |
| 3 | CMB-000002 | 100.0 | 0.328083 | 0.053924 | 6.084174 | 32.4998 |
| 4 | CMB-000007 | 100.0 | 0.322201 | 0.051460 | 6.261193 | 31.9178 |
| 5 | CMB-000009 | 100.0 | 0.322201 | 0.051460 | 6.261193 | 31.9178 |

### 4.2 CAGR / MDD / Calmar / 胜率 / 换手 / recent_1y / 稳健分

来源代码：

- `vnpy/web/services/cb_quant_service.py / _evaluate_combo(...)`
- `vnpy/web/services/cb_quant_service.py / _derive_leaderboard_metrics(...)`
- `vnpy/web/services/cb_quant_service.py / _calculate_robust_score(...)`

对 `1y` 单窗口任务，聚合逻辑实际上退化成“单窗口指标直接入榜”。

具体公式：

- `total_return = total_return_pct / 100`
- `mdd = max_drawdown_pct / 100`
- `years = sample_days / 244`
- `cagr = (1 + total_return) ** (1 / years) - 1`
- `calmar = cagr / mdd`
- `turnover = trade_count / rebalanced_days`，并裁剪到 `[0, 2]`
- `recent_1y = total_return`

稳健分公式：

```text
score = 55
      + clamp(cagr * 120, -35, 35)
      + clamp((0.25 - mdd) * 80, -20, 22)
      + clamp(calmar * 6, -8, 18)
      + clamp((win_rate_pct - 50) * 0.6, -10, 12)
      + clamp((0.30 - turnover) * 20, -8, 8)
```

本任务最佳组合 `CMB-000006` 的真实轻量回测统计为：

- `total_return_pct = 33.6732`
- `max_drawdown_pct = 5.3671`
- `trade_count = 313`
- `win_rate_pct = 61.6613`
- `sample_days = 242`
- `rebalanced_days = 241`

代入后得到：

- `total_return = 0.336732`
- `mdd = 0.053671`
- `years = 242 / 244 = 0.991803...`
- `cagr = 0.339942`
- `calmar = 0.339942 / 0.053671 = 6.333813`
- `turnover = 313 / 241 = 1.298755`
- `recent_1y = 0.336732`

稳健分分项：

- 基础分 `55`
- CAGR 项：`0.339942 * 120 = 40.79`，裁剪为 `+35`
- 回撤项：`(0.25 - 0.053671) * 80 = 15.70632`
- Calmar 项：`6.333813 * 6 = 38.00`，裁剪为 `+18`
- 胜率项：`(61.6613 - 50) * 0.6 = 6.99678`
- 换手项：`(0.30 - 1.298755) * 20 = -19.9751`，裁剪为 `-8`

合计：

```text
55 + 35 + 15.7063 + 18 + 6.9968 - 8 = 122.7031
```

再裁剪到上限 `100`，所以页面显示：

- `稳健分 = 100.00`

### 4.3 参数列

当前页面参数列展示的是 `row.params` 的 JSON。

但这里有一个关键问题：

- `row.params` 持久化时只保留了标量字段
- `selected_factor_keys`
- `factor_values`

这两个真正代表组合差异的字段被丢掉了

所以页面参数列现在展示的是：

- 基础多因子默认参数
- 任务级运行参数

而不是 `CMB-000006` 的真实双因子参数。

因此页面参数列当前**不具备完整审计意义**。

---

## 5. 页面上“当前市场 Top20 可转债”各列是怎么来的

来源：

- 数据源：`CbMarketService.list_bonds(...)`
- 排序代码：`vnpy/web/services/cb_quant_service.py / _score_current_market(...)`
- 持久化表：`cb_optimize_top_bond`

### 5.1 评分公式

最佳策略当前市场评分使用以下参数：

- `price_benchmark = 115`
- `premium_benchmark = 25`
- `stock_weight = 0.3`
- `bond_weight = 0.7`
- `premium_weight = 0.3`
- `outstanding_amount_weight = 0.15`
- `volatility_benchmark = 30`
- `max_candidate_price = 130`

对每一只债：

```text
premium_score = 1 - (premium_rt - 25) / 25
price_score   = 1 - (price - 115) / 115
remain_score  = 按剩余规模分段打分
pb_score      = 以 1.5 为基准打分，缺失时退回 1.0
stdev_score   = 以 30 为基准打分

score = 0.7 * price_score
      + 0.3 * (
            premium_score * 0.3
          + stdev_score * 0.2
          + remain_score * 0.15
          + pb_score * 0.1
        )
```

最终按：

1. `score` 降序
2. `amount_wan` 降序

排序后取前 20。

### 5.2 当前页面显示的 Top20

来源消息为：`Top20基于 tushare.pro(2026-03-06)（非实时）`

当前 20 行如下：

| 排名 | 债券代码 | 名称 | 现价 | 转股溢价率 | 双低 | 成交额(万) | 评分 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 128044 | 岭南转债 | 71.372 | -43.55% | 27.822 | 0.0 | 1.4315 |
| 2 | 127033 | 中装转2 | 89.726 | 0.31% | 90.036 | 0.0 | 1.1922 |
| 3 | 123210 | 信服转债 | 105.770 | -0.10% | 105.670 | 25692.6 | 1.0553 |
| 4 | 110067 | 华安转债 | 106.999 | 0.07% | 107.069 | 61526.3 | 1.0449 |
| 5 | 118008 | 海优转债 | 110.761 | -0.16% | 110.601 | 13092.5 | 1.0214 |
| 6 | 123221 | 力诺转债 | 122.000 | -0.44% | 121.560 | 30839.9 | 0.9930 |
| 7 | 113574 | 华体转债 | 117.818 | 4.84% | 122.658 | 5040.2 | 0.9927 |
| 8 | 113623 | 凤21转债 | 120.584 | -1.20% | 119.384 | 0.0 | 0.9892 |
| 9 | 128101 | 联创转债 | 110.048 | 13.50% | 123.548 | 10527.3 | 0.9866 |
| 10 | 113033 | 利群转债 | 109.955 | 16.20% | 126.155 | 8020.4 | 0.9727 |
| 11 | 110070 | 凌钢转债 | 122.155 | 1.11% | 123.265 | 7303.9 | 0.9677 |
| 12 | 123146 | 中环转2 | 124.300 | -0.34% | 123.960 | 15076.2 | 0.9499 |
| 13 | 127016 | 鲁泰转债 | 110.844 | 22.85% | 133.694 | 5596.7 | 0.9453 |
| 14 | 110092 | 三房转债 | 104.483 | 36.60% | 141.083 | 19949.8 | 0.9423 |
| 15 | 113584 | 家悦转债 | 113.479 | 20.14% | 133.619 | 2999.8 | 0.9330 |
| 16 | 128127 | 文科转债 | 118.810 | 17.74% | 136.550 | 2802.7 | 0.9206 |
| 17 | 123049 | 维尔转债 | 128.730 | 2.01% | 130.740 | 1745.8 | 0.9125 |
| 18 | 110085 | 通22转债 | 126.596 | 0.00% | 126.596 | 0.0 | 0.9064 |
| 19 | 128119 | 龙大转债 | 116.880 | 25.87% | 142.750 | 1929.7 | 0.9024 |
| 20 | 127018 | 本钢转债 | 123.650 | 10.25% | 133.900 | 5410.0 | 0.8941 |

### 5.3 Top1 评分的完整代入示例

以 `128044 / 岭南转债` 为例：

- `price = 71.372`
- `premium_rt = -43.55`
- `remain_scale_yi = 3.5909`
- `stock_volatility = 27.10`
- `stock_pb = None`，退回默认基准 `1.5`

分项为：

- `price_score = 1 - (71.372 - 115) / 115 = 1.3794`
- `premium_score = 1 - (-43.55 - 25) / 25 = 3.7420`
- `remain_score = 1.0`（因为剩余规模位于 3~30 亿之间）
- `pb_score = 1.0`
- `stdev_score = 1 - (30 - 27.10) / 30 = 0.9033`

总代入：

```text
score
= 0.7 * 1.3794
+ 0.3 * (3.7420 * 0.3 + 0.9033 * 0.2 + 1.0 * 0.15 + 1.0 * 0.1)
= 0.9656 + 0.4659
= 1.4315
```

与页面展示完全一致。

### 5.4 Top2 评分的完整代入示例

以 `127033 / 中装转2` 为例：

- `price = 89.726`
- `premium_rt = 0.31`
- `remain_scale_yi = 0.0918`
- `stock_volatility = 20.44`
- `stock_pb = None`，退回默认基准 `1.5`

分项：

- `price_score = 1 - (89.726 - 115) / 115 = 1.2198`
- `premium_score = 1 - (0.31 - 25) / 25 = 1.9876`
- `remain_score = 1 - (0.0918 - 3) / 3 = 1.9694`
- `pb_score = 1.0`
- `stdev_score = 1 - (30 - 20.44) / 30 = 0.6813`

总代入：

```text
score
= 0.7 * 1.2198
+ 0.3 * (1.9876 * 0.3 + 0.6813 * 0.2 + 1.9694 * 0.15 + 1.0 * 0.1)
= 0.8538 + 0.3384
= 1.1922
```

与页面展示完全一致。

---

## 6. 页面上“回测结果”为什么会显示 31.4619%，而不是 33.6732%

这是本任务最关键的口径问题。

### 6.1 当前页面显示值

当前分析快照里的“当前策略”行是：

- `总收益率 = 31.4619%`
- `累计资产 = 131.4619 万`
- `年化收益率 = 31.9103%`
- `最大回撤 = -5.4418%`
- `Sharpe = 2.9671`
- `Sortino = 2.7213`
- `Calmar = 5.8639`
- `日均换手 = 29.0978%`
- `交易周期 = 425`
- `盈利周期 = 251`
- `亏损周期 = 174`
- `胜率 = 59.0588%`
- `盈亏比 = 2.4755`
- `平均每周期收益 = 0.7419%`
- `最大单周期盈利 = 34.8882%`
- `最大单周期亏损 = -5.7374%`
- `最大回撤持续天数 = 47`

这些值来自分析快照，不是来自排行榜摘要。

### 6.2 根因：真实组合因子在持久化时丢失了

问题代码：

- `vnpy/web/services/cb_quant_service.py / _serialize_setting(...)`

这里当前只保留标量字段：

```python
if isinstance(value, (int, float, str, bool)) or value is None:
    payload[key] = value
```

因此会丢失：

- `selected_factor_keys`
- `factor_values`

而 `CMB-000006` 的关键差异恰恰就在：

```json
{
  "selected_factor_keys": ["dblow", "limit"],
  "factor_values": {
    "dblow": 105.0,
    "limit": 1.0
  }
}
```

这两个字段丢失后：

- 排行榜还能显示历史摘要值
- 但分析快照在重建 setting 时拿不到真实双因子参数
- 最终只能按“基础多因子默认参数”重跑详细分析

因此当前页面上的分析结果，实际上不是 `CMB-000006` 的真实详细分析。

### 6.3 证据链

#### A. 持久化后的最佳结果 params

`cb_optimize_result` 里保存的 `params` 不包含：

- `selected_factor_keys`
- `factor_values`

#### B. 用持久化后的 params 重算分析

得到：

- `总收益 = 31.4619%`
- `nav_end = 1.314619`

这与当前分析快照完全一致。

#### C. 用真实组合 setting 重算分析

即使用：

```json
{
  "selected_factor_keys": ["dblow", "limit"],
  "factor_values": {"dblow": 105.0, "limit": 1.0}
}
```

再做详细回放，得到：

- `总收益 = 33.6732%`
- `累计资产 = 133.6732 万`
- `年化收益率 = 34.1570%`
- `最大回撤 = -5.3671%`
- `Sharpe = 3.3799`
- `Sortino = 3.2156`
- `Calmar = 6.3642`
- `日均换手 = 22.8571%`
- `交易周期 = 313`
- `盈利周期 = 193`
- `亏损周期 = 120`
- `胜率 = 61.6613%`
- `盈亏比 = 3.4116`
- `平均每周期收益 = 1.1690%`
- `最大单周期盈利 = 42.5439%`
- `最大单周期亏损 = -6.3974%`
- `最大回撤持续天数 = 35`

这与排行榜中的最佳策略摘要值对齐：

- `total_return_pct = 33.6732`
- `cagr = 0.339942`
- `mdd = 0.053671`
- `calmar = 6.333813`
- `win_rate = 61.6613`
- `turnover = 1.298755`

### 6.4 结论

对于这个任务：

- “TopN 排行榜”里的最佳组合摘要值是可信的。
- “最佳策略分析”区块当前显示的明细值不是该组合的真实明细。

所以当前页面上：

- `33.6732%` 和 `31.4619%` 同时存在，并不是一个合理现象。
- 这不是前端展示误差，而是后端参数持久化口径错误。

---

## 7. 页面上“基准 / 超额收益”为什么当前不能对外背书

问题代码：

- `vnpy/web/services/cb_quant_service.py / _simulate_equal_weight_benchmark(...)`

当前基准逻辑使用了：

```python
if len(common_idx) > 0 and "price" in prev_frame.columns and "price" in frame.columns:
    prev_prices = prev_frame.loc[common_idx, "price"].astype(float)
    cur_prices = frame.loc[common_idx, "price"].astype(float)
```

但历史快照的标准列是：

- `close_price`

而不是：

- `price`

结果是：

- 条件几乎永远不成立
- `daily_ret` 基本一直是 `0`
- 基准净值保持 `1.0`
- 基准累计收益保持 `0.0%`

这就导致页面上：

- `基准策略`
- `相对超额`
- `绝对超额`
- `基准累计收益`
- `超额收益分布`

全部建立在错误的零基准之上。

所以这部分当前不能对外作为“系统准确”的证明材料。

---

## 8. 页面上曲线、分布、轮动是怎么来的

来源代码：

- `vnpy/web/services/cb_quant_service.py / _simulate_detailed_strategy(...)`
- `vnpy/web/services/cb_quant_service.py / _compute_backtest_metrics(...)`
- `vnpy/web/services/cb_quant_service.py / _build_distribution_rows(...)`

### 8.1 样本区间

分析快照实际使用区间：

- `2025-03-10 ~ 2026-03-08`
- 共 `242` 个样本点

这来自：

- 任务窗口是 `1y`
- 实际历史快照的可用交易日从 `2025-03-10` 开始

### 8.2 首个交易日建仓

首日 `2025-03-10` 候选前 12 名即初始持仓：

1. `123099 普利转退`
2. `127033 中装转2`
3. `110092 三房转债`
4. `127047 帝欧转债`
5. `118020 芳源转债`
6. `123175 百畅转债`
7. `123128 首华转债`
8. `118027 宏图转债`
9. `128108 蓝帆转债`
10. `127061 美锦转债`
11. `118008 海优转债`
12. `127060 湘佳转债`

由于首日只建仓不计收益，所以：

- `2025-03-10`
  - `strategy_cum_return_pct = 0.0`
  - `nav_wan = 100.0`

### 8.3 次日收益 2.4127% 的推演

`2025-03-11` 的组合日收益是由“昨日持仓按等权计算当日涨跌幅贡献”得到。

每只仓位占比约为：

- `1 / 12 = 8.3333%`

组合日收益公式：

```text
day_return += ((cur_price - last_price) / last_price) * ratio
```

次日逐仓贡献示例：

- `123099`: `69.353 -> 83.224`，贡献显著正收益
- `127033`: `77.461 -> 78.400`
- `110092`: `80.122 -> 82.013`
- 其余 9 只债按同样公式累计

最终：

- `2025-03-11 day_return = 2.4127%`
- `nav = 102.4127 万`
- `cumulative_return_pct = 2.4127%`

这与当前分析快照首个有效收益点一致。

### 8.4 当前页面快照中的关键曲线点

当前页面快照显示：

- 起点：`2025-03-10`，累计收益 `0.0%`
- 第二天：`2025-03-11`，累计收益 `2.4127%`
- 最高点：`2026-02-25`，累计收益 `33.3512%`
- 终点：`2026-03-08`，累计收益 `31.4619%`
- 最大回撤点：`2025-04-07`，回撤 `-5.4418%`

### 8.5 当前页面快照中的分布

年度分布：

- `2025年 = 29.7724%`
- `2026年 = 1.3019%`

最佳月份：

- `2025-06 = 6.0837%`

最差月份：

- `2026-03 = -0.6595%`

最佳周：

- `2025-W11 = 5.1288%`

最差周：

- `2025-W35 = -2.4558%`

### 8.6 当前页面快照中的轮动

当前快照共有：

- `208` 条轮动记录

首条轮动：

- `2025-03-10`
- `holding_count = 12`
- `turnover_pct = 0.0`
- `nav_wan = 100.0`

末条轮动：

- `2026-03-08`
- `holding_count = 7`
- `turnover_pct = 108.3333%`
- `period_return_pct = 0.0%`
- `cumulative_return_pct = 31.4619%`
- `nav_wan = 131.4619`

注意：

- 这组轮动数据是当前页面快照值
- 它对应的是“丢失双因子参数后的分析重算结果”
- 不等同于 `CMB-000006` 的真实双因子详细轮动

---

## 9. 对甲方汇报时，哪些可以讲，哪些现在不建议讲

### 9.1 可以讲的

- 任务管理、模板管理、参数空间展开、组合编号生成的逻辑是清楚且可追溯的。
- `TPL-1265` 的参数空间、`51` 个组合的来源、`CMB-000006` 的真实因子值，都可以明确推回。
- 当前市场 Top20 打分逻辑是透明的，且以 `岭南转债`、`中装转2` 为例可以逐项复算到页面分数。
- 优化排行榜里的最佳组合摘要结果 `33.6732% / 0.339942 / 0.053671 / 6.333812` 是可以复算出来的。

### 9.2 现在不建议对外承诺“完全准确”的

1. 最佳策略分析页  
原因：真实组合因子在持久化时丢失，导致分析页不是按真实组合重算。

2. 基准收益与超额收益  
原因：当前基准计算读取了错误列名，基准净值被算成了一条平的 0 曲线。

3. 参数列  
原因：当前参数列没有展示真实 `factor_values`，无法让客户看到组合真实差异。

---

## 10. 对外演示前的最低修正建议

如果目标是“拿这页直接向甲方证明产品准确且值得购买”，建议至少先做三件事：

1. 修正 `cb_optimize_result.params` 的持久化口径  
要求把：
   - `selected_factor_keys`
   - `factor_values`
   一并持久化下来。

2. 修正基准计算列名  
把 `_simulate_equal_weight_benchmark(...)` 中的 `price` 改为真实快照列 `close_price`。

3. 重新跑 `OPT-20260308-0025` 或重新生成其 analysis snapshot  
这样：
   - 排行榜
   - 分析页
   - 基准/超额
   三者才能口径一致。

---

## 11. 最终判断

对于 `OPT-20260308-0025` 这个具体任务：

- 系统“优化排序能力”和“当前市场评分能力”已经具备可审计性。
- 但“最佳策略详细分析”和“基准/超额收益”当前还不具备对外背书条件。

因此，这个任务当前更适合作为：

- 内部排查报告
- 技术审计材料
- 修复前的验收清单

而不建议直接作为“对甲方证明结果绝对准确”的销售材料。

如果要变成可对外汇报的版本，建议先修 bug、重算任务，再基于修正后的快照出第二版对外报告。
