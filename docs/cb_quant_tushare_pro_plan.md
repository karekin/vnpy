# CB Quant + Tushare Pro 数据与回测落地方案

## 1. 目标
- 数据源统一：策略、回测任务、回测结果统一落数据库，去掉 JSON 分散存储。
- 数据闭环：Tushare Pro -> 标准化因子/行情表 -> 回测引擎 -> 任务结果/持仓/换仓明细。
- 可运维：支持按业务日期筛选任务、任务手动取消、可追溯任务输入输出。

## 2. 建议接入的 Tushare Pro 接口

### 2.1 可转债主数据与行情
- `cb_basic`：可转债基础信息（代码、转股价、到期、评级等）。
- `cb_issue`：发行信息（规模、日期等）。
- `cb_call`：赎回/回售相关事件。
- `cb_daily`：可转债日线行情。
- `cb_price_chg`：转股价变动（前后转股价、起始日期等）。
- `cb_share`：转债转股结果（存续规模变化）。
- `cb_rate`：可转债票面利率。
- `cb_factor_pro`：官方因子增强数据（用于对账和快速构建因子层）。

### 2.2 正股与交易日辅助
- `trade_cal`：交易日历（停牌/节假日判断、业务日期对齐）。
- `stock_basic`：正股基础信息映射。
- `daily`：正股日线行情。
- `daily_basic`：正股估值指标（PE/PB/换手率等）。
- `adj_factor`：复权因子（正股收益率和波动率计算更稳）。

## 3. 数据库分层（建议）

### 3.1 ODS 原始层（可追溯）
- `ods_tushare_cb_basic`
- `ods_tushare_cb_daily`
- `ods_tushare_cb_event`（issue/call/share/price_chg/rate 合并或分表）
- `ods_tushare_stock_daily`

字段建议：`biz_date`, `ts_code`, `payload_json`, `source`, `ingested_at`。

### 3.2 DWD 标准层（回测直接可用）
- `dwd_cb_security_dim`（可转债维表）
- `dwd_cb_daily_bar`（可转债日行情）
- `dwd_stock_daily_bar`（正股日行情）
- `dwd_cb_event`（赎回/转股价调整/强赎触发等）
- `dwd_cb_factor_daily`（统一因子快照，含你们策略字段）

主键建议：`(trade_date, bond_id)`；事件表主键：`(event_date, bond_id, event_type)`。

### 3.3 业务层（策略与回测）
- `strategy_template`
- `strategy_template_config`
- `backtest_job`
- `backtest_result`（每个 job/window 一行）
- `backtest_nav_daily`（净值曲线）
- `backtest_rotation`（换仓明细）
- `backtest_trade`（交易级明细）

## 4. ETL 流程

### 4.1 全量初始化
1. 先拉 `trade_cal` 建交易日基准。
2. 拉 `cb_basic/issue/rate` 构建债券主数据。
3. 按交易日批量拉 `cb_daily` 与正股 `daily/daily_basic/adj_factor`。
4. 拉 `cb_price_chg/cb_share/cb_call` 事件并回填到 `dwd_cb_event`。
5. 生成 `dwd_cb_factor_daily`（双低、溢价率、规模、波动等策略因子）。

### 4.2 日增量
- 每日收盘后按 `trade_date` 增量抓取 + `UPSERT`。
- 事件类接口按最近 N 天重拉（建议 30 天）做幂等覆盖，防止公告回补。

## 5. 如何把数据整理成策略所需字段
- 标准输出视图：`vw_cb_backtest_input(trade_date, cb_code, cb_name, price, premium_rt, dblow, stock_pb, stock_volatility, remain_scale_yi, is_ransom_flag, ...)`。
- `dblow`、`premium_rt`、`stock_volatility` 等统一在 `dwd_cb_factor_daily` 计算。
- 回测入口仅依赖该视图，屏蔽数据源差异（Tushare / Eastmoney / 本地快照）。

## 6. 如何指定策略对历史数据回测
1. 前端选择 `template_id + 参数空间 + window/start_date/end_date + business_date`。
2. 后端从 `strategy_template_config` 解析参数组合，写入 `backtest_job`。
3. Worker 按 job 读取 `vw_cb_backtest_input` 切片运行回测。
4. 写回：
   - `backtest_job`（状态、进度、取消标记）
   - `backtest_result`（CAGR/MDD/Calmar/胜率等）
   - `backtest_nav_daily`、`backtest_rotation`、`backtest_trade`。
5. 排行榜和对比接口统一基于 DB 视图生成，不再依赖内存对象。

## 7. 取消与业务日期
- `backtest_job.cancel_requested` + `status in (queued,running,finished,failed,cancelled)`。
- `queued`：直接置 `cancelled`。
- `running`：置 `cancel_requested=1`，Worker 在阶段边界检查后尽快终止并落 `cancelled`。
- 所有查询接口支持 `business_date`、`business_date_from/to`。

## 8. 分期实施建议
- Phase 1（已完成一部分）：策略模板与回测任务 SQLite 化，支持取消接口、按业务日期筛选。
- Phase 2：回测结果明细（nav/rotation/trade）持久化，重启可恢复列表与分析。
- Phase 3：Tushare ETL + 因子层 + 回测输入视图切换到 DB。
- Phase 4：任务调度与监控（重试、告警、数据质量校验）。

### 8.1 当前交付状态（2026-02-25）
- ✅ 策略模板从 JSON 迁移到 DB（保留一次性 JSON 兜底迁移逻辑）
- ✅ 回测任务落库，支持手动取消，支持 `business_date` / `business_date_from` / `business_date_to`
- ✅ Tushare Pro 接入可用（本地 `.env.tushare.local` + Token + HTTP URL 自动读取）
- ✅ 前后端链路打通：
  - 后端：`/strategy/history-sync/tushare*`、`/backtest/jobs*`
  - 前端：回测评估页支持 Tushare 同步、回测任务筛选、手动取消

## 9. 当前已实现接口（2026-02-25）
- `POST /api/v1/cb-quant/strategy/history-sync/tushare`
  - 入参：`start_date`, `end_date`, `max_trade_days`
  - 作用：从 Tushare Pro 拉取交易日历、转债日线、正股日线/估值，生成因子快照并写入回测快照库
- `GET /api/v1/cb-quant/strategy/history-sync/tushare/status`
  - 作用：查询最近一次 Tushare 同步日志
- `GET /api/v1/cb-quant/strategy/history-sync/tushare/summary`
  - 作用：查询 Tushare ODS/DWD 数据覆盖范围

环境变量：
- `TUSHARE_TOKEN`：必填，Tushare Pro Token
- `TUSHARE_PRO_TOKEN`：可选，和 `TUSHARE_TOKEN` 二选一
- `TUSHARE_HTTP_URL`：可选，默认 `http://lianghua.nanyangqiankun.top`
- 依赖：`pip install tushare`

本地配置文件（推荐）：
- 项目根目录 `.env.tushare.local`
- 支持 `export KEY='value'` 格式
- 后端会自动读取该文件（环境变量优先）
