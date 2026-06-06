/**
 * 数据血缘定义 —— 每个主流程节点上下游的数据来源、处理逻辑和产出。
 * 基于统一的 PostgreSQL oltp / olap / dim 三层架构。
 * 纯静态数据，用于右侧抽屉展示，不涉及运行时请求。
 */

type LineageDataSource = {
  label: string;
  desc: string;
  /** 数据所在 schema.table */
  store?: string;
};

type LineageProcessing = {
  summary: string;
  steps: string[];
};

type LineageOutput = {
  label: string;
  desc: string;
  /** 写入的 schema.table */
  store?: string;
  /** 消费方阶段 */
  to?: string;
};

type LineageDataModel = {
  name: string;
  /** schema 前缀 */
  schema: "oltp" | "olap" | "dim";
  fields: string[];
};

type LineageApiEndpoint = {
  method: string;
  path: string;
  desc: string;
};

export type LineageStage = {
  title: string;
  summary: string;
  upstream: LineageDataSource[];
  processing: LineageProcessing;
  outputs: LineageOutput[];
  models: LineageDataModel[];
  apis: LineageApiEndpoint[];
};

/* ────────────────────── Hot Monitor ────────────────────── */

const hotMonitor: LineageStage = {
  title: "Hot Monitor",
  summary: "从社交媒体实时抓取股票热度，生成线索榜单，手动引入 Discover。",
  upstream: [
    { label: "Reddit 社区", desc: "r/wallstreetbets、r/stocks 等子版块，通过 ApeWisdom API 聚合。" },
    { label: "ApeWisdom API", desc: "实时提供过去 24 小时提及次数、点赞数和排名变化。" },
  ],
  processing: {
    summary: "聚合社交信号，计算热度评分，持久化到 oltp 快照表。",
    steps: [
      "按 symbol 汇总 mentions 和 upvotes",
      "计算 24 小时排名变化和提及变化百分比",
      "通过热度公式 (mentions + growthBonus + upvoteSignal) 生成 heatScore",
      "按热度降序排列，输出 Top N 热榜",
      "整批快照写入 oltp.social_hot_stock_snapshot (items_json JSONB)",
    ],
  },
  outputs: [
    { label: "热榜快照", desc: "每次拉取的完整快照存入 oltp.social_hot_stock_snapshot，items_json 含逐条明细。", store: "oltp.social_hot_stock_snapshot" },
    { label: "手动引入", desc: "用户点击「加入发现池」后以 source=hot-monitor 写入 oltp.user_discover_candidate_current。", store: "oltp.user_discover_candidate_current", to: "discover" },
  ],
  models: [
    { name: "social_hot_stock_snapshot", schema: "oltp", fields: ["id", "source", "fetched_at_epoch", "item_count", "items_json"] },
  ],
  apis: [
    { method: "GET", path: "/api/v1/social-hot-stocks", desc: "拉取 ApeWisdom 社交热股榜" },
  ],
};

/* ────────────────────── Discover ────────────────────── */

const discover: LineageStage = {
  title: "Discover",
  summary: "候选池核心：对纳入的标的进行多因子评分、生命周期管理和晋级门槛检查。",
  upstream: [
    { label: "Hot Monitor 线索", desc: "从热榜手动引入，写入 oltp.user_discover_candidate_current。", store: "oltp.social_hot_stock_snapshot" },
    { label: "手动纳入", desc: "用户提交 symbol + thesis + 可选投研报告，source=manual。" },
    { label: "Universe Buckets", desc: "预定义股票池（AI Infra、Cloud、Cybersecurity、Semiconductors）。" },
    { label: "行情与基本面", desc: "每日价格写入 olap.us_equity_price_daily_raw，财务数据写入 olap.security_financial_statement_raw。", store: "olap.us_equity_price_daily_raw" },
  ],
  processing: {
    summary: "ODS → DWD → DWS → ADS 四层管道，多因子评分 + 晋级门槛检查。",
    steps: [
      "ODS 层：原始行情 (olap.us_equity_price_daily_raw) 和财报 (olap.security_financial_statement_raw) 入库",
      "DWD 层：生成 olap.security_market_daily（日收益率、市值）和 olap.security_price_technical_daily（MA/ATR/波动率）",
      "DWS 层：计算 olap.security_feature_daily（因子特征）和 olap.security_score_component_daily（8 因子评分）",
      "ADS 层：产出 olap.candidate_pool_daily（排序候选）和 olap.research_card_current（研究卡片）",
      "OLTP 层：用户操作写入 oltp.user_discover_candidate_current，晋级检查结果更新 flowStatus",
    ],
  },
  outputs: [
    { label: "候选池", desc: "olap.candidate_pool_daily 提供评分排序的候选列表。", store: "olap.candidate_pool_daily" },
    { label: "评分明细", desc: "olap.security_score_component_daily 记录每个因子的得分和阶段。", store: "olap.security_score_component_daily" },
    { label: "研究卡片", desc: "olap.research_card_current 存储论文、证据和风险条目。", store: "olap.research_card_current", to: "research" },
    { label: "主题热度", desc: "olap.theme_heat_daily 按主题聚合热度和龙头标的。", store: "olap.theme_heat_daily", to: "themes" },
    { label: "可晋级标的", desc: "oltp.user_discover_candidate_current 中 flowStatus=watch-ready 的候选。", store: "oltp.user_discover_candidate_current", to: "watchlist" },
  ],
  models: [
    { name: "dim.security", schema: "dim", fields: ["security_id", "symbol", "company_name", "sector", "industry"] },
    { name: "olap.security_score_component_daily", schema: "olap", fields: ["security_id", "trade_date", "growth_score", "quality_score", "total_score", "stage"] },
    { name: "olap.candidate_pool_daily", schema: "olap", fields: ["security_id", "trade_date", "rank_no", "total_score", "stage", "risk_tags"] },
    { name: "oltp.user_discover_candidate_current", schema: "oltp", fields: ["user_id", "symbol", "source", "stage", "theme", "thesis", "score"] },
  ],
  apis: [
    { method: "GET", path: "/api/v1/tenx-hunter/workspace", desc: "加载完整工作区快照（候选+主题+观察+时间线）" },
    { method: "POST", path: "/api/v1/tenx-hunter/discover", desc: "手动新增候选标的" },
    { method: "GET", path: "/api/v1/tenx-hunter/research/:symbol", desc: "获取单个标的的深度研究卡片" },
  ],
};

/* ────────────────────── Earnings ────────────────────── */

const earnings: LineageStage = {
  title: "Earnings",
  summary: "财报日历与期权链分析，作为进入观察池前的事件验证层。",
  upstream: [
    { label: "候选池标的", desc: "来自 olap.candidate_pool_daily 的候选 symbol，按财报临近程度排序。", store: "olap.candidate_pool_daily" },
    { label: "财报日历", desc: "原始数据入 olap.us_earnings_calendar_raw，清洗后写 olap.security_earnings_calendar_current。", store: "olap.us_earnings_calendar_raw" },
    { label: "期权链数据", desc: "原始合约数据入 olap.us_option_chain_raw，聚合摘要写 olap.security_option_chain_summary_daily。", store: "olap.security_option_chain_summary_daily" },
    { label: "分析师预期", desc: "EPS/Revenue 预期写入 olap.us_analyst_estimate_raw，汇总到 olap.security_estimate_current。", store: "olap.security_estimate_current" },
  ],
  processing: {
    summary: "财报时间窗口评分 + 期权结构分析，数据全链路在 olap 层流转。",
    steps: [
      "olap.us_earnings_calendar_raw → olap.security_earnings_calendar_current：清洗财报日期和预期",
      "按 daysToEarnings 排序，生成 shortlineSignal：优先复核 → 准备清单 → 观察 → 低频跟踪",
      "olap.us_option_chain_raw → olap.security_option_chain_summary_daily：聚合流动性、资金流和结构评分",
      "C/P Volume & OI 比率、maxPain、impliedVolatility 汇总",
      "综合 optionSelectionScore 输出期权交易信号",
    ],
  },
  outputs: [
    { label: "财报短线", desc: "基于 olap.security_earnings_calendar_current 生成的日程和行动建议。", store: "olap.security_earnings_calendar_current", to: "watchlist" },
    { label: "期权摘要", desc: "olap.security_option_chain_summary_daily 提供流动性、资金流和信号评分。", store: "olap.security_option_chain_summary_daily", to: "watchlist" },
  ],
  models: [
    { name: "olap.us_earnings_calendar_raw", schema: "olap", fields: ["event_id", "symbol", "earnings_date", "eps_estimate", "revenue_estimate"] },
    { name: "olap.security_earnings_calendar_current", schema: "olap", fields: ["security_id", "next_earnings_date", "days_to_earnings", "eps_estimate"] },
    { name: "olap.security_option_chain_summary_daily", schema: "olap", fields: ["symbol", "trade_date", "liquidity_score", "flow_score", "selection_score"] },
  ],
  apis: [
    { method: "GET", path: "/api/v1/tenx-hunter/earnings-lens", desc: "加载财报日历和期权分析数据" },
  ],
};

/* ────────────────────── Watchlist ────────────────────── */

const watchlist: LineageStage = {
  title: "Watchlist",
  summary: "只保留通过晋级门槛的标的，持续跟踪论文状态和价格地图。",
  upstream: [
    { label: "晋级候选", desc: "oltp.user_discover_candidate_current 中 flowStatus=watch-ready 且通过所有 promotionChecks 的标的。", store: "oltp.user_discover_candidate_current" },
    { label: "价格地图", desc: "olap.price_map_current 提供 base/bull/bear 目标区间、关键价位和情景路径。", store: "olap.price_map_current" },
    { label: "用户确认", desc: "人工点击「观察」按钮，写入 oltp.user_watchlist_state_current，同时自动创建 oltp.user_alert_rule_current。", store: "oltp.user_watchlist_state_current" },
  ],
  processing: {
    summary: "晋级验证 → 状态记录 → 自动挂接事件规则，跨 oltp 和 olap 层协作。",
    steps: [
      "验证晋级条件：证据数 ≥ 2、风险 ≠ high、动量 ≠ cooling",
      "写入 oltp.user_watchlist_state_current（state=watching）",
      "自动挂接 P2 事件追踪规则到 oltp.user_alert_rule_current，默认 7 天复核周期",
      "DWS 层计算 olap.security_target_range_daily（目标区间）和 olap.security_key_level_daily（关键价位）",
      "ADS 层产出 olap.price_map_current（完整价格地图）和 olap.price_map_history_daily（历史快照）",
      "三层监控：事件层 → 结构层 → 执行层，触发时写入 olap.watchlist_alert_daily",
    ],
  },
  outputs: [
    { label: "跟踪标的", desc: "oltp.user_watchlist_state_current 记录论文状态和下次观察点。", store: "oltp.user_watchlist_state_current", to: "alerts" },
    { label: "价格地图", desc: "olap.price_map_current 提供实时目标区和情景路径。", store: "olap.price_map_current" },
    { label: "事件提醒", desc: "olap.watchlist_alert_daily 记录触发的提醒和行动建议。", store: "olap.watchlist_alert_daily", to: "alerts" },
  ],
  models: [
    { name: "oltp.user_watchlist_state_current", schema: "oltp", fields: ["user_id", "security_id", "symbol", "state", "latest_action_time"] },
    { name: "olap.price_map_current", schema: "olap", fields: ["security_id", "current_price", "posture", "base_target", "bull_target", "bear_zone", "key_levels"] },
    { name: "oltp.user_alert_rule_current", schema: "oltp", fields: ["rule_id", "symbol", "rule_type", "severity", "status", "rule_payload"] },
  ],
  apis: [
    { method: "GET", path: "/api/v1/tenx-hunter/workspace", desc: "工作区快照中的 watchlist 区域" },
    { method: "POST", path: "/api/v1/tenx-hunter/watchlist", desc: "确认候选晋级到观察池" },
    { method: "PATCH", path: "/api/v1/tenx-hunter/watchlist/:symbol", desc: "更新观察标的跟踪状态" },
  ],
};

/* ────────────────────── Alerts ────────────────────── */

const alerts: LineageStage = {
  title: "Alerts",
  summary: "事件提醒中心：三层分析（事件/结构/执行）+ 优先级分类。",
  upstream: [
    { label: "事件监控规则", desc: "oltp.user_alert_rule_current 定义监控范围和优先级。", store: "oltp.user_alert_rule_current" },
    { label: "Watchlist 标的", desc: "oltp.user_watchlist_state_current 提供当前跟踪的 symbol 列表。", store: "oltp.user_watchlist_state_current" },
    { label: "市场事件", desc: "olap.security_event_timeline 和 olap.security_document_signal 提供事件和信号。", store: "olap.security_event_timeline" },
    { label: "价格数据", desc: "olap.security_market_daily 提供实时价格变动和技术信号。", store: "olap.security_market_daily" },
  ],
  processing: {
    summary: "基于 oltp 规则驱动，跨 olap 事件/价格数据做三层分析，产出写入 oltp 和 olap。",
    steps: [
      "事件层：扫描 olap.security_event_timeline，判断是否出现改变收入/订单/交付预期的新事件",
      "结构层：对比 olap.price_map_current 和 olap.security_market_daily，判断价格是否进入目标区",
      "执行层：检查 olap.price_map_hit_review_daily，未复核前不升级为交易表达",
      "优先级分类：P1 (立即行动)、P2 (需要复核)、P3 (持续监控)",
      "写入 oltp.user_event_monitor_event_current（OLTP 事务操作）和 olap.watchlist_alert_daily（OLAP 分析记录）",
    ],
  },
  outputs: [
    { label: "事件监控", desc: "oltp.user_event_monitor_event_current 记录匹配的事件、证据评级和行动建议。", store: "oltp.user_event_monitor_event_current" },
    { label: "提醒中心", desc: "olap.watchlist_alert_daily 按严重程度排序，含失效信号。", store: "olap.watchlist_alert_daily" },
  ],
  models: [
    { name: "oltp.user_event_monitor_event_current", schema: "oltp", fields: ["monitor_event_id", "symbol", "priority", "evidence_grade", "confidence", "event_layer", "structure_layer", "execution_layer"] },
    { name: "olap.watchlist_alert_daily", schema: "olap", fields: ["alert_id", "symbol", "alert_type", "severity", "alert_message", "evidence_refs"] },
    { name: "olap.security_event_timeline", schema: "olap", fields: ["event_id", "symbol", "event_type", "title", "sentiment", "importance"] },
  ],
  apis: [
    { method: "GET", path: "/api/v1/tenx-hunter/alerts", desc: "加载提醒中心数据" },
    { method: "GET", path: "/api/v1/tenx-hunter/event-monitor", desc: "加载事件监控器状态" },
    { method: "POST", path: "/api/v1/tenx-hunter/alerts", desc: "创建新提醒" },
  ],
};

/* ────────────────────── Export ────────────────────── */

export const lineageByStage: Record<string, LineageStage> = {
  "hot-monitor": hotMonitor,
  discover,
  earnings,
  watchlist,
  alerts,
};

export const stageKeys = ["hot-monitor", "discover", "earnings", "watchlist", "alerts"] as const;
