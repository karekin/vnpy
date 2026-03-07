# 回测结果正确性论证报告（示例任务：OPT-20260226-0006）

## 1. 目标与范围
- 目标：用一个已完成任务证明页面上的关键图表与字段是可复算、可解释的。
- 任务：`OPT-20260226-0006`
- 策略：`CMB-000001`（模板：双三因子基准策略-F2-0009）
- 窗口：`1y`
- 初始资金：`100 万`

本报告覆盖：
- 最优策略榜单字段（稳健分/CAGR/MDD/CALMAR/收益%）
- 回测结果总表（当前策略/基准策略/相对超额/绝对超额）
- 回测走势图（5条线）
- 回报分布（年度）
- 持仓轮换（换手率）
- 当前市场 Top20 评分（以第1名债券举例）

---

## 2. 计算口径（代码依据）
- 分析主流程：`/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py:764`
- 策略净值/回撤/换手/轮换明细：`/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py:2365`
- 基准净值：`/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py:2562`
- 指标计算：`/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py:2610`
- 指标行组装（当前/基准/相对/绝对）：`/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py:2705`
- 年/月/周分布：`/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py:2749`
- Top20 打分：`/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py:2286`
- 稳健分公式：`/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py:2972`

---

## 3. 关键公式

### 3.1 净值与收益
- 单日收益率：`r_t = NAV_t / NAV_{t-1} - 1`
- 累计收益率：`TotalReturnPct = (NAV_end - 1) * 100`
- 累计资产(万)：`AssetWan = InitialCapitalWan * NAV_end`

### 3.2 年化收益
- `years = max(sample_days / 244, 1/244)`
- `AnnualReturnPct = (NAV_end^(1/years) - 1) * 100`

### 3.3 最大回撤与持续天数
- `Drawdown_t = NAV_t / Peak_t - 1`
- `MaxDrawdownPct = min_t(Drawdown_t) * 100`
- 回撤持续天数：连续 `Drawdown_t < 0` 的最长区间长度

### 3.4 夏普/索提诺/卡玛
- `Sharpe = mean(r) / std(r) * sqrt(244)`
- `Sortino = mean(r) / downside_std(r<0) * sqrt(244)`
- `Calmar = AnnualReturnPct / abs(MaxDrawdownPct)`

### 3.5 相对/绝对超额
- 相对超额（每个字段）：`当前策略 - 基准策略`
- 绝对超额（每个字段）：`当前策略`（代码定义）

### 3.6 回报分布（年度/月度/周度）
- 某周期复合收益：`(Π(1+r_t) - 1) * 100`
- 超额收益：`策略周期收益 - 基准周期收益`

### 3.7 Top20 单券评分
- `score = bond_ratio*price_score + stock_ratio*(premium_score*premium_ratio + stdev_score*0.2 + remain_score*remain_ratio + pb_score*0.1)`
- 其中：
  - `price_score = 1 - (price - price_benchmark)/price_benchmark`
  - `premium_score = 1 - (premium_rt - premium_benchmark)/premium_benchmark`
  - `bond_ratio = 1 - stock_ratio`
  - `stdev_score/pb_score/remain_score`按代码分段截断

---

## 4. 实测复算结果（OPT-20260226-0006）

## 4.1 回测总表字段核对
独立复算（用分析曲线重建日收益，再按上面公式计算）与页面值一致（四舍五入后一致）：

| 指标 | 当前策略（页面） | 当前策略（复算） | 基准策略（页面） | 基准策略（复算） |
|---|---:|---:|---:|---:|
| 总收益率(%) | 17.6331 | 17.6331 | 27.0715 | 27.0715 |
| 累计资产(万) | 117.6331 | 117.6331 | 127.0715 | 127.0715 |
| 年化收益率(%) | 17.7911 | 17.7911 | 27.3234 | 27.3234 |
| 最大回撤(%) | -3.8368 | -3.8368 | -8.5267 | -8.5267 |
| 夏普比 | 2.5360 | 2.5360 | 1.8722 | 1.8722 |
| 索提诺比 | 1.9231 | 1.9231 | 1.7121 | 1.7121 |
| 卡玛比 | 4.6369 | 4.6369 | 3.2045 | 3.2044 |
| 日均换手(%) | 10.2801 | 10.2801 | 0.0000 | 0.0000 |
| 交易周期 | 50 | 50 | 242 | 242 |

说明：
- “相对超额”行按字段逐项做差，例如：
  - `总收益率相对超额 = 17.6331 - 27.0715 = -9.4384`
  - 与页面一致。
- “绝对超额”行等于“当前策略”行（代码定义）。

## 4.2 回测走势图核对
- 末日（`2026-02-25`）曲线点：
  - `策略累计收益 = 17.6331%`
  - `基准累计收益 = 27.0715%`
  - `相对超额 = 17.6331 - 27.0715 = -9.4384%`
  - `绝对超额 = 17.6331%`
- 最大回撤点出现在 `2025-04-07`，`drawdown = -3.8368%`，与总表 MDD 一致。

## 4.3 回报分布（年度）核对
按年度复利聚合得到：
- `2025年`：策略 `17.6331%`，基准 `15.5462%`，超额 `2.0869%`
- `2026年`：策略 `0.0000%`，基准 `9.9746%`，超额 `-9.9746%`

与页面年度分布柱状图一致。

## 4.4 持仓轮换图核对（示例点）
以 `2025-09-30` 为例（页面悬浮点显示换手率 `100%`）：
- 前一调仓日（`2025-09-29`）持仓：`{127033}`
- 当日持仓：`{127033, 110092}`
- 变动数：`|prev-cur| + |cur-prev| = 0 + 1 = 1`
- 前一日持仓数：`1`
- `turnover = 1 / 1 * 100% = 100%`

与图中 `100%` 完全一致。

## 4.5 最优策略榜单字段核对（单任务）
页面榜单第1名（`CMB-000001`）：
- `CAGR = 0.177121 -> 17.7121%`
- `MDD = 0.038369 -> 3.8369%`
- `CALMAR = CAGR / MDD = 0.177121 / 0.038369 = 4.616253`
- `收益% = 17.6335`
- `稳健分 = 100.0`

稳健分按公式代入后命中上限 100（与页面一致）。

注：
- 榜单值来自“优化阶段”的高性能评估口径；“回测结果”卡片来自“详细分析”口径。
- 两者大方向一致，个别小数位存在轻微差异（如 17.71% vs 17.79%）是口径差异，不是计算错误。

## 4.6 Top20 可转债评分核对（示例：#1 正邦转债 128114）
策略参数（来自任务最优参数）：
- `price_benchmark=90`
- `premium_benchmark=25`
- `stock_ratio=0.3`
- `premium_ratio=0.3`
- `stock_stdevry_benchmark=20`
- `remain_ratio=0.15`

该券输入（同一快照）：
- `price=86.259`
- `premium_rt=15.2`
- `remain_scale_yi=11.7004`
- `stock_pb=-0.84`
- `stock_volatility=47.57`

代入子分项：
- `price_score = 1 - (86.259-90)/90 = 1.0416`
- `premium_score = 1 - (15.2-25)/25 = 1.3920`
- `remain_score = 1.0000`（处于 3~30 区间）
- `pb_score = 0.6000`（下限截断）
- `stdev_score = 1.5000`（上限截断）
- `bond_ratio = 0.7`

总分：
- `score = 0.7*1.0416 + 0.3*(1.3920*0.3 + 1.5*0.2 + 1.0*0.15 + 0.6*0.1)`
- `score = 1.0074`

与页面 `1.0074` 一致。

---

## 5. 结论
- 对任务 `OPT-20260226-0006`，页面主要字段与图表均可由后端原始序列按明确公式复算得到，数值一致（四舍五入后一致）。
- “回测总表 / 曲线 / 分布 / 轮换 / Top20评分”均可追溯到代码中的固定公式，具备可解释性和可审计性。
- 可将本报告作为对外说明模板：先给公式，再给代入值，再给误差（本例误差基本为 0）。
