# `convertible-bond-crawler` 融合进 `vnpy` 的重构方案

## 1. 文档目标

这份文档回答 4 个核心问题：

1. `convertible-bond-crawler` 在当前系统中的定位是什么
2. 它和 `vnpy/web` 哪些组件重叠，哪些能力仍不可替代
3. 是否应该融合进 `vnpy`
4. 如果要融合，应该按什么顺序做，风险怎么控制

本文档默认目标不是“保留两个长期并行演进的系统”，而是逐步把 `convertible-bond-crawler` 中仍有价值的策略核心吸收进 `vnpy cb-quant` 体系。

## 2. 当前现状

### 2.1 `convertible-bond-crawler` 的能力构成

当前子项目可以拆成两大块：

1. 策略核心层
   - 历史文件：`convertible-bond-crawler/filter.py`
   - 历史文件：`convertible-bond-crawler/config.py`
   - 历史文件：`convertible-bond-crawler/scripts/phase_a_optimize.py`
   - 这部分承载了多因子打分、候选池构造、轻量回测逻辑

2. 老数据/报表脚本层
   - 历史文件：`convertible-bond-crawler/main.py`
   - `utils/*`
   - `out/*.xlsx`
   - `html/*.html`
   - `log/*.json`
   - 这部分承载了网页抓取、Excel 快照、静态报表和离线运行流程

### 2.2 `vnpy/web` 的现有能力

`vnpy/web` 已经接管了大量“平台层”能力：

- 市场数据读取：[cb_market_service.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_market_service.py)
- Tushare 同步与因子/事件数据落库：[cb_tushare_service.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_tushare_service.py)
- 历史快照维护：[cb_history_service.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_history_service.py)
- 模板、候选、回测、优化任务编排：[cb_quant_service.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py)
- 历史快照适配桥：[crawler_phase_a_adapter.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/adapters/crawler_phase_a_adapter.py)

### 2.3 当前系统关系

当前实际状态不是两个完全独立系统，而是：

- `vnpy/web` 已经接管了数据通道、任务系统、前后端展示
- `convertible-bond-crawler` 当时仍然提供 Phase A 策略内核
- 两者当时通过 `CrawlerPhaseABacktestAdapter` 做桥接

可以理解为：

- `vnpy/web` 是平台外壳
- `convertible-bond-crawler` 曾经是被动态加载的策略遗产内核

## 3. 在 `vnpy` 中的生态位判断

### 3.1 它最像什么

`convertible-bond-crawler` 在 `vnpy` 中没有完全对应的单一组件。

它最接近的是：

- 一部分像“策略规则内核”
- 一部分像“历史数据导出脚本”
- 一部分像“早期原型验证仓库”

所以它的生态位不是：

- 主数据通道
- 主任务系统
- 主展示层

而是：

**`cb-quant` 的 Phase A 策略内核来源仓库**

### 3.2 它当前不可替代的部分

真正仍然有价值、且还没有完全被 `vnpy` 原生替代的，是这几项：

- `filter_multiple_factors(...)` 及其一整套多因子打分口径
- `build_candidates(...)` 的候选池生成逻辑
- `build_strategy_config(...)` 的参数映射逻辑
- `run_backtest(...)` 的 crawler 口径轻量回测实现
- `normalize_market_frame(...)` 的兼容数据归一化逻辑

### 3.3 它已经被替代的部分

这些能力已经不应该继续作为主路径存在：

- 基于网页抓取生成 `out/*.xlsx`
- 从本地 Excel 作为主历史数据来源
- 离线 HTML/Excel 报表输出
- `main.py` 驱动的整条数据抓取和展示流程

## 4. 是否应该融合

结论：**应该融合，但应该做“拆分式融合”，不应该整仓搬迁。**

原因如下：

### 4.1 为什么应该融合

- 当前存在双重数据路径：`cb_snapshots.db` 和 `out/*.xlsx`
- 当前存在动态模块加载，影响 IDE 跳转、类型分析和重构稳定性
- 当前回测和优化逻辑仍然依赖旧脚本模块，架构边界不清晰
- 数据、任务、策略核心分散在两个仓库，维护成本高

### 4.2 为什么不能直接整仓搬迁

`convertible-bond-crawler` 里混有两类完全不同价值密度的内容：

- 高价值：策略内核
- 低价值或已过时：抓取脚本、Excel/HTML 输出、历史产物

如果整仓搬进 `vnpy`，会把已经被替代的旧流程也一起搬过去，架构会更乱。

## 5. 重构目标

目标不是“让 `vnpy` 可以运行 crawler”，而是：

**让 `vnpy cb-quant` 原生拥有 Phase A 策略内核，不再依赖 `convertible-bond-crawler` 作为外部运行时模块。**

目标状态应满足：

1. 策略核心代码直接位于 `vnpy` 仓内
2. 历史数据统一来自 `cb_snapshots.db` 或其后续统一数据库
3. 回测与优化不再依赖 Excel 文件
4. IDE 能直接跳转到策略内核代码
5. `convertible-bond-crawler` 最终只保留为历史归档，或彻底移除

## 6. 目标架构

建议在 `vnpy/web/domain/cb_quant/` 下引入一个新的策略核心包，例如：

```text
vnpy/web/domain/cb_quant/cb_strategy_core/
  __init__.py
  normalizer.py
  scoring.py
  candidates.py
  backtest.py
  settings.py
```

建议职责划分：

- `normalizer.py`
  - 来自 `normalize_market_frame(...)`
  - 负责回测快照字段归一化

- `settings.py`
  - 来自 `config.py` 中的 `multiple_factors_config`
  - 负责默认参数、参数映射、口径说明

- `scoring.py`
  - 来自 `filter.py` 中多因子打分与过滤逻辑
  - 负责债券过滤、打分字段、排序权重

- `candidates.py`
  - 来自 `build_candidates(...)`
  - 负责给定单日快照生成候选债列表

- `backtest.py`
  - 来自 `run_backtest(...)`
  - 负责轻量回测主循环

## 7. 文件迁移映射

### 7.1 建议保留并迁移

- 历史来源：`convertible-bond-crawler/filter.py`
  -> `vnpy/web/domain/cb_quant/cb_strategy_core/scoring.py`

- 历史来源：`convertible-bond-crawler/config.py`
  -> `vnpy/web/domain/cb_quant/cb_strategy_core/settings.py`

- 历史来源：`convertible-bond-crawler/scripts/phase_a_optimize.py`
  -> 拆分为：
  - `normalizer.py`
  - `candidates.py`
  - `backtest.py`
  - 可选保留一个 CLI 包装脚本

### 7.2 建议降级为兼容层

- [vnpy/web/adapters/crawler_phase_a_adapter.py](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/adapters/crawler_phase_a_adapter.py)

短期保留，长期目标是：

- 不再动态加载 `phase_a_optimize.py`
- 改成直接 import 新的 `cb_strategy_core` 模块

### 7.3 建议废弃为主路径

- 历史来源：`convertible-bond-crawler/main.py`
- `convertible-bond-crawler/out/*.xlsx`
- `convertible-bond-crawler/html/*.html`
- `convertible-bond-crawler/log/*.json`
- `convertible-bond-crawler/utils/*` 中仅服务于旧抓取流程的代码

## 8. 分阶段实施方案

建议分 5 个阶段做，不要一步到位。

### 阶段 1：策略核心代码镜像进 `vnpy`

目标：

- 在 `vnpy` 内建立 `cb_strategy_core` 目录
- 先不改业务调用路径，只把策略核心复制并整理进去

动作：

1. 把 `multiple_factors_config` 和相关映射迁入 `settings.py`
2. 把 `normalize_market_frame(...)` 迁入 `normalizer.py`
3. 把 `filter_multiple_factors(...)` 迁入 `scoring.py`
4. 把 `build_candidates(...)` 迁入 `candidates.py`
5. 把 `run_backtest(...)` 迁入 `backtest.py`

验收：

- 能在 `vnpy` 内部直接 import 这些模块
- 单元测试结果与现有 crawler 逻辑一致

### 阶段 2：让 adapter 从动态加载切换为原生 import

目标：

- 消除 `importlib.util.spec_from_file_location(...)`
- 提高 IDE 跳转、类型检查和可维护性

动作：

1. 保留 `CrawlerPhaseABacktestAdapter` 这个抽象层
2. 把内部 `_load_module()` 改成直接 import `cb_strategy_core`
3. 让 adapter 调用：
   - `normalize_market_frame`
   - `build_strategy_config`
   - `build_candidates`
   - `run_backtest`

验收：

- `CbQuantService` 不需要知道底层变化
- VS Code 可直接跳转策略核心函数

### 阶段 3：彻底去掉 Excel 作为主历史数据源

目标：

- 历史回测统一只走 `cb_snapshots.db`
- Excel 只作为一次性导入或历史备份

动作：

1. 保留 `CbHistoryService.bootstrap_from_crawler_snapshots()` 作为冷启动导入工具
2. 在 adapter 中把 `module.load_market_data(data_dir)` 的 fallback 降级
3. `CbTushareService` / `CbHistoryService` 成为唯一主数据入口

验收：

- 不依赖 `out/*.xlsx` 也能完成历史回测和优化
- 新环境部署不要求准备 Excel 快照

### 阶段 4：统一回测内核口径

目标：

- 避免 Web 侧和 crawler 侧长期存在两套“相似但不完全相同”的回测实现

动作：

1. 评估 `_run_backtest_from_candidate_map(...)` 和 `cb_strategy_core.backtest.run_backtest(...)` 的差异
2. 提取共享的持仓轮动核心逻辑
3. 让优化、回测、分析页尽量复用同一套基础状态机

验收：

- 同一参数同一窗口下，优化结果与分析页结果偏差可解释
- 代码重复明显下降

### 阶段 5：收尾与仓库治理

目标：

- 明确 `convertible-bond-crawler` 是否保留

两个选择：

1. 保留为 archive 仓库
   - 只保留历史脚本与研究资料
   - 不再作为运行时依赖

2. 彻底移除
   - 所有运行时依赖已迁入 `vnpy`
   - 父仓库移除 gitlink

## 8.1 当前完成状态

截至 2026-03-08，上述方案已经完成到“彻底移除旧子项目运行角色”的状态：

- Phase A 运行时核心已迁入 [cb_strategy_core](/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/domain/cb_quant/cb_strategy_core/__init__.py)
- `CrawlerPhaseABacktestAdapter` 已改为直接引用新 core，不再动态加载旧脚本
- `CbHistoryService` 不再支持从旧 Excel 快照做运行时 bootstrap
- `cb_quant_service` 优化链路已复用 `cb_strategy_core` 的共享轻量回测核心
- 应用启动流程已移除 legacy bootstrap，仅保留当日行情快照同步
- 父仓库中的 `convertible-bond-crawler` gitlink 已移除
- 旧子项目目录已删除，相关资料转存到 `docs/`

## 9. 为什么不建议“先迁数据库，再迁策略内核”

当前主要架构痛点不是数据库，而是策略核心仍然悬挂在外部仓库中。

如果先迁数据库：

- 任务存储层更强
- 但策略调用边界依旧混乱
- 动态加载和双数据路径问题仍然存在

所以更合理的顺序是：

1. 先收拢策略核心
2. 再统一数据入口
3. 再考虑数据库和并发架构升级

## 10. 主要风险

### 风险 1：迁移后筛债结果不一致

来源：

- `filter.py` 中存在很多隐含字段假设
- 不同数据源字段类型和缺省值可能不同

缓解：

- 为 `normalize_market_frame(...)` 建回归测试
- 对相同历史快照做“旧逻辑 vs 新逻辑”候选列表 diff

### 风险 2：回测收益结果出现口径漂移

来源：

- 调仓时点、强赎处理、`until_win`、仓位权重等细节容易漂移

缓解：

- 建黄金样本集
- 对固定窗口、固定参数组合做逐日结果比对

### 风险 3：Web 侧短期同时维护两套逻辑

来源：

- 迁移过程中 adapter 和新 core 可能并存

缓解：

- 适配层长期只保留一份入口
- 不允许业务层同时直接调用旧脚本和新 core

### 风险 4：历史 Excel 依赖一次性移除过快

来源：

- 某些冷启动环境仍可能依赖旧快照文件

缓解：

- 先把 Excel 路径降级为 bootstrap-only
- 观察一段时间后再彻底移除

## 11. 建议的测试与验收方案

### 11.1 回归测试维度

至少覆盖：

- 单日候选池结果一致性
- 近一周窗口回测结果一致性
- 1 年窗口回测结果一致性
- 优化任务 TopN 排名一致性
- 分析页明细指标一致性

### 11.2 建议验收样本

使用固定历史区间，例如：

- 最近 1 周
- 最近 1 个月
- 最近 1 年

每个区间至少选：

- 1 组收益较高参数
- 1 组中性参数
- 1 组无交易参数

### 11.3 验收标准

可接受标准建议为：

- 候选池代码列表完全一致
- 总收益、最大回撤、胜率偏差小于可设阈值
- TopN 排名主体一致

## 12. 实施优先级建议

如果资源有限，建议按下面顺序做：

1. 把策略核心迁入 `vnpy`
2. 去掉动态 import
3. 去掉 Excel 主依赖
4. 统一回测核心
5. 最后处理仓库和数据库治理

## 13. 一句话结论

`convertible-bond-crawler` 不应该继续作为 `vnpy` 的长期运行时外部依赖存在。

它最有价值的是 Phase A 策略内核，这部分应该被拆出并吸收到 `vnpy cb-quant` 内部；而旧的抓取、Excel、HTML 报表链路应逐步退场，最终让 `vnpy` 成为唯一主系统。
