/**
 * 数据血缘定义 —— 每个主流程节点上下游的数据来源、处理逻辑和产出。
 * 纯静态数据，用于右侧抽屉展示，不涉及运行时请求。
 */

type LineageDataSource = {
  label: string;
  desc: string;
};

type LineageProcessing = {
  summary: string;
  steps: string[];
};

type LineageOutput = {
  label: string;
  desc: string;
  /** 消费方阶段 */
  to?: string;
};

type LineageDataModel = {
  name: string;
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
    summary: "聚合社交信号，计算热度评分。",
    steps: [
      "按 symbol 汇总 mentions 和 upvotes",
      "计算 24 小时排名变化和提及变化百分比",
      "通过热度公式 (mentions + growthBonus + upvoteSignal) 生成 heatScore",
      "按热度降序排列，输出 Top N 热榜",
    ],
  },
  outputs: [
    { label: "热榜列表", desc: "包含 symbol、mentions、upvotes、mentionChange、rank24hAgo 的排序清单。", to: "discover" },
    { label: "手动引入", desc: "用户点击「加入发现池」后以 source=hot-monitor 写入候选池。", to: "discover" },
  ],
  models: [
    { name: "SocialHotStockItem", fields: ["symbol", "mentions", "upvotes", "mentionChange", "mentionChangePct", "rank24hAgo"] },
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
    { label: "Hot Monitor 线索", desc: "从热榜手动引入，source=hot-monitor。" },
    { label: "手动纳入", desc: "用户提交 symbol + thesis + 可选投研报告，source=manual。" },
    { label: "Universe Buckets", desc: "预定义股票池（AI Infra、Cloud、Cybersecurity、Semiconductors）作为扫描范围。" },
    { label: "行情与基本面", desc: "Polygon / Yahoo Finance 提供价格、市值、财务数据。" },
  ],
  processing: {
    summary: "多因子评分引擎 + 晋级门槛检查。",
    steps: [
      "8 因子加权评分：Growth、Quality、Valuation、Size、Evidence、Theme、Momentum、Risk",
      "生命周期阶段分配：discovery → validation → acceleration → crowded / falsified",
      "flowStatus 计算：candidate → watch-ready（所有门槛通过）/ blocked",
      "晋级门槛检查：证据数 ≥ 2、风险 ≠ high、动量 ≠ cooling、阶段 ≥ validation",
    ],
  },
  outputs: [
    { label: "候选池", desc: "评分排序的候选标的列表，包含 stage、flowStatus、promotionChecks。" },
    { label: "研究卡片", desc: "每个 symbol 的深度研报卡片（thesis、evidence、risk）。", to: "research" },
    { label: "主题分析", desc: "候选按 theme 归类，汇总 heat 和 trend。", to: "themes" },
    { label: "可晋级标的", desc: "flowStatus=watch-ready 的候选，可推进至 Watchlist。", to: "watchlist" },
  ],
  models: [
    { name: "TenxCandidate", fields: ["symbol", "score", "stage", "flowStatus", "riskLevel", "momentum", "evidenceCount", "promotionChecks"] },
    { name: "TenxResearchCard", fields: ["symbol", "thesisSummary", "scoreBreakdown", "evidenceItems", "riskItems"] },
    { name: "TenxTheme", fields: ["slug", "name", "heat", "trend", "relatedSymbols"] },
    { name: "TenxWorkspaceSnapshot", fields: ["candidates", "themes", "watchlist", "timeline"] },
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
    { label: "候选池标的", desc: "来自 Discover 的候选 symbol，按财报临近程度排序。" },
    { label: "财报日历", desc: "SEC 公告 + Yahoo Finance 提供下一次财报日、EPS/Revenue 预期。" },
    { label: "期权链数据", desc: "Polygon API 提供隐含波动率、C/P 比率、未平仓量等。" },
  ],
  processing: {
    summary: "财报时间窗口评分 + 期权结构分析。",
    steps: [
      "按 daysToEarnings 排序，生成财报短线优先级列表",
      "shortlineSignal 分级：优先复核 → 准备清单 → 观察 → 低频跟踪",
      "期权流动性评分 (liquidityScore) 和资金流评分 (flowScore)",
      "C/P Volume & OI 比率、maxPain、impliedVolatility 汇总",
      "综合 optionSelectionScore 输出期权交易信号",
    ],
  },
  outputs: [
    { label: "财报短线", desc: "按临近程度排序的财报日程表，含 EPS/Rev 预期和行动建议。", to: "watchlist" },
    { label: "期权信号", desc: "流动性、资金流和结构评分，输出 optionSignal 和 actionLabel。", to: "watchlist" },
  ],
  models: [
    { name: "TenxEarningsShortlineItem", fields: ["symbol", "daysToEarnings", "shortlineSignal", "epsEstimate", "revenueEstimate", "actionLabel"] },
    { name: "TenxEarningsOptionItem", fields: ["symbol", "liquidityScore", "flowScore", "callPutVolumeRatio", "avgImpliedVolatility", "optionSignal"] },
    { name: "TenxEarningsLens", fields: ["shortline", "options", "notes"] },
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
    { label: "晋级候选", desc: "Discover 中 flowStatus=watch-ready 且通过所有 promotionChecks 的标的。" },
    { label: "价格地图", desc: "技术分析产出的 base/bull/bear 目标区间和关键价位。" },
    { label: "用户确认", desc: "人工点击「观察」按钮确认晋级，系统自动创建事件追踪规则。" },
  ],
  processing: {
    summary: "论文追踪 + 自动挂接事件规则。",
    steps: [
      "验证晋级条件：证据数 ≥ 2、风险 ≠ high、动量 ≠ cooling",
      "记录 thesisStatus（strengthening / needs-review / at-risk）",
      "自动挂接 P2 事件追踪规则，默认 7 天复核周期",
      "捕获 priceSnapshot：当前价、目标区间、置信度",
      "三层监控：事件层（收入/订单预期变化）、结构层（价格进入目标区）、执行层（复核后才可交易表达）",
    ],
  },
  outputs: [
    { label: "跟踪标的", desc: "已确认持续跟踪的标的列表，含论文状态和下次观察点。", to: "alerts" },
    { label: "活跃提醒", desc: "挂接的事件追踪规则触发的实时提醒。", to: "alerts" },
  ],
  models: [
    { name: "TenxWatchlistItem", fields: ["symbol", "thesisStatus", "riskLevel", "activeAlertCount", "trackingStatus", "nextAlertDue"] },
    { name: "TenxPriceSnapshot", fields: ["currentPrice", "posture", "baseTargetLow", "baseTargetHigh", "upsidePctMid", "downsidePctMid"] },
    { name: "TenxPriceMap", fields: ["baseTarget", "bullTarget", "bearZone", "keyLevels", "scenarioPaths", "invalidationRules"] },
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
    { label: "事件监控器", desc: "FOMC 会议 (P1)、财报日历 (P2)、政治信号 (P2)、高管事件 (P2)。" },
    { label: "Watchlist 事件", desc: "已跟踪标的的价格变动、财报事件和论文状态变化。" },
    { label: "市场数据", desc: "实时价格变化和技术信号。" },
    { label: "政治信号", desc: "Trump 提及、政治交易披露 (Senate/House filings)。" },
  ],
  processing: {
    summary: "三层分析 + 优先级分类 + 证据评级。",
    steps: [
      "事件层：是否出现改变收入/订单/交付预期的新事件",
      "结构层：价格是否进入 Base/Bull/Bear 目标区",
      "执行层：未复核价格地图和最大亏损前不升级为交易表达",
      "优先级分类：P1 (立即行动)、P2 (需要复核)、P3 (持续监控)",
      "证据评级 (A/B/C/D) + 置信度 (low/medium/high)",
    ],
  },
  outputs: [
    { label: "提醒中心", desc: "按严重程度排序的提醒列表，含行动建议和失效信号。" },
    { label: "行动建议", desc: "每条提醒的 nextAction 和 invalidationSignals。" },
  ],
  models: [
    { name: "TenxAlertItem", fields: ["symbol", "severity", "alertType", "eventLayer", "structureLayer", "executionLayer", "nextAction", "invalidationSignals"] },
    { name: "TenxAlertCenter", fields: ["items", "freshness", "availableActions"] },
    { name: "TenxEventMonitor", fields: ["rules", "events", "sourceStatus", "watchlistSymbols"] },
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
