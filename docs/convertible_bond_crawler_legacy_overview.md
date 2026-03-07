# `convertible-bond-crawler` 历史归档说明

这份文档用于承接原 `convertible-bond-crawler/Readme.md` 中仍有参考价值的内容，供 `vnpy cb-quant` 后续维护者理解该项目的历史背景。

## 原项目提供过的能力

原 `convertible-bond-crawler` 项目主要做过 4 类事情：

1. 获取可转债市场数据
2. 根据多种策略筛选标的
3. 基于筛选结果执行轻量回测
4. 输出 Excel、HTML、JSON 等离线分析结果

在融合前，它的能力大致可以拆成两层：

- 策略核心层
  - 多因子打分
  - 候选池生成
  - Phase A 轻量回测
- 旧数据/报表层
  - 网页抓取
  - Excel 快照
  - HTML 报表
  - 本地日志

## 原项目中的典型策略分类

原 README 中列出的核心策略包括：

- 到期保本
- 回售摸彩
- 低价格低溢价
- 三低转债
- 下修博弈
- 次新债
- 多因子策略

这些策略的共性是：围绕可转债价格、转股溢价率、剩余规模、正股市值、波动率、下修空间、强赎风险等字段构造筛选条件。

## 多因子策略的核心思路

原项目中的多因子策略，主要综合了以下几个维度：

1. 转债价格
2. 转股溢价率
3. 剩余规模
4. 正股市值
5. 到期时间/期权价值
6. 正股波动率
7. 正股 PB

这些维度后来已经迁入 `vnpy` 的 Phase A 核心中，当前实现位于：

- [settings.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/domain/cb_quant/phase_a_core/settings.py)
- [scoring.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/domain/cb_quant/phase_a_core/scoring.py)
- [candidates.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/domain/cb_quant/phase_a_core/candidates.py)
- [backtest.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/domain/cb_quant/phase_a_core/backtest.py)

## 原数据流与当前状态

原项目的主数据流是：

- 网页抓取 -> 本地 Excel 快照 -> 回测 / 报表

融合后，`vnpy cb-quant` 的主数据流已经改为：

- Tushare / 市场服务 -> `cb_snapshots.db` -> 回测 / 优化 / 分析页

也就是说：

- Excel、HTML、JSON 这些旧产物不再是运行时主路径
- `convertible-bond-crawler` 不再承担生产环境运行角色
- 当前运行时只保留其曾经沉淀下来的 Phase A 策略逻辑

## 历史定位

从系统演化角度看，`convertible-bond-crawler` 可以被理解为：

- `vnpy cb-quant` 的前身策略原型仓库
- Phase A 策略逻辑的最早沉淀来源
- 一个先有离线研究脚本、后被平台化吸收的历史模块

## 当前建议

如果后续继续维护 `cb-quant`，应直接阅读和修改 `vnpy` 内部的 Phase A 核心实现，而不是再恢复旧项目结构：

- [phase_a_core/__init__.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/domain/cb_quant/phase_a_core/__init__.py)

原 `convertible-bond-crawler` 目录已经退出运行时角色，保留下来的价值主要是策略思想和历史资料，而不是执行路径。
