# 可转债策略笔记归档

这份文档整理自原 `convertible-bond-crawler/docs/谈谈自己的可转债策略.md`，保留其中仍有参考价值的策略思想。

## 可转债的几个核心要素

原文强调了 4 个核心要素：

1. 转股价
2. 下修转股价条款
3. 强制赎回条款
4. 回售条款

围绕这 4 个要素，可以衍生出：

- 转股溢价率
- 到期收益率
- 回售收益率
- 双低/三低
- 下修博弈
- 强赎风险

## 四象限理解

原文把可转债粗分成四象限：

- 一象限：高价格，高溢价率，债性弱，股性强
- 二象限：低价格，高溢价率，债性强，股性弱
- 三象限：低价格，低溢价率，债性强，股性强
- 四象限：高价格，低溢价率，债性弱，容易强赎

原作者更偏向第二、第三象限，因为它们更符合“本金安全优先”的思路。

## 几类代表性策略

### 到期保本

核心特征：

- 税后到期收益率为正
- 已到转股期
- 转股价格 / 每股净资产有下修空间
- 满足下修条件且不处于承诺不下修期

核心思想：

- 先保本
- 再博弈下修和正股上涨

### 回售摸彩

核心特征：

- 进入回售期
- 满足下修股价要求
- 转债剩余 / 市值比例较高
- 转股价格 / 每股净资产有下修空间
- 价格不能太高，要保留一定安全垫

核心思想：

- 回售条款提供下沿保护
- 下修动力更强

### 低价格低溢价

核心特征：

- 低溢价
- 价格不过高
- 已到转股期
- 不在强赎区间

核心思想：

- 兼顾防御性和攻击性
- 既要债底，又要跟随正股弹性

### 三低转债

核心特征：

- 无强赎
- 剩余规模小
- 溢价率低或价格不高
- 正股市值小
- 距离到期还有一定时间

核心思想：

- 借助小规模和高弹性去寻找潜在高波动标的

## 组合操作思路

原文建议采用摊大饼方式，而不是押注单一标的：

- 一次持有 10 到 15 只左右
- 优先挑选回售摸彩和低价格低溢价中的优质标的
- 再从到期保本中补充仓位

这套思想后来也延续到了 `Phase A` 的候选池和轻量回测逻辑里：

- 每个交易日先生成候选池
- 再根据候选池构建持仓
- 再按规则轮动

## 和当前 `vnpy cb-quant` 的关系

这些策略思想并没有被丢弃，而是已经被吸收到当前的 Phase A 核心中：

- 默认参数：[settings.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/domain/cb_quant/cb_strategy_core/settings.py)
- 多因子打分：[scoring.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/domain/cb_quant/cb_strategy_core/scoring.py)
- 候选池生成：[candidates.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/domain/cb_quant/cb_strategy_core/candidates.py)
- 轻量回测：[backtest.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/domain/cb_quant/cb_strategy_core/backtest.py)

因此，这份文档今天的意义更偏“策略思想档案”，而不是运行文档。
